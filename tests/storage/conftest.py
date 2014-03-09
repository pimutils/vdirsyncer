import pytest
import tempfile
import shutil


@pytest.fixture
def class_tmpdir(request):
    request.cls.tmpdir = x = tempfile.mkdtemp()
    request.addfinalizer(lambda: shutil.rmtree(x))
