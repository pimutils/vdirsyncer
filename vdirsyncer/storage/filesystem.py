# -*- coding: utf-8 -*-

import errno
import os
import subprocess

from atomicwrites import atomic_write

from .base import Item, Storage
from .. import exceptions, log
from ..utils import checkdir, expand_path, generate_href, get_etag_from_file, \
    get_etag_from_fileobject
from ..utils.compat import text_type, to_native

logger = log.get(__name__)


class FilesystemStorage(Storage):

    '''
    Saves each item in its own file, given a directory.

    Can be used with `khal <http://lostpackets.de/khal/>`_. See :doc:`vdir` for
    a more formal description of the format.

    :param path: Absolute path to a vdir/collection. If this is used in
        combination with the ``collections`` parameter in a pair-section, this
        should point to a directory of vdirs instead.
    :param fileext: The file extension to use (e.g. ``.txt``). Contained in the
        href, so if you change the file extension after a sync, this will
        trigger a re-download of everything (but *should* not cause data-loss
        of any kind).
    :param encoding: File encoding for items, both content and filename.
    :param post_hook: A command to call for each item creation and
        modification. The command will be called with the path of the
        new/updated file.
    '''

    # This storage is not 100% threadsafe.However, it isn't really race-free
    # anyway when other applications are accessing the same storage.

    storage_name = 'filesystem'
    _repr_attributes = ('path',)

    def __init__(self, path, fileext, encoding='utf-8', post_hook=None,
                 **kwargs):
        super(FilesystemStorage, self).__init__(**kwargs)
        path = expand_path(to_native(path, encoding))
        checkdir(path, create=False)
        self.path = path
        self.encoding = encoding
        self.fileext = fileext
        self.post_hook = post_hook

    @classmethod
    def discover(cls, path, **kwargs):
        if kwargs.pop('collection', None) is not None:
            raise TypeError('collection argument must not be given.')
        path = expand_path(path)
        try:
            collections = os.listdir(path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        else:
            for collection in collections:
                collection_path = os.path.join(path, collection)
                if os.path.isdir(collection_path):
                    args = dict(collection=collection, path=collection_path,
                                **kwargs)
                    yield args

    @classmethod
    def create_collection(cls, collection, **kwargs):
        kwargs = dict(kwargs)
        encoding = kwargs.get('encoding', 'utf-8')
        path = to_native(kwargs['path'], encoding)

        if collection is not None:
            collection = to_native(collection, encoding)
            path = os.path.join(path, collection)

        checkdir(expand_path(path), create=True)

        kwargs['path'] = path
        kwargs['collection'] = collection
        return kwargs

    def _get_filepath(self, href):
        return os.path.join(self.path, to_native(href, self.encoding))

    def _get_href(self, ident):
        return generate_href(ident) + self.fileext

    def list(self):
        for fname in os.listdir(self.path):
            fpath = os.path.join(self.path, fname)
            if os.path.isfile(fpath) and fname.endswith(self.fileext):
                yield fname, get_etag_from_file(fpath)

    def get(self, href):
        fpath = self._get_filepath(href)
        try:
            with open(fpath, 'rb') as f:
                return (Item(f.read().decode(self.encoding)),
                        get_etag_from_file(fpath))
        except IOError as e:
            if e.errno == errno.ENOENT:
                raise exceptions.NotFoundError(href)
            else:
                raise

    def upload(self, item):
        if not isinstance(item.raw, text_type):
            raise TypeError('item.raw must be a unicode string.')

        try:
            href = self._get_href(item.ident)
            fpath, etag = self._upload_impl(item, href)
        except OSError as e:
            if e.errno in (
                errno.ENAMETOOLONG,  # Unix
                errno.ENOENT  # Windows
            ):
                logger.debug('UID as filename rejected, trying with random '
                             'one.')
                # random href instead of UID-based
                href = self._get_href(None)
                fpath, etag = self._upload_impl(item, href)
            else:
                raise

        if self.post_hook:
            self._run_post_hook(fpath)
        return href, etag

    def _upload_impl(self, item, href):
        fpath = self._get_filepath(href)
        try:
            with atomic_write(fpath, mode='wb', overwrite=False) as f:
                f.write(item.raw.encode(self.encoding))
                return fpath, get_etag_from_fileobject(f)
        except OSError as e:
            if e.errno == errno.EEXIST:
                raise exceptions.AlreadyExistingError(existing_href=href)
            else:
                raise

    def update(self, href, item, etag):
        if not isinstance(item.raw, text_type):
            raise TypeError('item.raw must be a unicode string.')

        fpath = self._get_filepath(href)
        try:
            actual_etag = get_etag_from_file(fpath)
        except OSError:
            raise exceptions.NotFoundError(item.uid)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        with atomic_write(fpath, mode='wb', overwrite=True) as f:
            f.write(item.raw.encode(self.encoding))
            etag = get_etag_from_fileobject(f)

        if self.post_hook:
            self._run_post_hook(fpath)
        return etag

    def delete(self, href, etag):
        fpath = self._get_filepath(href)
        try:
            actual_etag = get_etag_from_file(fpath)
        except OSError:
            raise exceptions.NotFoundError(href)

        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)
        os.remove(fpath)

    def _run_post_hook(self, fpath):
        logger.info('Calling post_hook={} with argument={}'.format(
            self.post_hook, fpath))
        try:
            subprocess.call([self.post_hook, fpath])
        except OSError as e:
            logger.warning('Error executing external hook: {}'.format(str(e)))

    def get_meta(self, key):
        fpath = os.path.join(self.path, key)
        try:
            with open(fpath, 'rb') as f:
                return f.read().decode(self.encoding) or None
        except IOError as e:
            if e.errno == errno.ENOENT:
                return None
            else:
                raise

    def set_meta(self, key, value):
        value = value or u''
        assert isinstance(value, text_type)
        fpath = os.path.join(self.path, key)
        with atomic_write(fpath, mode='wb', overwrite=True) as f:
            f.write(value.encode(self.encoding))
