from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
from abc import ABC
from abc import abstractmethod
from base64 import b64encode
from ssl import create_default_context

import aiohttp
import requests.auth
from aiohttp import ClientConnectionError
from aiohttp import ServerDisconnectedError
from aiohttp import ServerTimeoutError
from requests.utils import parse_dict_header
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from . import __version__
from . import exceptions
from .utils import expand_path

logger = logging.getLogger(__name__)
USERAGENT = f"vdirsyncer/{__version__}"

# 'hack' to prevent aiohttp from loading the netrc config,
# but still allow it to read PROXY_* env vars.
# Otherwise, if our host is defined in the netrc config,
# aiohttp will overwrite our Authorization header.
# https://github.com/pimutils/vdirsyncer/issues/1138
os.environ["NETRC"] = "NUL" if platform.system() == "Windows" else "/dev/null"


class AuthMethod(ABC):
    def __init__(self, username, password):
        self.username = username
        self.password = password

    @abstractmethod
    def handle_401(self, response):
        raise NotImplementedError

    @abstractmethod
    def get_auth_header(self, method, url):
        raise NotImplementedError

    def __eq__(self, other):
        if not isinstance(other, AuthMethod):
            return False
        return (
            self.__class__ == other.__class__
            and self.username == other.username
            and self.password == other.password
        )


class BasicAuthMethod(AuthMethod):
    def handle_401(self, _response):
        pass

    def get_auth_header(self, _method, _url):
        auth_str = f"{self.username}:{self.password}"
        return "Basic " + b64encode(auth_str.encode("utf-8")).decode("utf-8")


class DigestAuthMethod(AuthMethod):
    # make class var to 'cache' the state, which is more efficient because otherwise
    # each request would first require another 'initialization' request.
    _auth_helpers: dict[tuple[str, str], requests.auth.HTTPDigestAuth] = {}

    def __init__(self, username: str, password: str):
        super().__init__(username, password)

        self._auth_helper = self._auth_helpers.get(
            (username, password), requests.auth.HTTPDigestAuth(username, password)
        )
        self._auth_helpers[(username, password)] = self._auth_helper

    @property
    def auth_helper_vars(self):
        return self._auth_helper._thread_local

    def handle_401(self, response):
        s_auth = response.headers.get("www-authenticate", "")

        if "digest" in s_auth.lower():
            # Original source:
            # https://github.com/psf/requests/blob/f12ccbef6d6b95564da8d22e280d28c39d53f0e9/src/requests/auth.py#L262-L263
            pat = re.compile(r"digest ", flags=re.IGNORECASE)
            self.auth_helper_vars.chal = parse_dict_header(pat.sub("", s_auth, count=1))

    def get_auth_header(self, method, url):
        self._auth_helper.init_per_thread_state()

        if not self.auth_helper_vars.chal:
            # Need to do init request first
            return ""

        return self._auth_helper.build_digest_header(method, url)


def prepare_auth(auth, username, password):
    if username and password:
        if auth == "basic" or auth is None:
            return BasicAuthMethod(username, password)
        if auth == "digest":
            return DigestAuthMethod(username, password)
        if auth == "guess":
            raise exceptions.UserError(
                "'Guess' authentication is not supported in this version of "
                "vdirsyncer.\n"
                "Please explicitly specify either 'basic' or 'digest' auth instead. \n"
                "See the following issue for more information: "
                "https://github.com/pimutils/vdirsyncer/issues/1015"
            )
        else:
            raise exceptions.UserError(f"Unknown authentication method: {auth}")
    elif auth:
        raise exceptions.UserError(
            f"You need to specify username and password for {auth} authentication."
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


class TransientNetworkError(exceptions.Error):
    """Transient network condition that should be retried."""


def _is_safe_to_retry_method(method: str) -> bool:
    """Returns True if the HTTP method is safe/idempotent to retry.

    We consider these safe for our WebDAV usage:
    - GET, HEAD, OPTIONS: standard safe methods
    - PROPFIND, REPORT: read-only DAV queries used for listing/fetching
    """
    return method.upper() in {"GET", "HEAD", "OPTIONS", "PROPFIND", "REPORT"}


class UsageLimitReached(exceptions.Error):
    pass


async def _is_quota_exceeded_google(response: aiohttp.ClientResponse) -> bool:
    """Return True if the response JSON indicates Google-style `usageLimits` exceeded.

    Expected shape:
    {"error": {"errors": [{"domain": "usageLimits", ...}], ...}}

    See https://developers.google.com/workspace/calendar/api/guides/errors#403_usage_limits_exceeded
    """
    try:
        data = await response.json(content_type=None)
    except Exception:
        return False

    if not isinstance(data, dict):
        return False

    error = data.get("error")
    if not isinstance(error, dict):
        return False

    errors = error.get("errors")
    if not isinstance(errors, list):
        return False

    for entry in errors:
        if isinstance(entry, dict) and entry.get("domain") == "usageLimits":
            return True

    return False


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=(
        retry_if_exception_type(UsageLimitReached)
        | retry_if_exception_type(TransientNetworkError)
    ),
    reraise=True,
)
async def request(
    method,
    url,
    session,
    auth=None,
    latin1_fallback=True,
    **kwargs,
):
    """Wrapper method for requests, to ease logging and mocking as well as to
    support auth methods currently unsupported by aiohttp.

    Parameters should be the same as for ``aiohttp.request``, except:

    :param session: A requests session object to use.
    :param auth: The HTTP ``AuthMethod`` to use for authentication.
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
    logger.debug(kwargs.get("data"))
    logger.debug("Sending request...")

    assert isinstance(kwargs.get("data", b""), bytes)

    cert = kwargs.pop("cert", None)
    if cert is not None:
        ssl_context = kwargs.pop("ssl", create_default_context())
        ssl_context.load_cert_chain(*cert)
        kwargs["ssl"] = ssl_context

    headers = kwargs.pop("headers", {})
    response: aiohttp.ClientResponse | None = None
    for _attempt in range(2):
        if auth:
            headers["Authorization"] = auth.get_auth_header(method, url)
        try:
            response = await session.request(method, url, headers=headers, **kwargs)
        except (
            ServerDisconnectedError,
            ServerTimeoutError,
            ClientConnectionError,
            asyncio.TimeoutError,
        ) as e:
            # Retry only if the method is safe/idempotent for our DAV use
            if _is_safe_to_retry_method(method):
                logger.debug(
                    f"Transient network error on {method} {url}: {e}. Will retry."
                )
                raise TransientNetworkError(str(e)) from e
            raise e from None

        if response is None:
            raise RuntimeError("No HTTP response obtained")

        if response.ok or not auth:
            # we don't need to do the 401-loop if we don't do auth in the first place
            break

        if response.status == 401:
            auth.handle_401(response)
            # retry once more after handling the 401 challenge
            continue
        else:
            # some other error, will be handled later on
            break

    if response is None:
        raise RuntimeError("No HTTP response obtained")

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

    if logger.getEffectiveLevel() <= logging.DEBUG and response.status >= 400:
        # https://github.com/pimutils/vdirsyncer/issues/1186
        logger.debug(await response.text())

    if response.status == 403 and await _is_quota_exceeded_google(response):
        raise UsageLimitReached(response.reason)
    if response.status == 412:
        raise exceptions.PreconditionFailed(response.reason)
    if response.status in (404, 410):
        raise exceptions.NotFoundError(response.reason)
    if response.status == 429:
        raise UsageLimitReached(response.reason)

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
