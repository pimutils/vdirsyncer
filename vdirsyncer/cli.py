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

import click

from . import __version__, log
from .storage import storage_names
from .sync import StorageEmpty, SyncConflict, sync
from .utils import expand_path, get_class_init_args, parse_options, split_dict


try:
    from ConfigParser import RawConfigParser
except ImportError:
    from configparser import RawConfigParser


cli_logger = log.get(__name__)

PROJECT_HOME = 'https://github.com/untitaker/vdirsyncer'
DOCS_HOME = 'https://vdirsyncer.readthedocs.org/en/latest'


class CliError(RuntimeError):
    pass


def get_status_name(pair, collection):
    if collection is None:
        return pair
    return pair + '/' + collection


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

    if general is None:
        raise CliError(
            'Unable to find general section. You should copy the example '
            'config from the repository and edit it.\n{}'.format(PROJECT_HOME)
        )

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

    with open(full_path, 'w+') as f:
        for k, v in status.items():
            json.dump((k, v), f)
            f.write('\n')


def storage_class_from_config(config):
    config = dict(config)
    storage_name = config.pop('type')
    cls = storage_names.get(storage_name, None)
    if cls is None:
        raise KeyError('Unknown storage: {}'.format(storage_name))
    return cls, config


def storage_instance_from_config(config, description=None):
    '''
    :param config: A configuration dictionary to pass as kwargs to the class
        corresponding to config['type']
    :param description: A name for the storage for debugging purposes
    '''

    cls, config = storage_class_from_config(config)

    try:
        return cls(**config)
    except Exception:
        all, required = get_class_init_args(cls)
        given = set(config)
        missing = required - given
        invalid = given - all

        if not missing and not invalid:
            cli_logger.exception('')

        if missing:
            cli_logger.critical(
                u'error: {} storage requires the parameters: {}'
                .format(cls.storage_name, u', '.join(missing)))

        if invalid:
            cli_logger.critical(
                u'error: {} storage doesn\'t take the parameters: {}'
                .format(cls.storage_name, u', '.join(invalid)))

        raise CliError('error: Failed to initialize {}'
                       .format(description or cls.storage_name))


def expand_collection(pair, collection, all_pairs, all_storages):
    '''
    Replace the placeholder collections "from a" and "from b" with actual
    ones.

    :param collection: The collection.
    :param pair: The pair the collection belongs to.
    :param all_pairs: dictionary: pair_name => (name of storage a,
                                                name of storage b,
                                                pair config,
                                                storage defaults)
    :returns: One or more collections that replace the given one. The original
        collection is returned unmodified if the given collection is neither
        "from a" nor "from b".
    '''
    if collection in ('from a', 'from b'):
        a_name, b_name, _, storage_defaults = all_pairs[pair]
        config = dict(storage_defaults)
        if collection == 'from a':
            config.update(all_storages[a_name])
        else:
            config.update(all_storages[b_name])
        cls, config = storage_class_from_config(config)
        return (s.collection for s in cls.discover(**config))
    else:
        return [collection]


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
            collections = [x.strip() or None for x in
                           pair_options.get('collections', '').split(',')]
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
            except CliError as e:
                cli_logger.critical(str(e))
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
                raise CliError('Error during reading config{}:\n{}'
                               .format(fname, e))

    @app.command()
    @click.argument('pairs', nargs=-1)
    @click.option('--force-delete', multiple=True,
                  help=('Disable data-loss protection for the given pairs. '
                        'Can be passed multiple times'))
    @click.pass_context
    @catch_errors
    def sync(ctx, pairs, force_delete):
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

        actions = []
        handled_collections = set()
        force_delete = set(force_delete)
        for pair_name, _collection in parse_pairs_args(pairs, all_pairs):
            for collection in expand_collection(pair_name, _collection,
                                                all_pairs, all_storages):
                if (pair_name, collection) in handled_collections:
                    continue
                handled_collections.add((pair_name, collection))

                a_name, b_name, pair_options, storage_defaults = \
                    all_pairs[pair_name]

                config_a = dict(storage_defaults)
                config_a['collection'] = collection
                config_a.update(all_storages[a_name])

                config_b = dict(storage_defaults)
                config_b['collection'] = collection
                config_b.update(all_storages[b_name])

                actions.append({
                    'config_a': config_a,
                    'config_b': config_b,
                    'pair_name': pair_name,
                    'collection': collection,
                    'pair_options': pair_options,
                    'general': general,
                    'force_delete': force_delete
                })

        processes = general.get('processes', 0) or len(actions)
        cli_logger.debug('Using {} processes.'.format(processes))

        if processes == 1:
            cli_logger.debug('Not using multiprocessing.')
            rv = (_sync_collection(x) for x in actions)
        else:
            cli_logger.debug('Using multiprocessing.')
            from multiprocessing import Pool
            p = Pool(processes=general.get('processes', 0) or len(actions))
            rv = p.map_async(_sync_collection, actions).get(10**9)

        if not all(rv):
            sys.exit(1)

    return app

app = main = _create_app()
del _create_app


def _sync_collection(x):
    return sync_collection(**x)


def sync_collection(config_a, config_b, pair_name, collection, pair_options,
                    general, force_delete):
    status_name = get_status_name(pair_name, collection)
    collection_description = pair_name if collection is None \
        else '{} from {}'.format(collection, pair_name)

    a = storage_instance_from_config(config_a, collection_description)
    b = storage_instance_from_config(config_b, collection_description)

    cli_logger.info('Syncing {}'.format(collection_description))
    status = load_status(general['status_path'], status_name)
    rv = True
    try:
        sync(
            a, b, status,
            conflict_resolution=pair_options.get('conflict_resolution', None),
            force_delete=status_name in force_delete
        )
    except StorageEmpty as e:
        rv = False
        cli_logger.error(
            '{collection}: Storage "{side}" ({storage}) was completely '
            'emptied. Use "--force-delete {status_name}" to synchronize that '
            'emptyness to the other side, or delete the status by yourself to '
            'restore the items from the non-empty side.'.format(
                collection=collection_description,
                side='a' if e.empty_storage is a else 'b',
                storage=e.empty_storage,
                status_name=status_name
            )
        )
    except SyncConflict as e:
        rv = False
        cli_logger.error(
            '{collection}: One item changed on both sides. Resolve this '
            'conflict manually, or by setting the `conflict_resolution` '
            'parameter in your config file.\n'
            'See also {docs}/api.html#pair-section\n'
            'Item ID: {e.ident}\n'
            'Item href on side A: {e.href_a}\n'
            'Item href on side B: {e.href_b}\n'
            .format(collection=collection_description, e=e, docs=DOCS_HOME)
        )
    except Exception:
        rv = False
        cli_logger.exception('Unhandled exception occured while syncing {}.'
                             .format(collection_description))

    save_status(general['status_path'], status_name, status)
    return rv
