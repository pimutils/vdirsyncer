# -*- coding: utf-8 -*-
'''
Contains exception classes used by vdirsyncer. Not all exceptions are here,
only the most commonly used ones.
'''


class Error(Exception):
    '''Baseclass for all errors.'''

    def __init__(self, *args, **kwargs):
        for key, value in kwargs.items():
            if getattr(self, key, object()) is not None:
                raise TypeError('Invalid argument: {}'.format(key))
            setattr(self, key, value)

        super(Error, self).__init__(*args)


class CollectionNotFound(Error):
    '''Collection not found'''


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


class ReadOnlyError(Error):
    '''Storage is read-only.'''


class InvalidResponse(Error, ValueError):
    '''The backend returned an invalid result.'''
