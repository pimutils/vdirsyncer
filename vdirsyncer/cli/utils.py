# -*- coding: utf-8 -*-

import errno
import hashlib
import importlib
import json
import os
import string
import sys
import threading
import uuid
from itertools import chain

from atomicwrites import atomic_write

from . import CliError, cli_logger
from .. import DOCS_HOME, PROJECT_HOME, exceptions
from ..doubleclick import click
from ..sync import IdentConflict, StorageEmpty, SyncConflict
from ..utils import expand_path, get_class_init_args
from ..utils.compat import text_type
from ..utils.vobject import Item


try:
    from ConfigParser import RawConfigParser
except ImportError:
    from configparser import RawConfigParser

try:
    import Queue as queue
except ImportError:
    import queue


STATUS_PERMISSIONS = 0o600
STATUS_DIR_PERMISSIONS = 0o700


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


GENERAL_ALL = frozenset(['status_path', 'password_command'])
GENERAL_REQUIRED = frozenset(['status_path'])
SECTION_NAME_CHARS = frozenset(chain(string.ascii_letters, string.digits, '_'))


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


def validate_section_name(name, section_type):
    invalid = set(name) - SECTION_NAME_CHARS
    if invalid:
        chars_display = ''.join(sorted(SECTION_NAME_CHARS))
        raise CliError('The {}-section "{}" contains invalid characters. Only '
                       'the following characters are allowed for storage and '
                       'pair names:\n{}'.format(section_type, name,
                                                chars_display))


def get_status_name(pair, collection):
    if collection is None:
        return pair
    return pair + '/' + collection


def _get_collections_cache_key(pair_options, config_a, config_b):
    m = hashlib.sha256()
    j = json.dumps([
        pair_options.get('collections', None),
        config_a, config_b
    ], sort_keys=True)
    m.update(j.encode('utf-8'))
    return m.hexdigest()


