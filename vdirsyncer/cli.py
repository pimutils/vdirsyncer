# -*- coding: utf-8 -*-
'''
    vdirsyncer.cli
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os
import sys
import json
import ConfigParser
from vdirsyncer.sync import sync
from vdirsyncer.utils import expand_path, split_dict, parse_options
from vdirsyncer.storage import storage_names
import vdirsyncer.log as log
import argvard


cli_logger = log.get('cli')


def load_config(fname, pair_options=('collections', 'conflict_resolution')):
    c = ConfigParser.RawConfigParser()
    c.read(fname)

    get_options = lambda s: dict(parse_options(c.items(s)))

    pairs = {}
    storages = {}

    def handle_pair(section):
        pair_name = section[len('pair '):]
        options = get_options(section)
        a, b = options.pop('a'), options.pop('b')
        p, s = \
            split_dict(options, lambda x: x in pair_options)
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
            cli_logger.error(
                'Unknown section in {}: {}'.format(fname, section))

    return general, pairs, storages


def load_status(basepath, pair_name):
    full_path = os.path.join(expand_path(basepath), pair_name)
    if not os.path.exists(full_path):
        return {}
    with open(full_path) as f:
        return dict(json.loads(line) for line in f)


def save_status(basepath, pair_name, status):
    full_path = os.path.join(expand_path(basepath), pair_name)
    with open(full_path, 'w+') as f:
        for k, v in status.items():
            json.dump((k, v), f)
            f.write('\n')


def storage_instance_from_config(config):
    config = dict(config)
    storage_name = config.pop('type')
    cls = storage_names[storage_name]
    try:
        return cls(**config)
    except TypeError as e:
        import inspect
        x = cli_logger.critical
        spec = inspect.getargspec(cls.__init__)
        required_args = set(spec.args[:-len(spec.defaults)])

        x(str(e))
        x('')
        x('Unable to initialize storage {}.'.format(storage_name))
        x('Here are the required arguments for the storage:')
        x(list(required_args - {'self'}))
        x('Here are the optional arguments:')
        x(list(set(spec.args) - required_args))
        x('And here are the ones you gave: ')
        x(list(config))
        sys.exit(1)


def main():
    env = os.environ

    fname = env.get('VDIRSYNCER_CONFIG', expand_path('~/.vdirsyncer/config'))
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
            collections = [x.strip() for x in
                           pair_options.get('collections', '').split(',')]
        else:
            collections = [collection]

        for c in collections:
            yield pair, c


def _main(env, file_cfg):
    general, all_pairs, all_storages = file_cfg
    app = argvard.Argvard()

    @app.option('--verbosity verbosity')
    def verbose_option(context, verbosity):
        '''
        Basically Python logging levels.

        CRITICAL: Config errors, at most.

        ERROR: Normal errors, at most.

        WARNING: Problems of which vdirsyncer thinks that it can handle them
        itself, but which might crash other clients.

        INFO: Normal output.

        DEBUG: Show e.g. HTTP traffic. Not supposed to be readable by the
        normal user.

        '''
        x = getattr(log.logging, verbosity, None)
        if x is None:
            raise ValueError(u'Invalid verbosity value: {}'.format(verbosity))
        log.set_level(x)

    @app.option('--quiet|-q')
    def quiet_option(context=None):
        '''Print less information than normal.'''
        log.set_level(log.logging.WARNING)

    sync_command = argvard.Command()

    @sync_command.main('[pairs...]')
    def sync_main(context, pairs=None):
        '''
        Syncronize the given pairs. If no pairs are given, all will be
        synchronized.

        Examples:
        `vdirsyncer sync` will sync everything configured.
        `vdirsyncer sync bob frank` will sync the pairs "bob" and "frank".
        `vdirsyncer sync bob/first_collection` will sync "first_collection"
        from the pair "bob".
        '''
        actions = []
        for pair_name, collection in parse_pairs_args(pairs, all_pairs):
            a_name, b_name, pair_options, storage_defaults = \
                all_pairs[pair_name]
            if collection:
                storage_defaults['collection'] = collection
            config_a = dict(storage_defaults)
            config_a.update(all_storages[a_name])
            config_b = dict(storage_defaults)
            config_b.update(all_storages[b_name])
            a = storage_instance_from_config(config_a)
            b = storage_instance_from_config(config_b)

            def x(a=a, b=b, pair_name=pair_name, collection=collection):
                status_name = \
                    '_'.join(filter(bool, (pair_name, collection)))
                pair_description = \
                    ' from '.join(filter(bool, (collection, pair_name)))
                cli_logger.info('Syncing {}'.format(pair_description))
                status = load_status(general['status_path'], status_name)
                sync(a, b, status,
                     pair_options.get('conflict_resolution', None))
                save_status(general['status_path'], status_name, status)
            actions.append(x)

        for action in actions:
            action()

    app.register_command('sync', sync_command)
    app()
