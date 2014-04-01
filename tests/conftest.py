# -*- coding: utf-8 -*-
'''
    tests.conftest
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import pytest

@pytest.fixture(autouse=True)
def requests_mock(monkeypatch):
    '''It is easier than setting up the logging module!'''
    import requests.sessions
    old_func = requests.sessions.Session.request
    def mock_request(self, method, url, data=None, headers=None, **kw):
        print(method)
        print(url)
        print(data)
        print(headers)
        r = old_func(self, method, url, data=data, headers=headers, **kw)
        print(r.status_code)
        print(r.text)
        return r
    monkeypatch.setattr('requests.sessions.Session.request', mock_request)
