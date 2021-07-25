import subprocess

import aiostream
import pytest

from vdirsyncer.storage.filesystem import FilesystemStorage
from vdirsyncer.vobject import Item

from . import StorageTests


class TestFilesystemStorage(StorageTests):
    storage_class = FilesystemStorage

    @pytest.fixture
    def get_storage_args(self, tmpdir):
        async def inner(collection="test"):
            rv = {"path": str(tmpdir), "fileext": ".txt", "collection": collection}
            if collection is not None:
                rv = await self.storage_class.create_collection(**rv)
            return rv

        return inner

    def test_is_not_directory(self, tmpdir):
        with pytest.raises(OSError):
            f = tmpdir.join("hue")
            f.write("stub")
            self.storage_class(str(tmpdir) + "/hue", ".txt")

    @pytest.mark.asyncio
    async def test_broken_data(self, tmpdir):
        s = self.storage_class(str(tmpdir), ".txt")

        class BrokenItem:
            raw = "Ц, Ш, Л, ж, Д, З, Ю".encode()
            uid = "jeezus"
            ident = uid

        with pytest.raises(TypeError):
            await s.upload(BrokenItem)
        assert not tmpdir.listdir()

    @pytest.mark.asyncio
    async def test_ident_with_slash(self, tmpdir):
        s = self.storage_class(str(tmpdir), ".txt")
        await s.upload(Item("UID:a/b/c"))
        (item_file,) = tmpdir.listdir()
        assert "/" not in item_file.basename and item_file.isfile()

    @pytest.mark.asyncio
    async def test_ignore_tmp_files(self, tmpdir):
        """Test that files with .tmp suffix beside .ics files are ignored."""
        s = self.storage_class(str(tmpdir), ".ics")
        await s.upload(Item("UID:xyzxyz"))
        (item_file,) = tmpdir.listdir()
        item_file.copy(item_file.new(ext="tmp"))
        assert len(tmpdir.listdir()) == 2
        assert len(await aiostream.stream.list(s.list())) == 1

    @pytest.mark.asyncio
    async def test_ignore_tmp_files_empty_fileext(self, tmpdir):
        """Test that files with .tmp suffix are ignored with empty fileext."""
        s = self.storage_class(str(tmpdir), "")
        await s.upload(Item("UID:xyzxyz"))
        (item_file,) = tmpdir.listdir()
        item_file.copy(item_file.new(ext="tmp"))
        assert len(tmpdir.listdir()) == 2
        # assert False, tmpdir.listdir() # enable to see the created filename
        assert len(await aiostream.stream.list(s.list())) == 1

    @pytest.mark.asyncio
    async def test_ignore_files_typical_backup(self, tmpdir):
        """Test file-name ignorance with typical backup ending ~."""
        ignorext = "~"  # without dot

        storage = self.storage_class(str(tmpdir), "", fileignoreext=ignorext)
        await storage.upload(Item("UID:xyzxyz"))
        (item_file,) = tmpdir.listdir()
        item_file.copy(item_file.new(basename=item_file.basename + ignorext))

        assert len(tmpdir.listdir()) == 2
        assert len(await aiostream.stream.list(storage.list())) == 1

    @pytest.mark.asyncio
    async def test_too_long_uid(self, tmpdir):
        storage = self.storage_class(str(tmpdir), ".txt")
        item = Item("UID:" + "hue" * 600)

        href, etag = await storage.upload(item)
        assert item.uid not in href

    @pytest.mark.asyncio
    async def test_post_hook_inactive(self, tmpdir, monkeypatch):
        def check_call_mock(*args, **kwargs):
            raise AssertionError()

        monkeypatch.setattr(subprocess, "call", check_call_mock)

        s = self.storage_class(str(tmpdir), ".txt", post_hook=None)
        await s.upload(Item("UID:a/b/c"))

    @pytest.mark.asyncio
    async def test_post_hook_active(self, tmpdir, monkeypatch):
        calls = []
        exe = "foo"

        def check_call_mock(call, *args, **kwargs):
            calls.append(True)
            assert len(call) == 2
            assert call[0] == exe

        monkeypatch.setattr(subprocess, "call", check_call_mock)

        s = self.storage_class(str(tmpdir), ".txt", post_hook=exe)
        await s.upload(Item("UID:a/b/c"))
        assert calls

    @pytest.mark.asyncio
    async def test_ignore_git_dirs(self, tmpdir):
        tmpdir.mkdir(".git").mkdir("foo")
        tmpdir.mkdir("a")
        tmpdir.mkdir("b")

        expected = {"a", "b"}
        actual = {
            c["collection"] async for c in self.storage_class.discover(str(tmpdir))
        }
        assert actual == expected
