# -*- coding: utf-8 -*-

import os
import sys

import pytest

import wsgi_intercept
import wsgi_intercept.requests_intercept

wsgi_intercept.requests_intercept.install()


RADICALE_SCHEMA = '''
create table collection (
       path varchar(200) not null,
       parent_path varchar(200) references collection (path),
       primary key (path));

create table item (
       name varchar(200) not null,
       tag text not null,
       collection_path varchar(200) references collection (path),
       primary key (name));

create table header (
       name varchar(200) not null,
       value text not null,
       collection_path varchar(200) references collection (path),
       primary key (name, collection_path));

create table line (
       name text not null,
       value text not null,
       item_name varchar(200) references item (name),
       timestamp bigint not null,
       primary key (timestamp));

create table property (
       name varchar(200) not null,
       value text not null,
       collection_path varchar(200) references collection (path),
       primary key (name, collection_path));
'''.split(';')

storage_backend = os.environ.get('RADICALE_BACKEND', '') or 'filesystem'


def do_the_radicale_dance(tmpdir):
    # All of radicale is already global state, the cleanliness of the code and
    # all hope is already lost. This function runs before every test.

    # This wipes out the radicale modules, to reset all of its state.
    for module in list(sys.modules):
        if module.startswith('radicale'):
            del sys.modules[module]

    # radicale.config looks for this envvar. We have to delete it before it
    # tries to load a config file.
    os.environ['RADICALE_CONFIG'] = ''
    import radicale.config

    # Now we can set some basic configuration.
    radicale.config.set('rights', 'type', 'owner_only')
    radicale.config.set('auth', 'type', 'http')

    import radicale.auth.http

    def is_authenticated(user, password):
        return user == 'bob' and password == 'bob'
    radicale.auth.http.is_authenticated = is_authenticated

    if storage_backend == 'filesystem':
        radicale.config.set('storage', 'type', 'filesystem')
        radicale.config.set('storage', 'filesystem_folder', tmpdir)
    elif storage_backend == 'database':
        radicale.config.set('storage', 'type', 'database')
        radicale.config.set('storage', 'database_url', 'sqlite://')
        from radicale.storage import database

        s = database.Session()
        for line in RADICALE_SCHEMA:
            s.execute(line)
        s.commit()
    else:
        raise RuntimeError()


class ServerMixin(object):

    @pytest.fixture(autouse=True)
    def setup(self, request, tmpdir):
        do_the_radicale_dance(str(tmpdir))
        from radicale import Application

        wsgi_intercept.add_wsgi_intercept('127.0.0.1', 80, Application)

        def teardown():
            wsgi_intercept.remove_wsgi_intercept('127.0.0.1', 80)
        request.addfinalizer(teardown)

    def get_storage_args(self, collection='test'):
        url = 'http://127.0.0.1/bob/'
        if collection is not None:
            collection += self.storage_class.fileext

        return {'url': url, 'username': 'bob', 'password': 'bob',
                'collection': collection, 'unsafe_href_chars': ''}
