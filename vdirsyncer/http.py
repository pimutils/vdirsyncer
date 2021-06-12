import logging

import requests

from . import __version__
from . import DOCS_HOME
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
            return (username, password)
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
            raise exceptions.UserError("Unknown authentication method: {}".format(auth))
    elif auth:
        raise exceptions.UserError(
            "You need to specify username and password "
            "for {} authentication.".format(auth)
        )
    else:
        return None


def prepare_verify(verify, verify_fingerprint):
    if isinstance(verify, (str, bytes)):
        verify = expand_path(verify)
    elif not isinstance(verify, bool):
        raise exceptions.UserError(
            "Invalid value for verify ({}), "
            "must be a path to a PEM-file or boolean.".format(verify)
        )

    if verify_fingerprint is not None:
        if not isinstance(verify_fingerprint, (bytes, str)):
            raise exceptions.UserError(
                "Invalid value for verify_fingerprint "
                "({}), must be a string or null.".format(verify_fingerprint)
            )
    elif not verify:
        raise exceptions.UserError(
            "Disabling all SSL validation is forbidden. Consider setting "
            "verify_fingerprint if you have a broken or self-signed cert."
        )

    return {
        "verify": verify,
        "verify_fingerprint": verify_fingerprint,
    }


def prepare_client_cert(cert):
    if isinstance(cert, (str, bytes)):
        cert = expand_path(cert)
    elif isinstance(cert, list):
        cert = tuple(map(prepare_client_cert, cert))
    return cert


def _install_fingerprint_adapter(session, fingerprint):
    prefix = "https://"
    try:
        from requests_toolbelt.adapters.fingerprint import FingerprintAdapter
    except ImportError:
        raise RuntimeError(
            "`verify_fingerprint` can only be used with "
            "requests-toolbelt versions >= 0.4.0"
        )

    if not isinstance(session.adapters[prefix], FingerprintAdapter):
        fingerprint_adapter = FingerprintAdapter(fingerprint)
        session.mount(prefix, fingerprint_adapter)


def request(
    method, url, session=None, latin1_fallback=True, verify_fingerprint=None, **kwargs
):
    """
    Wrapper method for requests, to ease logging and mocking. Parameters should
    be the same as for ``requests.request``, except:

    :param session: A requests session object to use.
    :param verify_fingerprint: Optional. SHA1 or MD5 fingerprint of the
        expected server certificate.
    :param latin1_fallback: RFC-2616 specifies the default Content-Type of
        text/* to be latin1, which is not always correct, but exactly what
        requests is doing. Setting this parameter to False will use charset
        autodetection (usually ending up with utf8) instead of plainly falling
        back to this silly default. See
        https://github.com/kennethreitz/requests/issues/2042
    """

    if session is None:
        session = requests.Session()

    if verify_fingerprint is not None:
        _install_fingerprint_adapter(session, verify_fingerprint)

    session.hooks = {"response": _fix_redirects}

    func = session.request

    logger.debug("=" * 20)
    logger.debug(f"{method} {url}")
    logger.debug(kwargs.get("headers", {}))
    logger.debug(kwargs.get("data", None))
    logger.debug("Sending request...")

    assert isinstance(kwargs.get("data", b""), bytes)

    r = func(method, url, **kwargs)

    # See https://github.com/kennethreitz/requests/issues/2042
    content_type = r.headers.get("Content-Type", "")
    if (
        not latin1_fallback
        and "charset" not in content_type
        and content_type.startswith("text/")
    ):
        logger.debug("Removing latin1 fallback")
        r.encoding = None

    logger.debug(r.status_code)
    logger.debug(r.headers)
    logger.debug(r.content)

    if r.status_code == 412:
        raise exceptions.PreconditionFailed(r.reason)
    if r.status_code in (404, 410):
        raise exceptions.NotFoundError(r.reason)

    r.raise_for_status()
    return r


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
