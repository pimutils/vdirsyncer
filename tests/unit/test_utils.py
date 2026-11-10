from __future__ import annotations

import os

from vdirsyncer import utils


def test_checkfile_bare_filename_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "test.ics"
    target.write_bytes(b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
    utils.checkfile("test.ics")


def test_checkfile_bare_filename_create(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    utils.checkfile("new.ics", create=True)
    assert os.path.isfile("new.ics")
