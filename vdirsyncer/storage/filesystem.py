import errno
import logging
import os
import subprocess

from atomicwrites import atomic_write

from .. import exceptions
from ..utils import checkdir
from ..utils import expand_path
from ..utils import generate_href
from ..utils import get_etag_from_file
from ..vobject import Item
from .base import normalize_meta_value
from .base import Storage

logger = logging.getLogger(__name__)


class FilesystemStorage(Storage):

    storage_name = 'filesystem'
    _repr_attributes = ('path',)

    def __init__(self, path, fileext, encoding='utf-8', post_hook=None,
                 **kwargs):
        super().__init__(**kwargs)
        path = expand_path(path)
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
                if not cls._validate_collection(collection_path):
                    continue
                args = dict(collection=collection, path=collection_path,
                            **kwargs)
                yield args

    @classmethod
    def _validate_collection(cls, path):
        if not os.path.isdir(path):
            return False
        if os.path.basename(path).startswith('.'):
            return False
        return True

    @classmethod
    def create_collection(cls, collection, **kwargs):
        kwargs = dict(kwargs)
        path = kwargs['path']

        if collection is not None:
            path = os.path.join(path, collection)

        checkdir(expand_path(path), create=True)

        kwargs['path'] = path
        kwargs['collection'] = collection
        return kwargs

    def _get_filepath(self, href):
        return os.path.join(self.path, href)

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
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise exceptions.NotFoundError(href)
            else:
                raise

    def upload(self, item):
        if not isinstance(item.raw, str):
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
                return fpath, get_etag_from_file(f)
        except OSError as e:
            if e.errno == errno.EEXIST:
                raise exceptions.AlreadyExistingError(existing_href=href)
            else:
                raise

    def update(self, href, item, etag):
        fpath = self._get_filepath(href)
        if not os.path.exists(fpath):
            raise exceptions.NotFoundError(item.uid)
        actual_etag = get_etag_from_file(fpath)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        if not isinstance(item.raw, str):
            raise TypeError('item.raw must be a unicode string.')

        with atomic_write(fpath, mode='wb', overwrite=True) as f:
            f.write(item.raw.encode(self.encoding))
            etag = get_etag_from_file(f)

        if self.post_hook:
            self._run_post_hook(fpath)
        return etag

    def delete(self, href, etag):
        fpath = self._get_filepath(href)
        if not os.path.isfile(fpath):
            raise exceptions.NotFoundError(href)
        actual_etag = get_etag_from_file(fpath)
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
                return normalize_meta_value(f.read().decode(self.encoding))
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    def set_meta(self, key, value):
        value = normalize_meta_value(value)

        fpath = os.path.join(self.path, key)
        if value is None:
            try:
                os.remove(fpath)
            except OSError:
                pass
            return

        with atomic_write(fpath, mode='wb', overwrite=True) as f:
            f.write(value.encode(self.encoding))