def collections_for_pair(status_path, name_a, name_b, pair_name, config_a,
                         config_b, pair_options, skip_cache=False):
    '''Determine all configured collections for a given pair. Takes care of
    shortcut expansion and result caching.

    :param status_path: The path to the status directory.
    :param name_a: The config name of storage A.
    :param name_b: The config name of storage B.
    :param pair_name: The config name of the pair.
    :param config_a: The configuration for storage A.
    :param config_b: The configuration for storage B.
    :param pair_options: Pair-specific options.
    :param skip_cache: Whether to skip the cached data and always do discovery.
        Even with this option enabled, the new cache is written.

    :returns: iterable of (collection, (a_args, b_args))
    '''
    rv = load_status(status_path, pair_name, data_type='collections')
    cache_key = _get_collections_cache_key(pair_options, config_a, config_b)
    if rv and not skip_cache:
        if rv.get('cache_key', None) == cache_key:
            return list(_expand_collections_cache(
                rv['collections'], config_a, config_b
            ))
        elif rv:
            cli_logger.info('Detected change in config file, discovering '
                            'collections for {}'.format(pair_name))

    cli_logger.info('Discovering collections for pair {}'
                    .format(pair_name))

    # We have to use a list here because the special None/null value would get
    # mangled to string (because JSON objects always have string keys).
    rv = list(_collections_for_pair_impl(status_path, name_a, name_b,
                                         pair_name, config_a, config_b,
                                         pair_options))

    save_status(status_path, pair_name, data_type='collections',
                data={
                    'collections': list(
                        _compress_collections_cache(rv, config_a, config_b)
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


def _collections_for_pair_impl(status_path, name_a, name_b, pair_name,
                               config_a, config_b, pair_options):

    shortcuts = set(pair_options.get('collections', ()))
    if not shortcuts:
        yield None, (config_a, config_b)
    else:
        a_discovered = _discover_from_config(config_a)
        b_discovered = _discover_from_config(config_b)

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
                    a_args = _handle_collection_not_found(config_a, collection)

                try:
                    b_args = b_discovered[collection]
                except KeyError:
                    b_args = _handle_collection_not_found(config_b, collection)

                yield collection, (a_args, b_args)


def _validate_general_section(general_config):
    if 'passwordeval' in general_config:
        # XXX: Deprecation
        cli_logger.warning('The `passwordeval` parameter has been renamed to '
                           '`password_command`.')

    invalid = set(general_config) - GENERAL_ALL
    missing = GENERAL_REQUIRED - set(general_config)
    problems = []

    if invalid:
        problems.append(u'general section doesn\'t take the parameters: {}'
                        .format(u', '.join(invalid)))

    if missing:
        problems.append(u'general section is missing the parameters: {}'
                        .format(u', '.join(missing)))

    if problems:
        raise CliError(u'Invalid general section. You should copy the example '
                       u'config from the repository and edit it: {}\n'
                       .format(PROJECT_HOME), problems=problems)


def _validate_pair_section(pair_config):
    collections = pair_config.get('collections', None)
    if collections is None:
        return
    e = ValueError('`collections` parameter must be a list of collection '
                   'names (strings!) or `null`.')
    if not isinstance(collections, list) or \
       any(not isinstance(x, (text_type, bytes)) for x in collections):
        raise e


def load_config():
    fname = os.environ.get('VDIRSYNCER_CONFIG', None)
    if not fname:
        fname = expand_path('~/.vdirsyncer/config')
        if not os.path.exists(fname):
            xdg_config_dir = os.environ.get('XDG_CONFIG_HOME',
                                            expand_path('~/.config/'))
            fname = os.path.join(xdg_config_dir, 'vdirsyncer/config')

    try:
        with open(fname) as f:
            general, pairs, storages = read_config(f)
    except Exception as e:
        raise CliError('Error during reading config {}: {}'
                       .format(fname, e))

    return general, pairs, storages


def read_config(f):
    c = RawConfigParser()
    c.readfp(f)

    def get_options(s):
        return dict(parse_options(c.items(s), section=s))

    general = {}
    pairs = {}
    storages = {}

    def handle_storage(storage_name, options):
        storages.setdefault(storage_name, {}).update(options)
        storages[storage_name]['instance_name'] = storage_name

    def handle_pair(pair_name, options):
        _validate_pair_section(options)
        a, b = options.pop('a'), options.pop('b')
        pairs[pair_name] = a, b, options

    def handle_general(_, options):
        if general:
            raise CliError('More than one general section in config file.')
        general.update(options)

    def bad_section(name, options):
        cli_logger.error('Unknown section: {}'.format(name))

    handlers = {'storage': handle_storage, 'pair': handle_pair, 'general':
                handle_general}

    for section in c.sections():
        if ' ' in section:
            section_type, name = section.split(' ', 1)
        else:
            section_type = name = section

        try:
            validate_section_name(name, section_type)
            f = handlers.get(section_type, bad_section)
            f(name, get_options(section))
        except ValueError as e:
            raise CliError('Section `{}`: {}'.format(section, str(e)))

    _validate_general_section(general)
    if getattr(f, 'name', None):
        general['status_path'] = os.path.join(
            os.path.dirname(f.name),
            expand_path(general['status_path'])
        )
    return general, pairs, storages


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

    if collection is not None and os.path.isfile(dirname):
        raise CliError('{} is probably a legacy file and could be removed '
                       'automatically, but this choice is left to the '
                       'user. If you think this is an error, please file '
                       'a bug at {}'.format(dirname, PROJECT_HOME))

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


def parse_pairs_args(pairs_args, all_pairs):
    '''
    Expand the various CLI shortforms ("pair, pair/collection") to an iterable
    of (pair, collections).
    '''
    rv = {}
    for pair_and_collection in (pairs_args or all_pairs):
        pair, collection = pair_and_collection, None
        if '/' in pair:
            pair, collection = pair.split('/')

        if pair not in all_pairs:
            raise CliError('Pair not found: {}\n'
                           'These are the pairs found: {}'
                           .format(pair, list(all_pairs)))

        collections = rv.setdefault(pair, set())
        if collection:
            collections.add(collection)

    return rv.items()


class WorkerQueue(object):
    def __init__(self, max_workers):
        self._queue = queue.Queue()
        self._workers = []
        self._exceptions = []
        self._max_workers = max_workers

    def _worker(self):
        # This is a daemon thread. Since the global namespace is going to
        # vanish on interpreter shutdown, redefine everything from the global
        # namespace here.
        _TypeError = TypeError
        _Empty = queue.Empty
        _handle_cli_error = handle_cli_error

        while True:
            try:
                func = self._queue.get()
            except (_TypeError, _Empty):
                # Any kind of error might be raised if vdirsyncer just finished
                # processing all items and the interpreter is shutting down,
                # yet the workers try to get new tasks.
                # https://github.com/untitaker/vdirsyncer/issues/167
                # http://bugs.python.org/issue14623
                break

            try:
                func(wq=self)
            except Exception as e:
                _handle_cli_error()
                self._exceptions.append(e)
            finally:
                self._queue.task_done()

    def spawn_worker(self):
        if self._max_workers and len(self._workers) >= self._max_workers:
            return

        t = threading.Thread(target=self._worker)
        t.daemon = True
        t.start()
        self._workers.append(t)

    def join(self):
        self._queue.join()
        if self._exceptions:
            sys.exit(1)

    def put(self, f):
        return self._queue.put(f)


def parse_config_value(value):
    try:
        return json.loads(value)
    except ValueError:
        pass

    for wrong, right in [
        (('on', 'yes'), 'true'),
        (('off', 'no'), 'false'),
        (('none',), 'null')
    ]:
        if value.lower() in wrong + (right,):
            cli_logger.warning('You probably meant {} instead of "{}", which '
                               'will now be interpreted as a literal string.'
                               .format(right, value))

    if '#' in value:
        raise ValueError('Invalid value:{}\n'
                         'Use double quotes (") if you want to use hashes in '
                         'your value.')

    if len(value.splitlines()) > 1:
        # ConfigParser's barrier for mistaking an arbitrary line for the
        # continuation of a value is awfully low. The following example will
        # also contain the second line in the value:
        #
        # foo = bar
        #  # my comment
        raise ValueError('No multiline-values allowed:\n{}'.format(value))

    return value


def parse_options(items, section=None):
    for key, value in items:
        try:
            yield key, parse_config_value(value)
        except ValueError as e:
            raise ValueError('Section "{}", option "{}": {}'
                             .format(section, key, e))


def format_storage_config(cls, header=True):
    if header is True:
        yield '[storage example_for_{}]'.format(cls.storage_name)
    yield 'type = {}'.format(cls.storage_name)

    from ..storage.base import Storage
    from ..utils import get_class_init_specs
    handled = set()
    for spec in get_class_init_specs(cls, stop_at=Storage):
        defaults = dict(zip(spec.args[-len(spec.defaults):], spec.defaults))
        for key in spec.args[1:]:
            if key in handled:
                continue
            handled.add(key)

            comment = '' if key not in defaults else '#'
            value = defaults.get(key, '...')
            yield '{}{} = {}'.format(comment, key, json.dumps(value))


def repair_storage(storage):
    seen_uids = set()
    all_hrefs = list(storage.list())
    for i, (href, _) in enumerate(all_hrefs):
        item, etag = storage.get(href)
        cli_logger.info('[{}/{}] Processing {}'
                        .format(i, len(all_hrefs), href))

        parsed = item.parsed
        changed = False
        if parsed is None:
            cli_logger.warning('Item {} can\'t be parsed, skipping.'
                               .format(href))
            continue

        if item.uid is None or item.uid in seen_uids:
            if item.uid is None:
                cli_logger.warning('No UID, assigning random one.')
            else:
                cli_logger.warning('Duplicate UID, reassigning random one.')

            new_uid = uuid.uuid4()
            stack = [parsed]
            while stack:
                component = stack.pop()
                if component.name in ('VEVENT', 'VTODO', 'VJOURNAL', 'VCARD'):
                    component['UID'] = new_uid
                    changed = True
                else:
                    stack.extend(component.subcomponents)

        new_item = Item(u'\r\n'.join(parsed.dump_lines()))
        assert new_item.uid
        seen_uids.add(new_item.uid)
        if changed:
            storage.update(href, new_item, etag)


def assert_permissions(path, wanted):
    permissions = os.stat(path).st_mode & 0o777
    if permissions > wanted:
        cli_logger.warning('Correcting permissions of {} from {:o} to {:o}'
                           .format(path, permissions, wanted))
        os.chmod(path, wanted)
