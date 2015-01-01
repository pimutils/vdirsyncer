
# -*- coding: utf-8 -*-
'''
    tests.storage.filesystem
    ~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import os

import pytest

from vdirsyncer.storage.filesystem import FilesystemStorage
from vdirsyncer.utils.vobject import Item

from . import StorageTests


class TestFilesystemStorage(StorageTests):
    storage_class = FilesystemStorage

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self.tmpdir = str(tmpdir)

    @pytest.fixture
    def get_storage_args(self):
        def inner(collection=None):
            path = self.tmpdir
            if collection is not None:
                os.makedirs(os.path.join(path, collection))
                path = os.path.join(path, collection)
            return {'path': path, 'fileext': '.txt', 'collection': collection}
        return inner

    def test_is_not_directory(self, tmpdir):
        with pytest.raises(IOError):
            f = tmpdir.join('hue')
            f.write('stub')
            self.storage_class(str(tmpdir) + '/hue', '.txt')

    def test_broken_data(self, tmpdir):
        s = self.storage_class(str(tmpdir), '.txt')

        class BrokenItem(object):
            raw = u'Ц, Ш, Л, ж, Д, З, Ю'.encode('utf-8')
            uid = 'jeezus'
            ident = uid
        with pytest.raises(TypeError):
            s.upload(BrokenItem)
        assert not tmpdir.listdir()

    def test_ident_with_slash(self, tmpdir):
        s = self.storage_class(str(tmpdir), '.txt')
        s.upload(Item(u'UID:a/b/c'))
        item_file, = tmpdir.listdir()
        assert str(item_file).endswith('a_b_c.txt')
