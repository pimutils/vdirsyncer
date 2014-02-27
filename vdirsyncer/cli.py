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
from vdirsyncer.storage.caldav import CaldavStorage
from vdirsyncer.storage.filesystem import FilesystemStorage
from vdirsyncer.utils import expand_path
import vdirsyncer.log as log
import argvard


cli_logger = log.get('cli')


storage_names = {
    'caldav': CaldavStorage,
    'filesystem': FilesystemStorage
}


def get_config_parser(env):
    fname = env.get('VDIRSYNCER_CONFIG', expand_path('~/.vdirsyncer/config'))
    c = ConfigParser.RawConfigParser()
    c.read(fname)
    pairs = {}
    storages = {}
    for section in c.sections():
        if section.startswith('storage '):
            name = section[len('storage '):]
            storages.setdefault(name, {}).update(c.items(section))
        elif section.startswith('pair '):
            name = section[len('pair '):]
            options = dict(c.items(section))
            pairs[name] = a, b = (options.pop('a'), options.pop('b'))
            storages.setdefault(a, {}).update(options)
            storages.setdefault(b, {}).update(options)
        elif section == 'general':
            general = dict(c.items(section))
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
    cfg = get_config_parser(env)
    _main(env, cfg)


def _main(env, file_cfg):
    general, all_pairs, all_storages = file_cfg
    app = argvard.Argvard()


    @app.main()
    def app_main(context):
        print("Hello.")

    @app.option('--debug|-v')
    def debug_option(context):
        log.get('cli').setLevel(log.logging.DEBUG)
        log.get('sync').setLevel(log.logging.DEBUG)

    sync_command = argvard.Command()

    @sync_command.main('[pairs...]')
    def sync_main(context, pairs=None):
        if pairs is None:
            pairs = list(all_pairs)
        actions = []
        for pair_name in pairs:
            try:
                a, b = all_pairs[pair_name]
            except KeyError:
                cli_logger.critical('Pair not found: {}'.format(pair_name))
                cli_logger.critical('These are the pairs found: ')
                cli_logger.critical(list(all_pairs))
                sys.exit(1)
            a = storage_instance_from_config(all_storages[a])
            b = storage_instance_from_config(all_storages[b])
            
            def x(a=a, b=b, pair_name=pair_name):
                cli_logger.debug('Syncing {}'.format(pair_name))
                status = load_status(general['status_path'], pair_name)
                sync(a, b, status)
                save_status(general['status_path'], pair_name, status)
            actions.append(x)

        for action in actions:
            action()

    app.register_command('sync', sync_command)
    app()
