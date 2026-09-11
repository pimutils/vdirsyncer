from __future__ import annotations

import pytest

from vdirsyncer import exceptions
from vdirsyncer.storage.google import GoogleCalendarStorage
from vdirsyncer.vobject import Item


@pytest.mark.parametrize(
    ("mode", "expected", "unexpected"),
    [
        ("preserve", "ORGANIZER:mailto:owner@example.com", "METHOD:"),
        ("passive", "ORGANIZER;SCHEDULE-AGENT=NONE:", "METHOD:"),
        ("standalone", "SUMMARY:Personal copy", "ORGANIZER"),
    ],
)
def test_google_calendar_scheduling_mode(mode, expected, unexpected):
    storage = object.__new__(GoogleCalendarStorage)
    storage.scheduling_mode = mode
    item = Item(
        "BEGIN:VCALENDAR\r\n"
        "METHOD:PUBLISH\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:one\r\n"
        "SUMMARY:Personal copy\r\n"
        "ORGANIZER:mailto:owner@example.com\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    actual = storage.prepare_item(item)

    assert expected in actual.raw
    assert unexpected not in actual.raw


def test_google_calendar_rejects_invalid_scheduling_mode():
    with pytest.raises(exceptions.UserError, match="scheduling_mode must be one of"):
        GoogleCalendarStorage(
            token_file="token",
            client_id="client",
            client_secret="secret",
            collection="calendar",
            scheduling_mode="invite-everyone",
        )
