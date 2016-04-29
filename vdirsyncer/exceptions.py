# -*- coding: utf-8 -*-
'''
Contains exception classes used by vdirsyncer. Not all exceptions are here,
only the most commonly used ones.
'''


class Error(Exception):
    '''Baseclass for all errors.'''

    def __init__(self, *args, **kwargs):
        for key, value in kwargs.items():
            if getattr(self, key, object()) is not None:  # pragma: no cover
                raise TypeError('Invalid argument: {}'.format(key))
            setattr(self, key, value)

        super(Error, self).__init__(*args)


class UserError(Error, ValueError):
    '''Wrapper exception to be used to signify the traceback should not be
    shown to the user.'''

    problems = None

    def __str__(self):
        msg = Error.__str__(self)
        for problem in self.problems or ():
            msg += u'\n  - {}'.format(problem)

        return msg


class CollectionNotFound(Error):
    '''Collection not found'''


class PairNotFound(Error):
    '''Pair not found'''

    pair_name = None


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
    '''Item already exists.'''
    existing_href = None


class WrongEtagError(PreconditionFailed):
    '''Wrong etag'''


class ReadOnlyError(Error):
    '''Storage is read-only.'''


class InvalidResponse(Error, ValueError):
    '''The backend returned an invalid result.'''


class UnsupportedMetadataError(Error, NotImplementedError):
    '''The storage doesn't support this type of metadata.'''
