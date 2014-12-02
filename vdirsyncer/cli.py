# -*- coding: utf-8 -*-
'''
    vdirsyncer.cli
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import functools
import json
import os
import sys
import threading

from . import DOCS_HOME, PROJECT_HOME, __version__, log
from .doubleclick import click
from .storage import storage_names
from .sync import StorageEmpty, SyncConflict, sync
from .utils import expand_path, get_class_init_args, parse_options, \
    safe_write, split_dict


try:
    from ConfigParser import RawConfigParser
except ImportError:
    from configparser import RawConfigParser

try:
    from Queue import Queue
except ImportError:
    from queue import Queue


cli_logger = log.get(__name__)

GENERAL_ALL = set(['status_path', 'passwordeval'])
GENERAL_REQUIRED = set(['status_path'])


class CliError(RuntimeError):
    pass


class JobFailed(RuntimeError):
    pass


def get_status_name(pair, collection):
    if collection is None:
        return pair
    return pair + '/' + collection


def validate_general_section(general_config):
    if general_config is None:
        raise CliError(
            'Unable to find general section. You should copy the example '
            'config from the repository and edit it.\n{}'.format(PROJECT_HOME)
        )

    invalid = set(general_config) - GENERAL_ALL
    missing = GENERAL_REQUIRED - set(general_config)

    if invalid:
        cli_logger.critical(u'general section doesn\'t take the parameters: {}'
                            .format(u', '.join(invalid)))

    if missing:
        cli_logger.critical(u'general section is missing the parameters: {}'
                            .format(u', '.join(missing)))

    if invalid or missing:
        raise CliError('Invalid general section.')


def load_config(fname, pair_options=('collections', 'conflict_resolution')):
    c = RawConfigParser()
    with open(fname) as f:
        c.readfp(f)

    get_options = lambda s: dict(parse_options(c.items(s), section=s))

    general = None
    pairs = {}
    storages = {}

    def handle_storage(storage_name, options):
        storages.setdefault(storage_name, {}).update(options)
        storages[storage_name]['instance_name'] = storage_name

    def handle_pair(pair_name, options):
        a, b = options.pop('a'), options.pop('b')
        p, s = split_dict(options, lambda x: x in pair_options)
        pairs[pair_name] = a, b, p, s

    def bad_section(name, options):
        cli_logger.error('Unknown section: {}'.format(name))

    handlers = {'storage': handle_storage, 'pair': handle_pair}

    for section in c.sections():
        if ' ' in section:
            section_type, name = section.split(' ', 1)
        else:
            section_type = name = section

        if section_type == 'general':
            if general is not None:
                raise CliError('More than one general section in config file.')
            general = get_options(section_type)
        else:
            handlers.get(section_type, bad_section)(name, get_options(section))

    validate_general_section(general)
    return general, pairs, storages


def load_status(path, status_name):
    full_path = expand_path(os.path.join(path, status_name))
    if not os.path.exists(full_path):
        return {}
    with open(full_path) as f:
        return dict(json.loads(line) for line in f)


def save_status(path, status_name, status):
    full_path = expand_path(os.path.join(path, status_name))
    base_path = os.path.dirname(full_path)

    if os.path.isfile(base_path):
        raise CliError('{} is probably a legacy file and could be removed '
                       'automatically, but this choice is left to the '
                       'user. If you think this is an error, please file '
                       'a bug at {}'.format(base_path, PROJECT_HOME))
    if not os.path.exists(base_path):
        os.makedirs(base_path, 0o750)

    with safe_write(full_path, 'w+') as f:
        for k, v in status.items():
            json.dump((k, v), f)
            f.write('\n')


def storage_class_from_config(config):
    config = dict(config)
    storage_name = config.pop('type')
    cls = storage_names.get(storage_name, None)
    if cls is None:
        raise CliError('Unknown storage type: {}'.format(storage_name))
    return cls, config


def storage_instance_from_config(config):
    '''
    :param config: A configuration dictionary to pass as kwargs to the class
        corresponding to config['type']
    :param description: A name for the storage for debugging purposes
    '''

    cls, config = storage_class_from_config(config)

    try:
        return cls(**config)
    except Exception:
        handle_storage_init_error(cls, config)


def handle_storage_init_error(cls, config):
    e = sys.exc_info()[1]
    if isinstance(e, (click.Abort, CliError, KeyboardInterrupt)):
        raise

    all, required = get_class_init_args(cls)
    given = set(config)
    missing = required - given
    invalid = given - all

    if missing:
        cli_logger.critical(
            u'{} storage requires the parameters: {}'
            .format(cls.storage_name, u', '.join(missing)))

    if invalid:
        cli_logger.critical(
            u'{} storage doesn\'t take the parameters: {}'
            .format(cls.storage_name, u', '.join(invalid)))

    if not missing and not invalid:
        cli_logger.exception('')

    raise CliError('Failed to initialize {}.'.format(config['instance_name']))


def parse_pairs_args(pairs_args, all_pairs):
    '''
    Expand the various CLI shortforms ("pair, pair/collection") to an iterable
    of (pair, collection).
    '''
    if not pairs_args:
        pairs_args = list(all_pairs)
    for pair_and_collection in pairs_args:
        pair, collection = pair_and_collection, None
        if '/' in pair:
            pair, collection = pair.split('/')

        try:
            a_name, b_name, pair_options, storage_defaults = \
                all_pairs[pair]
        except KeyError:
            raise CliError('Pair not found: {}\n'
                           'These are the pairs found: {}'
                           .format(pair, list(all_pairs)))

        if collection is None:
            collections = pair_options.get('collections', [None])
            if isinstance(collections, str):
                # XXX: Deprecation
                orig_collections = collections
                collections = [x.strip() or None
                               for x in collections.split(',')]
                cli_logger.warning(
                    '{!r} is deprecated, please use:\ncollections = {}\n'
                    'The old form will be removed in 0.4.0.'
                    .format(orig_collections, json.dumps(collections)))
        else:
            collections = [collection]

        for c in collections:
            yield pair, c

# We create the app inside a factory and destroy that factory after first use
# to avoid pollution of the module namespace.


def _create_app():
    def catch_errors(f):
        @functools.wraps(f)
        def inner(*a, **kw):
            try:
                f(*a, **kw)
            except:
                if not handle_cli_error():
                    sys.exit(1)

        return inner

    def validate_verbosity(ctx, param, value):
        x = getattr(log.logging, value.upper(), None)
        if x is None:
            raise click.BadParameter('Invalid verbosity value {}. Must be '
                                     'CRITICAL, ERROR, WARNING, INFO or DEBUG'
                                     .format(value))
        return x

    @click.group()
    @click.option('--verbosity', '-v', default='INFO',
                  callback=validate_verbosity,
                  help='Either CRITICAL, ERROR, WARNING, INFO or DEBUG')
    @click.version_option(version=__version__)
    @click.pass_context
    @catch_errors
    def app(ctx, verbosity):
        '''
        vdirsyncer -- synchronize calendars and contacts
        '''
        log.add_handler(log.stdout_handler)
        log.set_level(verbosity)

        if ctx.obj is None:
            ctx.obj = {}

        if 'config' not in ctx.obj:
            fname = expand_path(os.environ.get('VDIRSYNCER_CONFIG',
                                               '~/.vdirsyncer/config'))
            try:
                ctx.obj['config'] = load_config(fname)
            except Exception as e:
                raise CliError('Error during reading config {}: {}'
                               .format(fname, e))

    @app.command()
    @click.argument('pairs', nargs=-1)
    @click.option('--force-delete', multiple=True,
                  help=('Disable data-loss protection for the given pairs. '
                        'Can be passed multiple times'))
    @click.option('--max-workers',
                  default=0, type=click.IntRange(min=0, max=None),
                  help=('Use at most this many connections, 0 means '
                        'unlimited.'))
    @click.pass_context
    @catch_errors
    def sync(ctx, pairs, force_delete, max_workers):
        '''
        Synchronize the given pairs. If no pairs are given, all will be
        synchronized.

        Examples:
        `vdirsyncer sync` will sync everything configured.
        `vdirsyncer sync bob frank` will sync the pairs "bob" and "frank".
        `vdirsyncer sync bob/first_collection` will sync "first_collection"
        from the pair "bob".
        '''
        general, all_pairs, all_storages = ctx.obj['config']
        force_delete = set(force_delete)

        queue = Queue()
        workers = []
        cli_logger.debug('Using {} maximal workers.'.format(max_workers))
        exceptions = []
        handled_collections = set()

        def process_job():
            func = queue.get()
            try:
                func(queue=queue, spawn_worker=spawn_worker,
                     handled_collections=handled_collections)
            except:
                if not handle_cli_error():
                    exceptions.append(sys.exc_info()[1])
            finally:
                queue.task_done()

        def spawn_worker():
            if max_workers and len(workers) >= max_workers:
                return

            def worker():
                while True:
                    process_job()

            t = threading.Thread(target=worker)
            t.daemon = True
            t.start()
            workers.append(t)

        for pair_name, collection in parse_pairs_args(pairs, all_pairs):
            spawn_worker()
            queue.put(
                functools.partial(prepare_sync, pair_name=pair_name,
                                  collection=collection, general=general,
                                  all_pairs=all_pairs,
                                  all_storages=all_storages,
                                  force_delete=force_delete))

        queue.join()
        if exceptions:
            sys.exit(1)

    return app

app = main = _create_app()
del _create_app


def expand_collection(pair_name, collection, general, all_pairs, all_storages):
    a_name, b_name, pair_options, storage_defaults = all_pairs[pair_name]
    if collection in ('from a', 'from b'):
        # from_name: name of the storage which should be used for discovery
        # other_name: the other storage's name
        if collection == 'from a':
            from_name, other_name = a_name, b_name
        else:
            from_name, other_name = b_name, a_name

        cli_logger.info('Syncing {}: Discovering collections from {}'
                        .format(pair_name, from_name))

        config = dict(storage_defaults)
        config.update(all_storages[from_name])
        cls, config = storage_class_from_config(config)
        try:
            storages = list(cls.discover(**config))
        except Exception:
            handle_storage_init_error(cls, config)

        for storage in storages:
            config = dict(storage_defaults)
            config.update(all_storages[other_name])
            config['collection'] = actual_collection = storage.collection
            other_storage = storage_instance_from_config(config)

            if collection == 'from a':
                a, b = storage, other_storage
            else:
                b, a = storage, other_storage

            yield actual_collection, a, b
    else:
        config = dict(storage_defaults)
        config.update(all_storages[a_name])
        config['collection'] = collection
        a = storage_instance_from_config(config)

        config = dict(storage_defaults)
        config.update(all_storages[b_name])
        config['collection'] = collection
        b = storage_instance_from_config(config)

        yield collection, a, b


def prepare_sync(queue, spawn_worker, handled_collections, pair_name,
                 collection, general, all_pairs, all_storages, force_delete):
    key = ('prepare', pair_name, collection)
    if key in handled_collections:
        status_name = get_status_name(pair_name, collection)
        cli_logger.warning('Already prepared {}, skipping'.format(status_name))
        return
    handled_collections.add(key)

    a_name, b_name, pair_options, storage_defaults = all_pairs[pair_name]
    jobs = list(expand_collection(pair_name, collection, general, all_pairs,
                                  all_storages))

    for i in range(len(jobs) - 1):
        # spawn one worker less because we can reuse the current one
        spawn_worker()

    for collection, a, b in jobs:
        queue.put(functools.partial(sync_collection, pair_name=pair_name,
                                    collection=collection, a=a, b=b,
                                    pair_options=pair_options, general=general,
                                    force_delete=force_delete))


def handle_cli_error(status_name='sync'):
    try:
        raise
    except CliError as e:
        cli_logger.critical(str(e))
    except StorageEmpty as e:
        cli_logger.error(
            '{status_name}: Storage "{name}" was completely emptied. Use '
            '"--force-delete {status_name}" to synchronize that emptyness to '
            'the other side, or delete the status by yourself to restore the '
            'items from the non-empty side.'.format(
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
    except (click.Abort, KeyboardInterrupt, JobFailed):
        pass
    except Exception as e:
        cli_logger.exception('Unhandled exception occured while syncing {}.'
                             .format(status_name))
    else:
        return True


def sync_collection(queue, spawn_worker, handled_collections, pair_name,
                    collection, a, b, pair_options, general, force_delete):
    status_name = get_status_name(pair_name, collection)

    key = ('sync', pair_name, collection)
    if key in handled_collections:
        cli_logger.warning('Already syncing {}, skipping'.format(status_name))
        return
    handled_collections.add(key)

    try:
        cli_logger.info('Syncing {}'.format(status_name))

        status = load_status(general['status_path'], status_name)
        cli_logger.debug('Loaded status for {}'.format(status_name))
        sync(
            a, b, status,
            conflict_resolution=pair_options.get('conflict_resolution', None),
            force_delete=status_name in force_delete
        )
    except:
        if not handle_cli_error(status_name):
            raise JobFailed()

    save_status(general['status_path'], status_name, status)
