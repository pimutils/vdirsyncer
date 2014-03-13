# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.test_utils
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import vdirsyncer.utils as utils

def test_parse_options():
    o = {
        'foo': 'yes',
        'bar': '',
        'baz': 'whatever',
        'bam': '123',
        'asd': 'off'
    }

    assert dict(utils.parse_options(o.items())) == {
        'foo': True,
        'bar': '',
        'baz': 'whatever',
        'bam': 123,
        'asd': False
    }
