import logging
from ssl import create_default_context

import aiohttp

from . import DOCS_HOME
from . import __version__
from . import exceptions
from .utils import expand_path

logger = logging.getLogger(__name__)
USERAGENT = f"vdirsyncer/{__version__}"


def _detect_faulty_requests():  # pragma: no cover
    text = (
        "Error during import: {e}\n\n"
        "If you have installed vdirsyncer from a distro package, please file "
        "a bug against that package, not vdirsyncer.\n\n"
        "Consult {d}/problems.html#requests-related-importerrors"
        "-based-distributions on how to work around this."
    )

    try:
        from requests_toolbelt.auth.guess import GuessAuth  # noqa
    except ImportError as e:
        import sys

        print(text.format(e=str(e), d=DOCS_HOME), file=sys.stderr)
        sys.exit(1)


_detect_faulty_requests()
del _detect_faulty_requests


def prepare_auth(auth, username, password):
    if username and password:
        if auth == "basic" or auth is None:
            return aiohttp.BasicAuth(username, password)
        elif auth == "digest":
            from requests.auth import HTTPDigestAuth

            return HTTPDigestAuth(username, password)
        elif auth == "guess":
            try:
                from requests_toolbelt.auth.guess import GuessAuth
            except ImportError:
                raise exceptions.UserError(
                    "Your version of requests_toolbelt is too "
                    "old for `guess` authentication. At least "
                    "version 0.4.0 is required."
                )
            else:
                return GuessAuth(username, password)
        else:
            raise exceptions.UserError(f"Unknown authentication method: {auth}")
    elif auth:
        raise exceptions.UserError(
            "You need to specify username and password "
            "for {} authentication.".format(auth)
        )

    return None


def prepare_verify(verify, verify_fingerprint):
    if isinstance(verify, str):
        return create_default_context(cafile=expand_path(verify))
    elif verify is not None:
        raise exceptions.UserError(
            f"Invalid value for verify ({verify}), must be a path to a PEM-file."
        )

    if verify_fingerprint is not None:
        if not isinstance(verify_fingerprint, str):
            raise exceptions.UserError(
                "Invalid value for verify_fingerprint "
                f"({verify_fingerprint}), must be a string."
            )

        return aiohttp.Fingerprint(bytes.fromhex(verify_fingerprint.replace(":", "")))

    return None


def prepare_client_cert(cert):
    if isinstance(cert, (str, bytes)):
        cert = expand_path(cert)
    elif isinstance(cert, list):
        cert = tuple(map(prepare_client_cert, cert))
    return cert


async def request(
    method,
    url,
    session,
    latin1_fallback=True,
    **kwargs,
):
    """Wrapper method for requests, to ease logging and mocking.

    Parameters should be the same as for ``aiohttp.request``, as well as:

    :param session: A requests session object to use.
    :param verify_fingerprint: Optional. SHA256 of the expected server certificate.
    :param latin1_fallback: RFC-2616 specifies the default Content-Type of
        text/* to be latin1, which is not always correct, but exactly what
        requests is doing. Setting this parameter to False will use charset
        autodetection (usually ending up with utf8) instead of plainly falling
        back to this silly default. See
        https://github.com/kennethreitz/requests/issues/2042
    """

    # TODO: Support for client-side certifications.

    session.hooks = {"response": _fix_redirects}

    # TODO: rewrite using
    # https://docs.aiohttp.org/en/stable/client_advanced.html#client-tracing
    logger.debug("=" * 20)
    logger.debug(f"{method} {url}")
    logger.debug(kwargs.get("headers", {}))
    logger.debug(kwargs.get("data", None))
    logger.debug("Sending request...")

    assert isinstance(kwargs.get("data", b""), bytes)

    kwargs.pop("cert", None)  # TODO XXX FIXME!

    response = await session.request(method, url, **kwargs)

    # See https://github.com/kennethreitz/requests/issues/2042
    content_type = response.headers.get("Content-Type", "")
    if (
        not latin1_fallback
        and "charset" not in content_type
        and content_type.startswith("text/")
    ):
        logger.debug("Removing latin1 fallback")
        response.encoding = None

    logger.debug(response.status)
    logger.debug(response.headers)
    logger.debug(response.content)

    if response.status == 412:
        raise exceptions.PreconditionFailed(response.reason)
    if response.status in (404, 410):
        raise exceptions.NotFoundError(response.reason)

    response.raise_for_status()
    return response


def _fix_redirects(r, *args, **kwargs):
    """
    Requests discards of the body content when it is following a redirect that
    is not a 307 or 308. We never want that to happen.

    See:
    https://github.com/kennethreitz/requests/issues/3915
    https://github.com/pimutils/vdirsyncer/pull/585
    https://github.com/pimutils/vdirsyncer/issues/586

    FIXME: This solution isn't very nice. A new hook in requests would be
    better.
    """
    if r.is_redirect:
        logger.debug("Rewriting status code from %s to 307", r.status_code)
        r.status_code = 307
