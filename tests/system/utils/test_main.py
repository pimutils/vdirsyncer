import logging
import sys

import click_log
import pytest
import requests
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


def test_request_ssl():
    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        http.request("GET", "https://self-signed.badssl.com/")
    assert "certificate verify failed" in str(excinfo.value)

    http.request("GET", "https://self-signed.badssl.com/", verify=False)


def _fingerprints_broken():
    from pkg_resources import parse_version as ver

    broken_urllib3 = ver(requests.__version__) <= ver("2.5.1")
    return broken_urllib3


def fingerprint_of_cert(cert, hash=hashes.SHA256):
    return x509.load_pem_x509_certificate(cert.bytes()).fingerprint(hash()).hex()


@pytest.mark.skipif(
    _fingerprints_broken(), reason="https://github.com/shazow/urllib3/issues/529"
)
@pytest.mark.parametrize("hash_algorithm", [hashes.MD5, hashes.SHA256])
def test_request_ssl_leaf_fingerprint(httpserver, localhost_cert, hash_algorithm):
    fingerprint = fingerprint_of_cert(localhost_cert.cert_chain_pems[0], hash_algorithm)

    # We have to serve something:
    httpserver.expect_request("/").respond_with_data("OK")
    url = f"https://{httpserver.host}:{httpserver.port}/"

    http.request("GET", url, verify=False, verify_fingerprint=fingerprint)
    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        http.request("GET", url, verify_fingerprint=fingerprint)

    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        http.request(
            "GET",
            url,
            verify=False,
            verify_fingerprint="".join(reversed(fingerprint)),
        )
    assert "Fingerprints did not match" in str(excinfo.value)


@pytest.mark.skipif(
    _fingerprints_broken(), reason="https://github.com/shazow/urllib3/issues/529"
)
@pytest.mark.xfail(reason="Not implemented")
@pytest.mark.parametrize("hash_algorithm", [hashes.MD5, hashes.SHA256])
def test_request_ssl_ca_fingerprint(httpserver, ca, hash_algorithm):
    fingerprint = fingerprint_of_cert(ca.cert_pem)

    # We have to serve something:
    httpserver.expect_request("/").respond_with_data("OK")
    url = f"https://{httpserver.host}:{httpserver.port}/"

    http.request("GET", url, verify=False, verify_fingerprint=fingerprint)
    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        http.request("GET", url, verify_fingerprint=fingerprint)

    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        http.request(
            "GET",
            url,
            verify=False,
            verify_fingerprint="".join(reversed(fingerprint)),
        )
    assert "Fingerprints did not match" in str(excinfo.value)


def test_open_graphical_browser(monkeypatch):
    import webbrowser

    # Just assert that this internal attribute still exists and behaves the way
    # expected
    if sys.version_info < (3, 7):
        iter(webbrowser._tryorder)
    else:
        assert webbrowser._tryorder is None

    monkeypatch.setattr("webbrowser._tryorder", [])

    with pytest.raises(RuntimeError) as excinfo:
        utils.open_graphical_browser("http://example.com")

    assert "No graphical browser found" in str(excinfo.value)
