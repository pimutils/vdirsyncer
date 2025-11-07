from __future__ import annotations

import logging
from typing import Any

import aiohttp
import click_log
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes

from vdirsyncer import http
from vdirsyncer import utils


@pytest.fixture(autouse=True)
def no_debug_output(request: Any) -> Any:
    logger = click_log.basic_config("vdirsyncer")
    logger.setLevel(logging.WARNING)


def test_get_storage_init_args() -> None:
    from vdirsyncer.storage.memory import MemoryStorage

    all, required = utils.get_storage_init_args(MemoryStorage)
    assert all == {"fileext", "collection", "read_only", "instance_name", "no_delete"}
    assert not required


@pytest.mark.asyncio
async def test_request_ssl() -> None:
    async with aiohttp.ClientSession() as session:
        with pytest.raises(
            aiohttp.ClientConnectorCertificateError,
            match="certificate verify failed",
        ):
            await http.request(
                "GET",
                "https://self-signed.badssl.com/",
                session=session,
            )


@pytest.mark.xfail(reason="feature not implemented")
@pytest.mark.asyncio
async def test_request_unsafe_ssl() -> None:
    async with aiohttp.ClientSession() as session:
        await http.request(
            "GET",
            "https://self-signed.badssl.com/",
            verify=False,
            session=session,
        )


def fingerprint_of_cert(cert: Any, hash: Any = hashes.SHA256) -> str:
    return x509.load_pem_x509_certificate(cert.bytes()).fingerprint(hash()).hex()


@pytest.mark.parametrize("hash_algorithm", [hashes.SHA256])
@pytest.mark.asyncio
async def test_request_ssl_leaf_fingerprint(
    httpserver: Any,
    localhost_cert: Any,
    hash_algorithm: Any,
    aio_session: Any,
) -> None:
    fingerprint = fingerprint_of_cert(localhost_cert.cert_chain_pems[0], hash_algorithm)
    bogus = "".join(reversed(fingerprint))

    # We have to serve something:
    httpserver.expect_request("/").respond_with_data("OK")
    url = f"https://127.0.0.1:{httpserver.port}/"

    ssl = http.prepare_verify(None, fingerprint)
    await http.request("GET", url, ssl=ssl, session=aio_session)

    ssl = http.prepare_verify(None, bogus)
    with pytest.raises(aiohttp.ServerFingerprintMismatch):
        await http.request("GET", url, ssl=ssl, session=aio_session)


@pytest.mark.xfail(reason="Not implemented")
@pytest.mark.parametrize("hash_algorithm", [hashes.SHA256])
@pytest.mark.asyncio
async def test_request_ssl_ca_fingerprints(
    httpserver: Any,
    ca: Any,
    hash_algorithm: Any,
    aio_session: Any,
) -> None:
    fingerprint = fingerprint_of_cert(ca.cert_pem)
    bogus = "".join(reversed(fingerprint))

    # We have to serve something:
    httpserver.expect_request("/").respond_with_data("OK")
    url = f"https://127.0.0.1:{httpserver.port}/"

    await http.request(
        "GET",
        url,
        verify=False,
        verify_fingerprint=fingerprint,
        session=aio_session,
    )

    with pytest.raises(aiohttp.ServerFingerprintMismatch):
        http.request(
            "GET",
            url,
            verify=False,
            verify_fingerprint=bogus,
            session=aio_session,
        )


def test_open_graphical_browser(monkeypatch: Any) -> None:
    import webbrowser

    # Just assert that this internal attribute still exists and behaves the way
    # expected
    assert webbrowser._tryorder is None  # type: ignore[attr-defined]

    monkeypatch.setattr("webbrowser._tryorder", [])

    with pytest.raises(RuntimeError) as excinfo:
        utils.open_graphical_browser("http://example.com")

    assert "No graphical browser found" in str(excinfo.value)
