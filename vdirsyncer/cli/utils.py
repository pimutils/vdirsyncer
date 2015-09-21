# -*- coding: utf-8 -*-

import contextlib
import errno
import functools
import hashlib
import importlib
import json
import os
import sys
import threading

from atomicwrites import atomic_write

import click

import click_threading

from . import CliError, cli_logger
from .. import DOCS_HOME, exceptions
from ..sync import IdentConflict, StorageEmpty, SyncConflict
from ..utils import expand_path, get_class_init_args

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


def handle_cli_error(status_name=None):
    '''
    Print a useful error message for the current exception.

    This is supposed to catch all exceptions, and should never raise any
    exceptions itself.
    '''

    try:
        raise
    except CliError as e:
        cli_logger.critical(e.format_cli())
    except StorageEmpty as e:
        cli_logger.error(
            '{status_name}: Storage "{name}" was completely emptied. Use '
            '`vdirsyncer sync --force-delete {status_name}` to synchronize '
            'that emptyness to the other side, or delete the status by '
            'yourself to restore the items from the non-empty side.'.format(
                name=e.empty_storage.instance_name,
                status_name=status_name
            )
        )
    except SyncConflict as e:
        cli_logger.error(
            '{status_name}: One item changed on both sides. Resolve this '
            'conflict manually, or by setting the `conflict_resolution` '
            'parameter in your config file.\n'
            'See also {docs}/api.html#pair-section\n'
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
    except Exception as e:
        if status_name:
            msg = 'Unhandled exception occured for {}.'.format(status_name)
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


def collections_for_pair(status_path, pair, skip_cache=False):
    '''Determine all configured collections for a given pair. Takes care of
    shortcut expansion and result caching.

    :param status_path: The path to the status directory.
    :param skip_cache: Whether to skip the cached data and always do discovery.
        Even with this option enabled, the new cache is written.

    :returns: iterable of (collection, (a_args, b_args))
    '''
    rv = load_status(status_path, pair.name, data_type='collections')
    cache_key = _get_collections_cache_key(pair)
    if rv and not skip_cache:
        if rv.get('cache_key', None) == cache_key:
            return list(_expand_collections_cache(
                rv['collections'], pair.config_a, pair.config_b
            ))
        elif rv:
            cli_logger.info('Detected change in config file, discovering '
                            'collections for {}'.format(pair.name))

    cli_logger.info('Discovering collections for pair {}'
                    .format(pair.name))

    # We have to use a list here because the special None/null value would get
    # mangled to string (because JSON objects always have string keys).
    rv = list(_collections_for_pair_impl(status_path, pair))

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
        discovered = list(cls.discover(**config))
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
                             collection, storage_name))

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

    raise CliError('Unable to find or create collection "{collection}" for '
                   'storage "{storage}". Please create the collection '
                   'yourself.'.format(collection=collection,
                                      storage=storage_name))


def _collections_for_pair_impl(status_path, pair):

    shortcuts = set(pair.options.get('collections', ()))
    if not shortcuts:
        yield None, (pair.config_a, pair.config_b)
    else:
        a_discovered = _discover_from_config(pair.config_a)
        b_discovered = _discover_from_config(pair.config_b)

        for shortcut in shortcuts:
            if shortcut == 'from a':
                collections = a_discovered
            elif shortcut == 'from b':
                collections = b_discovered
            else:
                collections = [shortcut]

            for collection in collections:
                try:
                    a_args = a_discovered[collection]
                except KeyError:
                    a_args = _handle_collection_not_found(pair.config_a,
                                                          collection)

                try:
                    b_args = b_discovered[collection]
                except KeyError:
                    b_args = _handle_collection_not_found(pair.config_b,
                                                          collection)

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

        # XXX: Deprecate
        # Old status format, deprecated as of 0.4.0
        # See commit 06a701bc10dac16ff0ff304eb7cb9f502b71cf95
        f.seek(0)
        try:
            return dict(json.loads(line) for line in f)
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
        raise CliError('Unknown storage type: {}'.format(storage_name))
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
    if isinstance(e, (click.Abort, CliError, KeyboardInterrupt)):
        raise

    all, required = get_class_init_args(cls)
    given = set(config)
    missing = required - given
    invalid = given - all

    problems = []

    if missing:
        cli_logger.critical(
            u'{} storage requires the parameters: {}'
            .format(cls.storage_name, u', '.join(missing)))

    if invalid:
        cli_logger.critical(
            u'{} storage doesn\'t take the parameters: {}'
            .format(cls.storage_name, u', '.join(invalid)))

    if not problems:
        if not isinstance(e, exceptions.UserError):
            cli_logger.exception('')
        problems.append(str(e))

    raise CliError(u'Failed to initialize {}'.format(config['instance_name']),
                   problems=problems)


