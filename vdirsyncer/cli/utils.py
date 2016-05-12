# -*- coding: utf-8 -*-

import contextlib
import errno
import hashlib
import importlib
import itertools
import json
import os
import sys

from atomicwrites import atomic_write

import click

import click_threading

from . import cli_logger
from .. import BUGTRACKER_HOME, DOCS_HOME, exceptions
from ..sync import IdentConflict, StorageEmpty, SyncConflict
from ..utils import expand_path, get_storage_init_args
from ..utils.compat import to_native

try:
    import Queue as queue
except ImportError:
    import queue


STATUS_PERMISSIONS = 0o600
STATUS_DIR_PERMISSIONS = 0o700

# Increase whenever upgrade potentially breaks discovery cache and collections
# should be re-discovered
DISCOVERY_CACHE_VERSION = 1


class _StorageIndex(object):
    def __init__(self):
        self._storages = dict(
            caldav='vdirsyncer.storage.dav.CaldavStorage',
            carddav='vdirsyncer.storage.dav.CarddavStorage',
            filesystem='vdirsyncer.storage.filesystem.FilesystemStorage',
            http='vdirsyncer.storage.http.HttpStorage',
            singlefile='vdirsyncer.storage.singlefile.SingleFileStorage',
            remotestorage_contacts=(
                'vdirsyncer.storage.remotestorage.RemoteStorageContacts'),
            remotestorage_calendars=(
                'vdirsyncer.storage.remotestorage.RemoteStorageCalendars'),
            google_calendar='vdirsyncer.storage.google.GoogleCalendarStorage',
            google_contacts='vdirsyncer.storage.google.GoogleContactsStorage'
        )

    def __getitem__(self, name):
        item = self._storages[name]
        if not isinstance(item, str):
            return item

        modname, clsname = item.rsplit('.', 1)
        mod = importlib.import_module(modname)
        self._storages[name] = rv = getattr(mod, clsname)
        assert rv.storage_name == name
        return rv


storage_names = _StorageIndex()
del _StorageIndex


class JobFailed(RuntimeError):
    pass


# TODO: Making this a decorator would be nice
def handle_cli_error(status_name=None):
    '''
    Print a useful error message for the current exception.

    This is supposed to catch all exceptions, and should never raise any
    exceptions itself.
    '''

    try:
        raise
    except exceptions.UserError as e:
        cli_logger.critical(e)
    except StorageEmpty as e:
        cli_logger.error(
            '{status_name}: Storage "{name}" was completely emptied. If you '
            'want to delete ALL entries on BOTH sides, then use '
            '`vdirsyncer sync --force-delete {status_name}`. '
            'Otherwise delete the files for {status_name} in your status '
            'directory.'.format(
                name=e.empty_storage.instance_name,
                status_name=status_name
            )
        )
    except SyncConflict as e:
        cli_logger.error(
            '{status_name}: One item changed on both sides. Resolve this '
            'conflict manually, or by setting the `conflict_resolution` '
            'parameter in your config file.\n'
            'See also {docs}/config.html#pair-section\n'
            'Item ID: {e.ident}\n'
            'Item href on side A: {e.href_a}\n'
            'Item href on side B: {e.href_b}\n'
            .format(status_name=status_name, e=e, docs=DOCS_HOME)
        )
    except IdentConflict as e:
        cli_logger.error(
            '{status_name}: Storage "{storage.instance_name}" contains '
            'multiple items with the same UID or even content. Vdirsyncer '
            'will now abort the synchronization of this collection, because '
            'the fix for this is not clear; It could be the result of a badly '
            'behaving server. You can try running:\n\n'
            '    vdirsyncer repair {storage.instance_name}\n\n'
            'But make sure to have a backup of your data in some form. The '
            'offending hrefs are:\n\n{href_list}\n'
            .format(status_name=status_name,
                    storage=e.storage,
                    href_list='\n'.join(map(repr, e.hrefs)))
        )
    except (click.Abort, KeyboardInterrupt, JobFailed):
        pass
    except exceptions.PairNotFound as e:
        cli_logger.error(
            'Pair {pair_name} does not exist. Please check your '
            'configuration file and make sure you\'ve typed the pair name '
            'correctly'.format(pair_name=e.pair_name)
        )
    except exceptions.InvalidResponse as e:
        cli_logger.error(
            'The server returned something vdirsyncer doesn\'t understand. '
            'Error message: {!r}\n'
            'While this is most likely a serverside problem, the vdirsyncer '
            'devs are generally interested in such bugs. Please report it in '
            'the issue tracker at {}'
            .format(e, BUGTRACKER_HOME)
        )
    except Exception as e:
        if status_name:
            msg = 'Unhandled exception occured for {}.'.format(
                coerce_native(status_name))
        else:
            msg = 'Unhandled exception occured.'

        cli_logger.exception(msg)


