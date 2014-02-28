# -*- coding: utf-8 -*-
'''
    vdirsyncer.exceptions
    ~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''


class Error(Exception):

    '''Baseclass for all errors.'''


class PreconditionFailed(Error):

    '''
      - The item doesn't exist although it should
      - The item exists although it shouldn't
      - The etags don't match.

    Due to CalDAV we can't actually say which error it is.
    This error may indicate race conditions.
    '''


class NotFoundError(PreconditionFailed):

    '''Item not found'''


class AlreadyExistingError(PreconditionFailed):

    '''Item already exists'''


class WrongEtagError(PreconditionFailed):

    '''Wrong etag'''


class StorageError(Error):

    '''Internal or initialization errors with storage.'''


class SyncError(Error):
    pass


class SyncConflict(SyncError):
    pass
