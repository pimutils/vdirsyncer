# -*- coding: utf-8 -*-
'''
    vdirsyncer.cli
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import json
import os
import sys

import click

from . import log
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
    try:
        with open(fname) as f:
            c.readfp(f)
    except IOError:
        cli_logger.exception('Error while trying to read config file.')
        sys.exit(1)

    get_options = lambda s: dict(parse_options(c.items(s), section=s))

    general = None
    pairs = {}
    storages = {}

    def handle_pair(section):
        pair_name = section[len('pair '):]
        options = get_options(section)
        a, b = options.pop('a'), options.pop('b')
        p, s = split_dict(options, lambda x: x in pair_options)
        pairs[pair_name] = a, b, p, s

    for section in c.sections():
        if section.startswith('storage '):
            name = section[len('storage '):]
            storages.setdefault(name, {}).update(get_options(section))
        elif section.startswith('pair '):
            handle_pair(section)
        elif section == 'general':
            general = get_options(section)
        else:
            cli_logger.error('Unknown section in {}: {}'
                             .format(fname, section))

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
        os.makedirs(base_path)

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

        cli_logger.critical('error: Failed to initialize {}'
                            .format(description or cls.storage_name))

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

        sys.exit(1)


def expand_collection(pair, collection, all_pairs, all_storages):
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


def main():
    env = os.environ

    fname = expand_path(env.get('VDIRSYNCER_CONFIG', '~/.vdirsyncer/config'))
    cfg = load_config(fname)
    _main(env, cfg)


def parse_pairs_args(pairs_args, all_pairs):
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
            cli_logger.critical('Pair not found: {}'.format(pair))
            cli_logger.critical('These are the pairs found: ')
            cli_logger.critical(list(all_pairs))
            sys.exit(1)

        if collection is None:
            collections = [x.strip() or None for x in
                           pair_options.get('collections', '').split(',')]
        else:
            collections = [collection]

        for c in collections:
            yield pair, c


def _main(env, file_cfg):
    general, all_pairs, all_storages = file_cfg

    @click.group()
    @click.option('--verbosity', '-v', default='INFO',
                  help='Either CRITICAL, ERROR, WARNING, INFO or DEBUG')
    def app(verbosity):
        '''
        vdirsyncer -- synchronize calendars and contacts
        '''
        verbosity = verbosity.upper()
        x = getattr(log.logging, verbosity, None)
        if x is None:
            cli_logger.critical(u'Invalid verbosity value: {}'
                                .format(verbosity))
            sys.exit(1)
        else:
            log.set_level(x)

    @app.command()
    @click.argument('pairs', nargs=-1)
    @click.option('--force-delete', multiple=True,
                  help=('Disable data-loss protection for the given pairs. '
                        'Can be passed multiple times'))
    def sync(pairs, force_delete):
        '''
        Synchronize the given pairs. If no pairs are given, all will be
        synchronized.

        Examples:
        `vdirsyncer sync` will sync everything configured.
        `vdirsyncer sync bob frank` will sync the pairs "bob" and "frank".
        `vdirsyncer sync bob/first_collection` will sync "first_collection"
        from the pair "bob".
        '''
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
            map(_sync_collection, actions)
        else:
            cli_logger.debug('Using multiprocessing.')
            from multiprocessing import Pool
            p = Pool(processes=general.get('processes', 0) or len(actions))
            if not all(p.map_async(_sync_collection, actions).get(10**9)):
                sys.exit(1)

    try:
        app()
    except CliError as e:
        cli_logger.critical(str(e))
        sys.exit(1)


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
        cli_logger.critical(
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
        cli_logger.critical(
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
