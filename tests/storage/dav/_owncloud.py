# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.dav._owncloud
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Using utilities from paste to wrap the PHP application into WSGI.

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from vdirsyncer.utils import expand_path
import subprocess
import os

owncloud_repo = expand_path(os.path.join(os.path.dirname(__file__), '../../../owncloud-testserver/'))

class ServerMixin(object):
    storage_class = None
    wsgi_teardown = None

    def setup_method(self, method):
        subprocess.call([os.path.join(owncloud_repo, 'install.sh')])

    def get_storage_args(self, collection='test'):
        assert self.storage_class.fileext in ('.ics', '.vcf')
        url = 'http://127.0.0.1:8080'
        if self.storage_class.fileext == '.vcf':
            url += '/remote.php/carddav/addressbooks/asdf/'
        else:
            url += '/remote.php/carddav/addressbooks/asdf/'
        if collection is not None:
            # the following collections are setup in ownCloud
            assert collection in ('test', 'test1', 'test2', 'test3', 'test4',
                                  'test5', 'test6', 'test7', 'test8', 'test9',
                                  'test10')

            return {'url': url, 'collection': collection, 'username': 'asdf', 'password': 'asdf'}
