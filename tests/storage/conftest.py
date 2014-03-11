import pytest


@pytest.fixture
def class_tmpdir(request, tmpdir):
    request.instance.tmpdir = str(tmpdir)
