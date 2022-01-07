import pytest
from aiohttp import BasicAuth
from aioresponses import CallbackResult
from aioresponses import aioresponses

from tests import normalize_item
from vdirsyncer.exceptions import UserError
from vdirsyncer.storage.http import HttpStorage
from vdirsyncer.storage.http import prepare_auth


@pytest.mark.asyncio
async def test_list(aio_connector):
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

    def callback(url, headers, **kwargs):
        assert headers["User-Agent"].startswith("vdirsyncer/")
        assert responses

        return CallbackResult(
            status=200,
            body=responses.pop().encode("utf-8"),
            headers={"Content-Type": "text/calendar; charset=iso-8859-1"},
        )

    with aioresponses() as m:
        m.get(collection_url, callback=callback, repeat=True)

        s = HttpStorage(url=collection_url, connector=aio_connector)

        found_items = {}

        async for href, etag in s.list():
            item, etag2 = await s.get(href)
            assert item.uid is not None
            assert etag2 == etag
            found_items[normalize_item(item)] = href

        expected = {
            normalize_item("BEGIN:VCALENDAR\n" + x + "\nEND:VCALENDAR") for x in items
        }

        assert set(found_items) == expected

        async for href, etag in s.list():
            item, etag2 = await s.get(href)
            assert item.uid is not None
            assert etag2 == etag
            assert found_items[normalize_item(item)] == href


def test_readonly_param(aio_connector):
    """The ``readonly`` param cannot be ``False``."""

    url = "http://example.com/"
    with pytest.raises(ValueError):
        HttpStorage(url=url, read_only=False, connector=aio_connector)

    a = HttpStorage(url=url, read_only=True, connector=aio_connector)
    b = HttpStorage(url=url, read_only=None, connector=aio_connector)

    assert a.read_only is b.read_only is True


def test_prepare_auth():
    assert prepare_auth(None, "", "") is None

    assert prepare_auth(None, "user", "pwd") == BasicAuth("user", "pwd")
    assert prepare_auth("basic", "user", "pwd") == BasicAuth("user", "pwd")

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
        prepare_auth("guess", "user", "pwd"),
        requests_toolbelt.auth.guess.GuessAuth,
    )

    monkeypatch.delattr(requests_toolbelt.auth.guess, "GuessAuth")

    with pytest.raises(UserError) as excinfo:
        prepare_auth("guess", "user", "pwd")

    assert "requests_toolbelt is too old" in str(excinfo.value).lower()


def test_verify_false_disallowed(aio_connector):
    with pytest.raises(ValueError) as excinfo:
        HttpStorage(url="http://example.com", verify=False, connector=aio_connector)

    assert "must be a path to a pem-file." in str(excinfo.value).lower()