def get_status_name(pair, collection):
    if collection is None:
        return pair
    return pair + '/' + collection


def _get_collections_cache_key(pair):
    m = hashlib.sha256()
    j = json.dumps([
        DISCOVERY_CACHE_VERSION,
        pair.options.get('collections', None),
        pair.config_a,
        pair.config_b,
    ], sort_keys=True)
    m.update(j.encode('utf-8'))
    return m.hexdigest()


def collections_for_pair(status_path, pair, from_cache=True,
                         list_collections=False):
    '''Determine all configured collections for a given pair. Takes care of
    shortcut expansion and result caching.

    :param status_path: The path to the status directory.
    :param from_cache: Whether to load from cache (aborting on cache miss) or
        discover and save to cache.

    :returns: iterable of (collection, (a_args, b_args))
    '''
    cache_key = _get_collections_cache_key(pair)
    if from_cache:
        rv = load_status(status_path, pair.name, data_type='collections')
        if rv and rv.get('cache_key', None) == cache_key:
            return list(_expand_collections_cache(
                rv['collections'], pair.config_a, pair.config_b
            ))
        elif rv:
            raise exceptions.UserError('Detected change in config file, '
                                       'please run `vdirsyncer discover {}`.'
                                       .format(pair.name))
        else:
            raise exceptions.UserError('Please run `vdirsyncer discover {}` '
                                       ' before synchronization.'
                                       .format(pair.name))

    cli_logger.info('Discovering collections for pair {}'
                    .format(pair.name))

    # We have to use a list here because the special None/null value would get
    # mangled to string (because JSON objects always have string keys).
    rv = list(_collections_for_pair_impl(status_path, pair,
                                         list_collections=list_collections))

    save_status(status_path, pair.name, data_type='collections',
                data={
                    'collections': list(
                        _compress_collections_cache(rv, pair.config_a,
                                                    pair.config_b)
                    ),
                    'cache_key': cache_key
                })
    return rv


def _compress_collections_cache(collections, config_a, config_b):
    def deduplicate(x, y):
        rv = {}
        for key, value in x.items():
            if key not in y or y[key] != value:
                rv[key] = value

        return rv

    for name, (a, b) in collections:
        yield name, (deduplicate(a, config_a), deduplicate(b, config_b))


def _expand_collections_cache(collections, config_a, config_b):
    for name, (a_delta, b_delta) in collections:
        a = dict(config_a)
        a.update(a_delta)

        b = dict(config_b)
        b.update(b_delta)

        yield name, (a, b)


def _discover_from_config(config):
    storage_type = config['type']
    cls, config = storage_class_from_config(config)

    try:
        try:
            discovered = list(cls.discover(**config))
        except NotImplementedError:
            raise exceptions.UserError(
                'The storage {} (type {}) doesn\'t support collection '
                'discovery. You can only use `collections = null` with it.'
                .format(config.get('instance_name', '???'), storage_type)
            )
    except Exception:
        return handle_storage_init_error(cls, config)
    else:
        rv = {}
        for args in discovered:
            args['type'] = storage_type
            rv[args['collection']] = args
        return rv


def _handle_collection_not_found(config, collection, e=None):
    storage_name = config.get('instance_name', None)

    cli_logger.error('{}No collection {} found for storage {}.'
                     .format('{}\n'.format(e) if e else '',
                             coerce_native(collection), storage_name))

    if click.confirm('Should vdirsyncer attempt to create it?'):
        storage_type = config['type']
        cls, config = storage_class_from_config(config)
        config['collection'] = collection
        try:
            args = cls.create_collection(**config)
            args['type'] = storage_type
            return args
        except NotImplementedError as e:
            cli_logger.error(e)

    raise exceptions.UserError(
        'Unable to find or create collection "{collection}" for '
        'storage "{storage}". Please create the collection '
        'yourself.'.format(collection=collection,
                           storage=storage_name))


