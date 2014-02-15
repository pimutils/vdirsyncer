# -*- coding: utf-8 -*-
'''
    vdirsyncer.exceptions
    ~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

class Error(Exception):
    '''Baseclass for all errors.'''
    pass

class NotFoundError(Error):
    '''The item does not exist (anymore).'''
    pass

class AlreadyExistingError(Error):
    '''The item exists although it shouldn't, possible race condition.'''
    pass

class WrongEtagError(Error):
    '''The given etag doesn't match the etag from the storage, possible race
    condition.'''
    pass
