import pytest
from requests import Response

from tests import normalize_item
from vdirsyncer.exceptions import UserError
from vdirsyncer.storage.http import HttpStorage
from vdirsyncer.storage.http import prepare_auth


def test_list(monkeypatch):
    collection_url = "http://127.0.0.1/calendar/collection.ics"

    items = [
        (
            "BEGIN:VEVENT\n"
            "SUMMARY:Eine Kurzinfo\n"
            "DESCRIPTION:Beschreibung des Termines\n"
            "END:VEVENT"
        ),
        (
            "BEGIN:VEVENT\n"
            "SUMMARY:Eine zweite Küèrzinfo\n"
            "DESCRIPTION:Beschreibung des anderen Termines\n"
            "BEGIN:VALARM\n"
            "ACTION:AUDIO\n"
            "TRIGGER:19980403T120000\n"
            "ATTACH;FMTTYPE=audio/basic:http://host.com/pub/ssbanner.aud\n"
            "REPEAT:4\n"
            "DURATION:PT1H\n"
            "END:VALARM\n"
            "END:VEVENT"
        ),
    ]

    responses = ["\n".join(["BEGIN:VCALENDAR"] + items + ["END:VCALENDAR"])] * 2

    def get(self, method, url, *a, **kw):
        assert method == "GET"
        assert url == collection_url
        r = Response()
        r.status_code = 200
        assert responses
        r._content = responses.pop().encode("utf-8")
        r.headers["Content-Type"] = "text/calendar"
        r.encoding = "ISO-8859-1"
        return r

    monkeypatch.setattr("requests.sessions.Session.request", get)

    s = HttpStorage(url=collection_url)

    found_items = {}

    for href, etag in s.list():
        item, etag2 = s.get(href)
        assert item.uid is not None
        assert etag2 == etag
        found_items[normalize_item(item)] = href

    expected = {
        normalize_item("BEGIN:VCALENDAR\n" + x + "\nEND:VCALENDAR") for x in items
    }

    assert set(found_items) == expected

    for href, etag in s.list():
        item, etag2 = s.get(href)
        assert item.uid is not None
        assert etag2 == etag
        assert found_items[normalize_item(item)] == href


def test_readonly_param():
    url = "http://example.com/"
    with pytest.raises(ValueError):
        HttpStorage(url=url, read_only=False)

    a = HttpStorage(url=url, read_only=True).read_only
    b = HttpStorage(url=url, read_only=None).read_only
    assert a is b is True


def test_prepare_auth():
    assert prepare_auth(None, "", "") is None

    assert prepare_auth(None, "user", "pwd") == ("user", "pwd")
    assert prepare_auth("basic", "user", "pwd") == ("user", "pwd")

    with pytest.raises(ValueError) as excinfo:
        assert prepare_auth("basic", "", "pwd")
    assert "you need to specify username and password" in str(excinfo.value).lower()

    from requests.auth import HTTPDigestAuth

    assert isinstance(prepare_auth("digest", "user", "pwd"), HTTPDigestAuth)

    with pytest.raises(ValueError) as excinfo:
        prepare_auth("ladida", "user", "pwd")

    assert "unknown authentication method" in str(excinfo.value).lower()


def test_prepare_auth_guess(monkeypatch):
    import requests_toolbelt.auth.guess

    assert isinstance(
        prepare_auth("guess", "user", "pwd"), requests_toolbelt.auth.guess.GuessAuth
    )

    monkeypatch.delattr(requests_toolbelt.auth.guess, "GuessAuth")

    with pytest.raises(UserError) as excinfo:
        prepare_auth("guess", "user", "pwd")

    assert "requests_toolbelt is too old" in str(excinfo.value).lower()


def test_verify_false_disallowed():
    with pytest.raises(ValueError) as excinfo:
        HttpStorage(url="http://example.com", verify=False)

    assert "forbidden" in str(excinfo.value).lower()
    assert "consider setting verify_fingerprint" in str(excinfo.value).lower()
