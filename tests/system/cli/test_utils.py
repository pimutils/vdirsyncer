from vdirsyncer import exceptions
from vdirsyncer.cli.utils import handle_cli_error


def test_handle_cli_error(capsys):
    try:
        raise exceptions.InvalidResponse('ayy lmao')
    except BaseException:
        handle_cli_error()

    out, err = capsys.readouterr()
    assert 'returned something vdirsyncer doesn\'t understand' in err
    assert 'ayy lmao' in err
