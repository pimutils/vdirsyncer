import logging

import aiohttp
import click_log
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes

from vdirsyncer import http
from vdirsyncer import utils


@pytest.fixture(autouse=True)
def no_debug_output(request):
    logger = click_log.basic_config("vdirsyncer")
    logger.setLevel(logging.WARNING)


def test_get_storage_init_args():
    from vdirsyncer.storage.memory import MemoryStorage

    all, required = utils.get_storage_init_args(MemoryStorage)
    assert all == {"fileext", "collection", "read_only", "instance_name"}
    assert not required


@pytest.mark.asyncio
async def test_request_ssl():
    async with aiohttp.ClientSession() as session:
        with pytest.raises(aiohttp.ClientConnectorCertificateError) as excinfo:
            await http.request(
                "GET",
                "https://self-signed.badssl.com/",
                session=session,
            )
        assert "certificate verify failed" in str(excinfo.value)

        # XXX FIXME

        with pytest.raises(Exception):
            await http.request(
                "GET",
                "https://self-signed.badssl.com/",
                verify=False,
                session=session,
            )


def fingerprint_of_cert(cert, hash=hashes.SHA256) -> str:
    return x509.load_pem_x509_certificate(cert.bytes()).fingerprint(hash()).hex()


@pytest.mark.parametrize("hash_algorithm", [hashes.SHA256])
@pytest.mark.asyncio
async def test_request_ssl_leaf_fingerprint(
    httpserver,
    localhost_cert,
    hash_algorithm,
    aio_session,
):
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
async def test_request_ssl_ca_fingerprints(httpserver, ca, hash_algorithm, aio_session):
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


def test_open_graphical_browser(monkeypatch):
    import webbrowser

    # Just assert that this internal attribute still exists and behaves the way
    # expected
    assert webbrowser._tryorder is None

    monkeypatch.setattr("webbrowser._tryorder", [])

    with pytest.raises(RuntimeError) as excinfo:
        utils.open_graphical_browser("http://example.com")

    assert "No graphical browser found" in str(excinfo.value)
