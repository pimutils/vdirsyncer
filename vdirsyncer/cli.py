# -*- coding: utf-8 -*-
'''
    vdirsyncer.cli
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os
import ConfigParser
from vdirsyncer.sync import sync_classes

def _path(p):
    p = os.path.expanduser(p)
    p = os.path.abspath(p)
    return p

def get_config_parser(env):
    fname = env.get('VDIRSYNCER_CONFIG', _path('~/.vdirsyncer/config'))
    c = ConfigParser.SafeConfigParser()
    c.read(fname)
    return dict((c, c.items(c)) for c in c.sections())

def main():
    env = os.environ
    cfg = get_config_parser(env)
    _main(env, cfg)

def _main(env, file_cfg):
    app = argvard.Argvard()

    sync = argvard.Command()
    @sync_command.main('[accounts...]')
    def sync_main(accounts=None):
        if accounts is None:
            accounts = list(file_cfg.keys())
        for account in accounts:
            account_cfg = dict(file_cfg[account])
            del account_cfg['type']
            syncer = sync_classes[account_cfg['type']](**account_cfg)
            syncer.run()
