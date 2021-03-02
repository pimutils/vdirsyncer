import logging
import sys

import click_log
import pytest
import requests

from vdirsyncer import http
from vdirsyncer import utils


@pytest.fixture(autouse=True)
def no_debug_output(request):
    logger = click_log.basic_config('vdirsyncer')
    logger.setLevel(logging.WARNING)


def test_get_storage_init_args():
    from vdirsyncer.storage.memory import MemoryStorage

    all, required = utils.get_storage_init_args(MemoryStorage)
    assert all == {'fileext', 'collection', 'read_only', 'instance_name'}
    assert not required


def test_request_ssl():
    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        http.request('GET', "https://self-signed.badssl.com/")
    assert 'certificate verify failed' in str(excinfo.value)

    http.request('GET', "https://self-signed.badssl.com/", verify=False)


def _fingerprints_broken():
    from pkg_resources import parse_version as ver
    broken_urllib3 = ver(requests.__version__) <= ver('2.5.1')
    return broken_urllib3


@pytest.mark.skipif(_fingerprints_broken(),
                    reason='https://github.com/shazow/urllib3/issues/529')
@pytest.mark.parametrize('fingerprint', [
    '94:FD:7A:CB:50:75:A4:69:82:0A:F8:23:DF:07:FC:69:3E:CD:90:CA',
    '19:90:F7:23:94:F2:EF:AB:2B:64:2D:57:3D:25:95:2D'
])
def test_request_ssl_fingerprints(httpsserver, fingerprint):
    httpsserver.serve_content('')  # we need to serve something

    http.request('GET', httpsserver.url, verify=False,
                 verify_fingerprint=fingerprint)
    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        http.request('GET', httpsserver.url,
                     verify_fingerprint=fingerprint)

    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        http.request('GET', httpsserver.url, verify=False,
                     verify_fingerprint=''.join(reversed(fingerprint)))
    assert 'Fingerprints did not match' in str(excinfo.value)


def test_open_graphical_browser(monkeypatch):
    import webbrowser
    # Just assert that this internal attribute still exists and behaves the way
    # expected
    if sys.version_info < (3, 7):
        iter(webbrowser._tryorder)
    else:
        assert webbrowser._tryorder is None

    monkeypatch.setattr('webbrowser._tryorder', [])

    with pytest.raises(RuntimeError) as excinfo:
        utils.open_graphical_browser('http://example.com')

    assert 'No graphical browser found' in str(excinfo.value)
