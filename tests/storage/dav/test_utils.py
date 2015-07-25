# -*- coding: utf-8 -*-

from vdirsyncer.storage.dav import _parse_xml


def test_broken_xml(capsys):
    rv = _parse_xml(b'<h1>\x10haha</h1>')
    assert rv.text == 'haha'
    warnings = capsys.readouterr()[1]
    assert 'partially invalid xml' in warnings.lower()
