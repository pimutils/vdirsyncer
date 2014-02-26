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
import argvard


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
            raise RuntimeError('Unknown section: {}'.format(section))

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


def storage_instance_from_config(config):
    config = dict(config)
    cls = storage_names[config.pop('type')]
    try:
        return cls(**config)
    except TypeError:
        print(config)
        raise


def main():
    env = os.environ
    cfg = get_config_parser(env)
    _main(env, cfg)


def _main(env, file_cfg):
    general, all_pairs, all_storages = file_cfg
    app = argvard.Argvard()


    @app.main()
    def app_main(context):
        print("heY")

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
                print('Pair not found: {}'.format(pair_name))
                print(file_cfg)
                sys.exit(1)
            a = storage_instance_from_config(all_storages[a])
            b = storage_instance_from_config(all_storages[b])
            
            def x(a=a, b=b, pair_name=pair_name):
                status = load_status(general['status_path'], pair_name)
                sync(a, b, status)
                save_status(general['status_path'], pair_name, status)
            actions.append(x)

        for action in actions:
            action()

    app.register_command('sync', sync_command)
    app()
