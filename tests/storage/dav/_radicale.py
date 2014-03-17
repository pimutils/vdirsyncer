# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.dav._radicale
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Using the Radicale CalDAV/CardDAV server to test the CalDAV and CardDAV
    storages. Done by using Werkzeug's test client for WSGI apps. While this is
    pretty fast, Radicale has so much global state such that a clean separation
    of the unit tests is not easy.

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import sys
import os
import urlparse
import tempfile
import shutil
import mock

from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse as WerkzeugResponse

import vdirsyncer.exceptions as exceptions
from vdirsyncer.storage.base import Item

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
    radicale.config.set('rights', 'type', 'None')

    if os.environ.get('RADICALE_STORAGE', 'filesystem') == 'filesystem':
        radicale.config.set('storage', 'type', 'filesystem')
        radicale.config.set('storage', 'filesystem_folder', tmpdir)
    else:
        radicale.config.set('storage', 'type', 'database')
        radicale.config.set('storage', 'database_url', 'sqlite://')
        from radicale.storage import database

        s = database.Session()
        for line in RADICALE_SCHEMA.split(';'):
            s.execute(line)
        s.commit()

    # This one is particularly useful with radicale's debugging logs and
    # pytest-capturelog, however, it is very verbose.
    #import radicale.log
    #radicale.log.start()


class Response(object):

    '''Fake API of requests module'''

    def __init__(self, x):
        self.x = x
        self.status_code = x.status_code
        self.content = x.get_data(as_text=False)
        self.text = x.get_data(as_text=True)
        self.headers = x.headers
        self.encoding = x.charset

    def raise_for_status(self):
        '''copied from requests itself'''
        if 400 <= self.status_code < 600:
            from requests.exceptions import HTTPError
            raise HTTPError(str(self.status_code))


class ServerMixin(object):
    '''hrefs are paths without scheme or netloc'''
    storage_class = None
    patcher = None
    tmpdir = None

    def setup_method(self, method):
        self.tmpdir = tempfile.mkdtemp()
        do_the_radicale_dance(self.tmpdir)
        from radicale import Application
        app = Application()

        c = Client(app, WerkzeugResponse)

        def x(session, method, url, data=None, headers=None, **kw):
            path = urlparse.urlparse(url).path
            assert isinstance(data, bytes) or data is None
            r = c.open(path=path, method=method, data=data, headers=headers)
            r = Response(r)
            return r

        self.patcher = p = mock.patch('requests.Session.request', new=x)
        p.start()

    def get_storage_args(self, collection='test'):
        url = 'http://127.0.0.1/bob/'
        if collection is not None:
            collection += self.storage_class.fileext
        return {'url': url, 'collection': collection}

    def teardown_method(self, method):
        self.app = None
        if self.tmpdir is not None:
            shutil.rmtree(self.tmpdir)
            self.tmpdir = None
        if self.patcher is not None:
            self.patcher.stop()
            self.patcher = None

    def test_dav_broken_item(self):
        item = Item(u'UID:1')
        s = self._get_storage()
        try:
            s.upload(item)
        except exceptions.Error:
            pass
        assert not list(s.list())
