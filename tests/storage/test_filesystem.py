from __future__ import annotations

import subprocess
from typing import Any

import aiostream
import pytest

from vdirsyncer.storage.filesystem import FilesystemStorage
from vdirsyncer.vobject import Item

from . import StorageTests


class TestFilesystemStorage(StorageTests):
    storage_class = FilesystemStorage

    @pytest.fixture
    def get_storage_args(self, tmpdir: Any) -> Any:
        async def inner(collection: Any = "test") -> dict[str, Any]:
            rv = {"path": str(tmpdir), "fileext": ".txt", "collection": collection}
            if collection is not None:
                rv = await self.storage_class.create_collection(**rv)
            return rv

        return inner

    def test_is_not_directory(self, tmpdir: Any) -> None:
        with pytest.raises(OSError):
            f = tmpdir.join("hue")
            f.write("stub")
            self.storage_class(str(tmpdir) + "/hue", ".txt")

    @pytest.mark.asyncio
    async def test_broken_data(self, tmpdir: Any) -> None:
        s = self.storage_class(str(tmpdir), ".txt")

        class BrokenItem:
            raw = "Ц, Ш, Л, ж, Д, З, Ю".encode()
            uid = "jeezus"
            ident = uid

        with pytest.raises(TypeError):
            await s.upload(BrokenItem())  # type: ignore[arg-type]
        assert not tmpdir.listdir()

    @pytest.mark.asyncio
    async def test_ident_with_slash(self, tmpdir: Any) -> None:
        s = self.storage_class(str(tmpdir), ".txt")
        await s.upload(Item("UID:a/b/c"))
        (item_file,) = tmpdir.listdir()
        assert "/" not in item_file.basename
        assert item_file.isfile()

    @pytest.mark.asyncio
    async def test_ignore_tmp_files(self, tmpdir: Any) -> None:
        """Test that files with .tmp suffix beside .ics files are ignored."""
        s = self.storage_class(str(tmpdir), ".ics")
        await s.upload(Item("UID:xyzxyz"))
        (item_file,) = tmpdir.listdir()
        item_file.copy(item_file.new(ext="tmp"))
        assert len(tmpdir.listdir()) == 2
        assert len(await aiostream.stream.list(s.list())) == 1

    @pytest.mark.asyncio
    async def test_ignore_tmp_files_empty_fileext(self, tmpdir: Any) -> None:
        """Test that files with .tmp suffix are ignored with empty fileext."""
        s = self.storage_class(str(tmpdir), "")
        await s.upload(Item("UID:xyzxyz"))
        (item_file,) = tmpdir.listdir()
        item_file.copy(item_file.new(ext="tmp"))
        assert len(tmpdir.listdir()) == 2
        # assert False, tmpdir.listdir() # enable to see the created filename
        assert len(await aiostream.stream.list(s.list())) == 1

    @pytest.mark.asyncio
    async def test_ignore_files_typical_backup(self, tmpdir: Any) -> None:
        """Test file-name ignorance with typical backup ending ~."""
        ignorext = "~"  # without dot

        storage = self.storage_class(str(tmpdir), "", fileignoreext=ignorext)
        await storage.upload(Item("UID:xyzxyz"))
        (item_file,) = tmpdir.listdir()
        item_file.copy(item_file.new(basename=item_file.basename + ignorext))

        assert len(tmpdir.listdir()) == 2
        assert len(await aiostream.stream.list(storage.list())) == 1

    @pytest.mark.asyncio
    async def test_too_long_uid(self, tmpdir: Any) -> None:
        storage = self.storage_class(str(tmpdir), ".txt")
        item = Item("UID:" + "hue" * 600)

        href, _etag = await storage.upload(item)
        assert item.uid is not None
        assert item.uid not in href

    @pytest.mark.asyncio
    async def test_post_hook_inactive(self, tmpdir: Any, monkeypatch: Any) -> None:
        def check_call_mock(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError

        monkeypatch.setattr(subprocess, "call", check_call_mock)

        s = self.storage_class(str(tmpdir), ".txt", post_hook=None)
        await s.upload(Item("UID:a/b/c"))

    @pytest.mark.asyncio
    async def test_post_hook_active(self, tmpdir: Any, monkeypatch: Any) -> None:
        calls = []
        exe = "foo"

        def check_call_mock(call: Any, *args: Any, **kwargs: Any) -> Any:
            calls.append(True)
            assert len(call) == 2
            assert call[0] == exe

        monkeypatch.setattr(subprocess, "call", check_call_mock)

        s = self.storage_class(str(tmpdir), ".txt", post_hook=exe)
        await s.upload(Item("UID:a/b/c"))
        assert calls

    @pytest.mark.asyncio
    async def test_ignore_git_dirs(self, tmpdir: Any) -> None:
        tmpdir.mkdir(".git").mkdir("foo")
        tmpdir.mkdir("a")
        tmpdir.mkdir("b")

        expected = {"a", "b"}
        actual = {
            c["collection"] async for c in self.storage_class.discover(path=str(tmpdir))
        }
        assert actual == expected
