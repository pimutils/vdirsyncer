from __future__ import annotations

import ssl
from typing import Any

import pytest
import trustme


@pytest.fixture(scope="session")
def ca() -> Any:
    return trustme.CA()


@pytest.fixture(scope="session")
def localhost_cert(ca: Any) -> Any:
    return ca.issue_cert("localhost")


@pytest.fixture(scope="session")
def httpserver_ssl_context(localhost_cert: Any) -> Any:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    crt = localhost_cert.cert_chain_pems[0]
    key = localhost_cert.private_key_pem
    with crt.tempfile() as crt_file, key.tempfile() as key_file:
        context.load_cert_chain(crt_file, key_file)

    return context