def _print_collections(base_config, discovered):
    instance_name = base_config['instance_name']
    cli_logger.info('{}:'.format(coerce_native(instance_name)))
    for args in discovered.values():
        args['instance_name'] = instance_name
        try:
            storage = storage_instance_from_config(args)
            displayname = storage.get_meta('displayname')
        except Exception:
            displayname = u''

        cli_logger.info('  - {}{}'.format(
            storage.collection,
            ' ("{}")'.format(coerce_native(displayname))
            if displayname and displayname != storage.collection
            else ''
        ))


def _collections_for_pair_impl(status_path, pair, list_collections=False):
    handled_collections = set()

    shortcuts = pair.options['collections']
    if shortcuts is None:
        yield None, (pair.config_a, pair.config_b)
    else:
        a_discovered = _discover_from_config(pair.config_a)
        b_discovered = _discover_from_config(pair.config_b)

        if list_collections:
            _print_collections(pair.config_a, a_discovered)
            _print_collections(pair.config_b, b_discovered)

        for shortcut in shortcuts:
            if shortcut == 'from a':
                collections = a_discovered
            elif shortcut == 'from b':
                collections = b_discovered
            else:
                collections = [shortcut]

            for collection in collections:
                if isinstance(collection, list):
                    try:
                        collection, collection_a, collection_b = collection
                    except ValueError:
                        raise exceptions.UserError(
                            'Expected string or list of length 3, '
                            '{} found instead.'
                            .format(collection))
                else:
                    collection_a = collection_b = collection

                if collection in handled_collections:
                    continue
                handled_collections.add(collection)

                try:
                    a_args = a_discovered[collection_a]
                except KeyError:
                    a_args = _handle_collection_not_found(pair.config_a,
                                                          collection_a)

                try:
                    b_args = b_discovered[collection_b]
                except KeyError:
                    b_args = _handle_collection_not_found(pair.config_b,
                                                          collection_b)

                yield collection, (a_args, b_args)


def load_status(base_path, pair, collection=None, data_type=None):
    assert data_type is not None
    status_name = get_status_name(pair, collection)
    path = expand_path(os.path.join(base_path, status_name))
    if os.path.isfile(path) and data_type == 'items':
        new_path = path + '.items'
        cli_logger.warning('Migrating statuses: Renaming {} to {}'
                           .format(path, new_path))
        os.rename(path, new_path)

    path += '.' + data_type
    if not os.path.exists(path):
        return None

    assert_permissions(path, STATUS_PERMISSIONS)

    with open(path) as f:
        try:
            return dict(json.load(f))
        except ValueError:
            pass

    return {}


def save_status(base_path, pair, collection=None, data_type=None, data=None):
    assert data_type is not None
    assert data is not None
    status_name = get_status_name(pair, collection)
    path = expand_path(os.path.join(base_path, status_name)) + '.' + data_type
    dirname = os.path.dirname(path)

    try:
        os.makedirs(dirname, STATUS_DIR_PERMISSIONS)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    with atomic_write(path, mode='w', overwrite=True) as f:
        json.dump(data, f)

    os.chmod(path, STATUS_PERMISSIONS)


def storage_class_from_config(config):
    config = dict(config)
    storage_name = config.pop('type')
    try:
        cls = storage_names[storage_name]
    except KeyError:
        raise exceptions.UserError(
            'Unknown storage type: {}'.format(storage_name))
    return cls, config


def storage_instance_from_config(config, create=True):
    '''
    :param config: A configuration dictionary to pass as kwargs to the class
        corresponding to config['type']
    '''

    cls, new_config = storage_class_from_config(config)

    try:
        return cls(**new_config)
    except exceptions.CollectionNotFound as e:
        if create:
            config = _handle_collection_not_found(
                config, config.get('collection', None), e=str(e))
            return storage_instance_from_config(config, create=False)
        else:
            raise
    except Exception:
        return handle_storage_init_error(cls, new_config)


