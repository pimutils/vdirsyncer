import vdirsyncer.log
vdirsyncer.log.set_level(vdirsyncer.log.logging.DEBUG)


def normalize_item(item):
    # - X-RADICALE-NAME is used by radicale, because hrefs don't really exist
    #   in their filesystem backend
    # - PRODID is changed by radicale for some reason after upload, but nobody
    #   cares about that anyway
    rv = set()
    for line in item.raw.splitlines():
        line = line.strip()
        line = line.strip().split(u':', 1)
        if line[0] in ('X-RADICALE-NAME', 'PRODID', 'REV'):
            continue
        rv.add(u':'.join(line))
    return rv


def assert_item_equals(a, b):
    assert normalize_item(a) == normalize_item(b)


def log_request(method, url, data, headers):
    print(method)
    print(url)
    print(data)
    print(headers)


def log_response(r):
    print(r.status_code)
    print(r.text)


def requests_mock(monkeypatch):
    '''It is easier than setting up the logging module!'''
    import requests.sessions
    old_func = requests.sessions.Session.request
    def mock_request(self, method, url, data=None, headers=None, **kw):
        log_request(method, url, data, headers)
        r = old_func(self, method, url, data=data, headers=headers, **kw)
        log_response(r)
        return r
    monkeypatch.setattr('requests.sessions.Session.request', mock_request)
