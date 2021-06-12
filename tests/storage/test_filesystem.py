import subprocess

import pytest

from . import StorageTests
from vdirsyncer.storage.filesystem import FilesystemStorage
from vdirsyncer.vobject import Item


class TestFilesystemStorage(StorageTests):
    storage_class = FilesystemStorage

    @pytest.fixture
    def get_storage_args(self, tmpdir):
        def inner(collection="test"):
            rv = {"path": str(tmpdir), "fileext": ".txt", "collection": collection}
            if collection is not None:
                rv = self.storage_class.create_collection(**rv)
            return rv

        return inner

    def test_is_not_directory(self, tmpdir):
        with pytest.raises(OSError):
            f = tmpdir.join("hue")
            f.write("stub")
            self.storage_class(str(tmpdir) + "/hue", ".txt")

    def test_broken_data(self, tmpdir):
        s = self.storage_class(str(tmpdir), ".txt")

        class BrokenItem:
            raw = "Ц, Ш, Л, ж, Д, З, Ю".encode()
            uid = "jeezus"
            ident = uid

        with pytest.raises(TypeError):
            s.upload(BrokenItem)
        assert not tmpdir.listdir()

    def test_ident_with_slash(self, tmpdir):
        s = self.storage_class(str(tmpdir), ".txt")
        s.upload(Item("UID:a/b/c"))
        (item_file,) = tmpdir.listdir()
        assert "/" not in item_file.basename and item_file.isfile()

    def test_ignore_tmp_files(self, tmpdir):
        """Test that files with .tmp suffix beside .ics files are ignored."""
        s = self.storage_class(str(tmpdir), ".ics")
        s.upload(Item("UID:xyzxyz"))
        (item_file,) = tmpdir.listdir()
        item_file.copy(item_file.new(ext="tmp"))
        assert len(tmpdir.listdir()) == 2
        assert len(list(s.list())) == 1

    def test_ignore_tmp_files_empty_fileext(self, tmpdir):
        """Test that files with .tmp suffix are ignored with empty fileext."""
        s = self.storage_class(str(tmpdir), "")
        s.upload(Item("UID:xyzxyz"))
        (item_file,) = tmpdir.listdir()
        item_file.copy(item_file.new(ext="tmp"))
        assert len(tmpdir.listdir()) == 2
        # assert False, tmpdir.listdir() # enable to see the created filename
        assert len(list(s.list())) == 1

    def test_ignore_files_typical_backup(self, tmpdir):
        """Test file-name ignorance with typical backup ending ~."""
        ignorext = "~"  # without dot

        storage = self.storage_class(str(tmpdir), "", fileignoreext=ignorext)
        storage.upload(Item("UID:xyzxyz"))
        (item_file,) = tmpdir.listdir()
        item_file.copy(item_file.new(basename=item_file.basename + ignorext))

        assert len(tmpdir.listdir()) == 2
        assert len(list(storage.list())) == 1

    def test_too_long_uid(self, tmpdir):
        storage = self.storage_class(str(tmpdir), ".txt")
        item = Item("UID:" + "hue" * 600)

        href, etag = storage.upload(item)
        assert item.uid not in href

    def test_post_hook_inactive(self, tmpdir, monkeypatch):
        def check_call_mock(*args, **kwargs):
            raise AssertionError()

        monkeypatch.setattr(subprocess, "call", check_call_mock)

        s = self.storage_class(str(tmpdir), ".txt", post_hook=None)
        s.upload(Item("UID:a/b/c"))

    def test_post_hook_active(self, tmpdir, monkeypatch):

        calls = []
        exe = "foo"

        def check_call_mock(call, *args, **kwargs):
            calls.append(True)
            assert len(call) == 2
            assert call[0] == exe

        monkeypatch.setattr(subprocess, "call", check_call_mock)

        s = self.storage_class(str(tmpdir), ".txt", post_hook=exe)
        s.upload(Item("UID:a/b/c"))
        assert calls

    def test_ignore_git_dirs(self, tmpdir):
        tmpdir.mkdir(".git").mkdir("foo")
        tmpdir.mkdir("a")
        tmpdir.mkdir("b")
        assert {c["collection"] for c in self.storage_class.discover(str(tmpdir))} == {
            "a",
            "b",
        }