class WorkerQueue(object):
    '''
    In which I reinvent concurrent.futures.ThreadPoolExecutor.

    I can't just block the main thread to wait for my tasks to finish, I have
    to run the UI worker on it.

    Unfortunately ThreadPoolExecutor doesn't allow me to return early from
    tasks and just quit when the queue is empty. This means that I e.g. have a
    few threads that do nothing but waiting for other threads, and when I set
    `max_workers=1`, I actually can't get any work done because the only worker
    is waiting for other jobs to be finished.

    This clone has the same problem at some places (like when the sync routine
    waits for all actions until it writes the status), but at least not
    everywhere. What I do in such situations is to just force-spawn a new
    worker, which may cross the `max_workers`-limit, but oh well, so be it.

    Note that workers quit if the queue is empty. That means you have to first
    put things into the queue before spawning the worker!
    '''
    def __init__(self, max_workers):
        assert max_workers > 0
        self._queue = queue.Queue()
        self._workers = []
        self._exceptions = []

        # We need one additional worker because sync blocks until completion
        # and doesn't do anything itself.
        self._max_workers = max_workers + 1
        self._shutdown_handlers = []

    def shutdown(self):
        if not self._queue.unfinished_tasks:
            while self._shutdown_handlers:
                try:
                    handler = self._shutdown_handlers.pop()
                    handler()
                except Exception:
                    pass

    def _worker(self):
        while True:
            try:
                func = self._queue.get(False)
            except queue.Empty:
                if not self._queue.unfinished_tasks:
                    self.shutdown()
                    break
                else:
                    continue

            try:
                func(wq=self)
            except Exception as e:
                handle_cli_error()
                self._exceptions.append(e)
            finally:
                self._queue.task_done()

    def map(self, function, items):
        events = []
        output = []

        def _work(wq, i, item):
            try:
                output[i] = function(item)
            except Exception as e:
                output[i] = e
                raise e
            finally:
                events[i].set()

        for i, item in enumerate(items):
            events.append(threading.Event())
            output.append(None)
            self.put(functools.partial(_work, i=i, item=item))

        # This is necessary so map's return value doesn't need to be used in
        # any way for the tasks to get enqueued.
        def get_results():
            for i, event in enumerate(events):
                event.wait()
                yield output[i]

        return get_results()

    @contextlib.contextmanager
    def join(self):
        assert self._workers or not self._queue.unfinished_tasks
        ui_worker = click_threading.UiWorker()
        self._shutdown_handlers.append(ui_worker.shutdown)
        with ui_worker.patch_click():
            yield
            ui_worker.run()
            self._queue.join()

        if self._exceptions:
            sys.exit(1)

    def put(self, f):
        self._queue.put(f)

        if len(self._workers) < self._max_workers:
            self.spawn_worker()

    def spawn_worker(self):
        t = click_threading.Thread(target=self._worker)
        t.daemon = True
        t.start()
        self._workers.append(t)


def format_storage_config(cls, header=True):
    if header is True:
        yield '[storage example_for_{}]'.format(cls.storage_name)
    yield 'type = {}'.format(cls.storage_name)

    from ..storage.base import Storage
    from ..utils import get_class_init_specs
    handled = set()
    for spec in get_class_init_specs(cls, stop_at=Storage):
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
