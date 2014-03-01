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
        assert type(raw) is unicode
        raw = raw.splitlines()
        self.uid = None

        for line in raw:
            if line.startswith(u'UID:'):
                self.uid = line[4:].strip()
        self.raw = u'\n'.join(raw)


class Storage(object):

    '''Superclass of all storages, mainly useful to summarize the interface to
    implement.

    Terminology:
      - UID: Global identifier of the item, across storages.
      - HREF: Per-storage identifier of item, might be UID.
      - ETAG: Checksum of item, or something similar that changes when the
              object does.
    '''
    fileext = '.txt'
    _repr_attributes = ()

    def __init__(self, item_class=Item):
        self.item_class = item_class

    def _get_href(self, uid):
        return uid + self.fileext

    def __repr__(self):
        return '<{}(**{})>'.format(
            self.__class__.__name__,
            dict((x, getattr(self, x)) for x in self._repr_attributes)
        )

    def list(self):
        '''
        :returns: list of (href, etag)
        '''
        raise NotImplementedError()

    def get(self, href):
        '''
        :param href: href to fetch
        :returns: (object, etag)
        '''
        raise NotImplementedError()

    def get_multi(self, hrefs):
        '''
        :param hrefs: list of hrefs to fetch
        :raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` if one of the
        items couldn't be found.
        :returns: iterable of (href, obj, etag)
        '''
        for href in hrefs:
            obj, etag = self.get(href)
            yield href, obj, etag

    def has(self, href):
        '''
        check if item exists by href
        :returns: True or False
        '''
        raise NotImplementedError()

    def upload(self, obj):
        '''
        Upload a new object, raise
        :exc:`vdirsyncer.exceptions.PreconditionFailed` if it already exists.
        :returns: (href, etag)
        '''
        raise NotImplementedError()

    def update(self, href, obj, etag):
        '''
        Update the object, raise
        :exc:`vdirsyncer.exceptions.PreconditionFailed` if the etag on the
        server doesn't match the given etag or if the item doesn't exist.

        :returns: etag
        '''
        raise NotImplementedError()

    def delete(self, href, etag):
        '''
        Delete the object by href, raise
        :exc:`vdirsyncer.exceptions.PreconditionFailed` when item has a
        different etag or doesn't exist.
        '''
        raise NotImplementedError()
