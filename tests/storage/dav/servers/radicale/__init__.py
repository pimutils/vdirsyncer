# -*- coding: utf-8 -*-

import sys
import os
import pytest
from vdirsyncer.utils import urlparse

from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse as WerkzeugResponse


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
'''

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
        assert user == 'bob' and password == 'bob'
        return True
    radicale.auth.http.is_authenticated = is_authenticated

    if storage_backend == 'filesystem':
        radicale.config.set('storage', 'type', 'filesystem')
        radicale.config.set('storage', 'filesystem_folder', tmpdir)
    elif storage_backend == 'database':
        radicale.config.set('storage', 'type', 'database')
        radicale.config.set('storage', 'database_url', 'sqlite://')
        from radicale.storage import database

        s = database.Session()
        for line in RADICALE_SCHEMA.split(';'):
            s.execute(line)
        s.commit()
    else:
        raise RuntimeError()


class ServerMixin(object):

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch, tmpdir):
        do_the_radicale_dance(str(tmpdir))
        from radicale import Application
        app = Application()
        c = Client(app, WerkzeugResponse)

        from requests import Response

        def send(self, request, *args, **kwargs):
            path = urlparse.urlparse(request.url).path
            wr = c.open(path=path, method=request.method,
                        data=request.body, headers=dict(request.headers))
            r = Response()
            r.request = request
            r._content = wr.get_data(as_text=False)
            r.headers = wr.headers
            r.encoding = wr.charset
            r.status_code = wr.status_code
            return r

        monkeypatch.setattr('requests.adapters.HTTPAdapter.send', send)

    def get_storage_args(self, collection='test'):
        url = 'http://127.0.0.1/bob/'
        if collection is not None:
            collection += self.storage_class.fileext

        return {'url': url, 'username': 'bob', 'password': 'bob',
                'collection': collection}
