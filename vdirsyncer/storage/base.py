# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.base
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

class Item(object):
    '''should-be-immutable wrapper class for VCALENDAR and VCARD'''
    def __init__(self, raw):
        self.raw = raw
        self._uid = None

    @property
    def uid(self):
        if self._uid is None:
            for line in self.raw.splitlines():
                if line.startswith(b'UID'):
                    self._uid = line.lstrip(b'UID:').strip()
        return self._uid


class Storage(object):
    '''Superclass of all storages, mainly useful to summarize the interface to
    implement.'''
    def __init__(self, fileext='', item_class=Item):
        self.fileext = fileext
        self.item_class = item_class

    def list(self):
        '''
        :returns: list of (uid, etag)
        '''
        raise NotImplementedError()

    def get(self, uid):
        '''
        :param uid: uid to fetch
        :returns: (object, etag)
        '''
        raise NotImplementedError()

    def get_multi(self, uids):
        '''
        :param uids: list of uids to fetch
        :returns: iterable of (uid, obj, etag)
        '''
        for uid in uids:
            obj, etag = self.get(uid)
            yield uid, obj, etag

    def has(self, uid):
        '''
        check if item exists
        :returns: True or False
        '''
        raise NotImplementedError()

    def upload(self, obj):
        '''
        Upload a new object, raise
        :exc:`vdirsyncer.exceptions.AlreadyExistingError` if it already exists.
        :returns: etag on the server
        '''
        raise NotImplementedError()

    def update(self, obj, etag):
        '''
        Update the object, raise :exc:`vdirsyncer.exceptions.WrongEtagError` if
        the etag on the server doesn't match the given etag, raise
        :exc:`vdirsyncer.exceptions.NotFoundError` if the item doesn't exist.

        :returns: etag on the server
        '''
        raise NotImplementedError()

    def delete(self, uid, etag):
        '''
        Delete the object, raise exceptions when etag doesn't match, no return
        value
        '''
        raise NotImplementedError()
