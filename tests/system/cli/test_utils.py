from vdirsyncer import exceptions
from vdirsyncer.cli.utils import handle_cli_error, \
    storage_instance_from_config, storage_names


def test_handle_cli_error(capsys):
    try:
        raise exceptions.InvalidResponse('ayy lmao')
    except BaseException:
        handle_cli_error()

    out, err = capsys.readouterr()
    assert 'returned something vdirsyncer doesn\'t understand' in err
    assert 'ayy lmao' in err


def test_storage_instance_from_config(monkeypatch):
    def lol(**kw):
        assert kw == {'foo': 'bar', 'baz': 1}
        return 'OK'

    monkeypatch.setitem(storage_names._storages, 'lol', lol)
    config = {'type': 'lol', 'foo': 'bar', 'baz': 1}
    assert storage_instance_from_config(config) == 'OK'