def handle_storage_init_error(cls, config):
    e = sys.exc_info()[1]
    if not isinstance(e, TypeError) or '__init__' not in repr(e):
        raise

    all, required = get_storage_init_args(cls)
    given = set(config)
    missing = required - given
    invalid = given - all

    problems = []

    if missing:
        problems.append(
            u'{} storage requires the parameters: {}'
            .format(cls.storage_name, u', '.join(missing)))

    if invalid:
        problems.append(
            u'{} storage doesn\'t take the parameters: {}'
            .format(cls.storage_name, u', '.join(invalid)))

    if not problems:  # XXX: Py2: Proper reraise
        raise e

    raise exceptions.UserError(
        u'Failed to initialize {}'.format(config['instance_name']),
        problems=problems
    )


class WorkerQueue(object):
    '''
    A simple worker-queue setup.

    Note that workers quit if queue is empty. That means you have to first put
    things into the queue before spawning the worker!
    '''
    def __init__(self, max_workers):
        self._queue = queue.Queue()
        self._workers = []
        self._max_workers = max_workers
        self._shutdown_handlers = []

        # According to http://stackoverflow.com/a/27062830, those are
        # threadsafe compared to increasing a simple integer variable.
        self.num_done_tasks = itertools.count()
        self.num_failed_tasks = itertools.count()

    def shutdown(self):
        while self._shutdown_handlers:
            try:
                self._shutdown_handlers.pop()()
            except Exception:
                pass

    def _worker(self):
        while True:
            try:
                func = self._queue.get(False)
            except queue.Empty:
                break

            try:
                func(wq=self)
            except Exception:
                handle_cli_error()
                next(self.num_failed_tasks)
            finally:
                self._queue.task_done()
                next(self.num_done_tasks)
                if not self._queue.unfinished_tasks:
                    self.shutdown()

    def spawn_worker(self):
        if self._max_workers and len(self._workers) >= self._max_workers:
            return

        t = click_threading.Thread(target=self._worker)
        t.start()
        self._workers.append(t)

    @contextlib.contextmanager
    def join(self):
        assert self._workers or not self._queue.unfinished_tasks
        ui_worker = click_threading.UiWorker()
        self._shutdown_handlers.append(ui_worker.shutdown)
        _echo = click.echo

        with ui_worker.patch_click():
            yield

            if not self._workers:
                # Ugly hack, needed because ui_worker is not running.
                click.echo = _echo
                cli_logger.critical('Nothing to do.')
                sys.exit(5)

            ui_worker.run()
            self._queue.join()
            for worker in self._workers:
                worker.join()

        tasks_failed = next(self.num_failed_tasks)
        tasks_done = next(self.num_done_tasks)

        if tasks_failed > 0:
            cli_logger.error('{} out of {} tasks failed.'
                             .format(tasks_failed, tasks_done))
            sys.exit(1)

    def put(self, f):
        return self._queue.put(f)


def format_storage_config(cls, header=True):
    if header is True:
        yield '[storage example_for_{}]'.format(cls.storage_name)
    yield 'type = {}'.format(cls.storage_name)

    from ..storage.base import Storage
    from ..utils import get_storage_init_specs
    handled = set()
    for spec in get_storage_init_specs(cls, stop_at=Storage):
        defaults = spec.defaults or ()
        defaults = dict(zip(spec.args[-len(defaults):], defaults))
        for key in spec.args[1:]:
            if key in handled:
                continue
            handled.add(key)

            comment = '' if key not in defaults else '#'
            value = defaults.get(key, '...')
            yield '{}{} = {}'.format(comment, key, json.dumps(value))


def assert_permissions(path, wanted):
    permissions = os.stat(path).st_mode & 0o777
    if permissions > wanted:
        cli_logger.warning('Correcting permissions of {} from {:o} to {:o}'
                           .format(path, permissions, wanted))
        os.chmod(path, wanted)


def coerce_native(x, encoding='utf-8'):
    # XXX: Remove with Python 3 only
    try:
        return str(x)
    except UnicodeError:
        pass

    try:
        return to_native(x, encoding=encoding)
    except UnicodeError:
        pass

    return repr(x)
