# SPDX-License-Identifier: Apache-2.0
#
# Based on:
# https://github.com/googleapis/google-auth-library-python-oauthlib/blob/1fb16be1bad9050ee29293541be44e41e82defd7/google_auth_oauthlib/flow.py#L513

import logging
import wsgiref.simple_server
import wsgiref.util
from typing import Any
from typing import Callable
from typing import Dict
from typing import Iterable
from typing import Optional

logger = logging.getLogger(__name__)


class _WSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    """Custom WSGIRequestHandler."""

    def log_message(self, format, *args):
        # (format is the argument name defined in the superclass.)
        logger.info(format, *args)


class _RedirectWSGIApp:
    """WSGI app to handle the authorization redirect.

    Stores the request URI and displays the given success message.
    """

    last_request_uri: Optional[str]

    def __init__(self, success_message: str):
        """
        :param success_message: The message to display in the web browser the
            authorization flow is complete.
        """
        self.last_request_uri = None
        self._success_message = success_message

    def __call__(
        self,
        environ: Dict[str, Any],
        start_response: Callable[[str, list], None],
    ) -> Iterable[bytes]:
        """WSGI Callable.

        :param environ: The WSGI environment.
        :param start_response: The WSGI start_response callable.
        :returns: The response body.
        """
        start_response("200 OK", [("Content-type", "text/plain; charset=utf-8")])
        self.last_request_uri = wsgiref.util.request_uri(environ)
        return [self._success_message.encode("utf-8")]
