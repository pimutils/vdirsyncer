# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.dav._owncloud
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Using utilities from paste to wrap the PHP application into WSGI.

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from paste.cgiapp import CGIApplication
from vdirsyncer.utils import expand_path
from ._radicale import wsgi_setup
import subprocess
import os

owncloud_repo = expand_path(os.path.join(os.path.dirname(__file__), '../../../owncloud-testserver/'))
app = CGIApplication(None, 'php.cgi', [owncloud_repo], include_os_environ=False, query_string=None)

def middleware(environ, start_response):
    print(environ)
    environ['REQUEST_URI'] = 'http://127.0.0.1' + environ['PATH_INFO']
    return app(environ, start_response)

class ServerMixin(object):
    storage_class = None
    wsgi_teardown = None

    def setup_method(self, method):
        subprocess.call([os.path.join(owncloud_repo, 'install.sh')])
        self.wsgi_teardown = wsgi_setup(middleware)

    def get_storage_args(self, collection='test'):
        assert self.storage_class.fileext in ('.ics', '.vcf')
        if self.storage_class.fileext == '.vcf':
            url = 'http://127.0.0.1/remote.php/carddav/addressbooks/asdf/'
        else:
            url = 'http://127.0.0.1/remote.php/carddav/addressbooks/asdf/'
        if collection is not None:
            assert collection in ('test', 'test1', 'test2', 'test3', 'test4',
                                  'test5', 'test6', 'test7', 'test8', 'test9',
                                  'test10')

        return {'url': url, 'collection': collection}

    def teardown_method(self, method):
        if self.wsgi_teardown is not None:
            self.wsgi_teardown()
            self.wsgi_teardown = None
