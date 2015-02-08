# -*- coding: utf-8 -*-

import hashlib
from itertools import chain, tee

import icalendar.cal
import icalendar.caselessdict
import icalendar.parser

from . import cached_property, split_sequence, uniq
from .compat import text_type


def _process_properties(*s):
    rv = set()
    for key in s:
        rv.add(key + ':')
        rv.add(key + ';')

    return tuple(rv)

IGNORE_PROPS = _process_properties(
    # PRODID is changed by radicale for some reason after upload
    'PRODID',
    # VERSION can get lost in singlefile storage
    'VERSION',
    # X-RADICALE-NAME is used by radicale, because hrefs don't really exist in
    # their filesystem backend
    'X-RADICALE-NAME',
    # REV is from the VCARD specification and is supposed to change when the
    # item does -- however, we can determine that ourselves
    'REV'
)
del _process_properties


# Whether the installed icalendar version has
# https://github.com/collective/icalendar/pull/136
# (support for keeping the order of properties and parameters)
#
# This basically checks whether the superclass of all icalendar classes has a
# method from OrderedDict.
ICALENDAR_ORIGINAL_ORDER_SUPPORT = \
    hasattr(icalendar.caselessdict.CaselessDict, '__reversed__')


class Item(object):

    '''Immutable wrapper class for VCALENDAR (VEVENT, VTODO) and
    VCARD'''

    def __init__(self, raw):
        assert isinstance(raw, text_type)
        self._raw = raw

    @cached_property
    def raw(self):
        '''Raw content of the item, as unicode string.

        Vdirsyncer doesn't validate the content in any way.
        '''
        return self._raw

    @cached_property
    def uid(self):
        '''Global identifier of the item, across storages, doesn't change after
        a modification of the item.'''
        stack = [self.parsed]
        while stack:
            component = stack.pop()
            if component is None:
                continue
            uid = component.get('UID', None)
            if uid:
                return uid
            stack.extend(component.subcomponents)

        for line in self.raw.splitlines():
            if line.startswith(u'UID:'):
                uid = line[4:].strip()
                if uid:
                    return uid

    @cached_property
    def hash(self):
        '''Hash of self.raw, used for etags.'''
        return hash_item(self.raw)

    @cached_property
    def ident(self):
        '''Used for generating hrefs and matching up items during
        synchronization. This is either the UID or the hash of the item's
        content.'''

        # We hash the item instead of directly using its raw content, because
        #
        # 1. The raw content might be really large, e.g. when its a contact
        #    with a picture, which bloats the status file.
        #
        # 2. The status file would contain really sensitive information.
        return self.uid or self.hash

    @cached_property
    def parsed(self):
        try:
            return icalendar.cal.Component.from_ical(self.raw)
        except Exception:
            return None


def normalize_item(item, ignore_props=IGNORE_PROPS):
    '''Create syntactically invalid mess that is equal for similar items.'''
    if not isinstance(item, Item):
        item = Item(item)
    return u'\r\n'.join(line.strip()
                        for line in sorted(item.raw.splitlines())
                        if line.strip() and
                        not line.startswith(IGNORE_PROPS))


def hash_item(text):
    return hashlib.sha256(normalize_item(text).encode('utf-8')).hexdigest()


def split_collection(text, inline=(u'VTIMEZONE',),
                     wrap_items_with=(u'VCALENDAR',)):
    '''Emits items in the order they occur in the text.'''
    assert isinstance(text, text_type)
    collections = icalendar.cal.Component.from_ical(text, multiple=True)
    collection_name = None

    for collection in collections:
        if collection_name is None:
            collection_name = collection.name
            start = end = ()
            if collection_name in wrap_items_with:
                start = (u'BEGIN:{}'.format(collection_name),)
                end = (u'END:{}'.format(collection_name),)

        elif collection.name != collection_name:
            raise ValueError('Different types of components at top-level. '
                             'Expected {}, got {}.'
                             .format(collection_name, collection.name))

        inlined_items, normal_items = split_sequence(
            collection.subcomponents,
            lambda item: item.name in inline
        )
        inlined_lines = list(chain(*(to_unicode_lines(inlined_item)
                                     for inlined_item in inlined_items)))

        for item in normal_items:
            lines = chain(start, inlined_lines, to_unicode_lines(item), end)
            yield u''.join(line + u'\r\n' for line in lines if line)


def to_unicode_lines(item):
    '''icalendar doesn't provide an efficient way of getting the ical data as
    unicode. So let's do it ourselves.'''

    if ICALENDAR_ORIGINAL_ORDER_SUPPORT:
        content_lines = item.content_lines(sorted=False)
    else:
        content_lines = item.content_lines()

    for content_line in content_lines:
        if content_line:
            # https://github.com/untitaker/vdirsyncer/issues/70
            # XXX: icalendar escapes semicolons which are not supposed to get
            # escaped, because it is not aware of vcard
            content_line = content_line.replace(u'\\;', u';')
            yield icalendar.parser.foldline(content_line)


_default_join_wrappers = {
    u'VCALENDAR': u'VCALENDAR',
    u'VEVENT': u'VCALENDAR',
    u'VTODO': u'VCALENDAR',
    u'VCARD': u'VADDRESSBOOK'
}


def join_collection(items, wrappers=_default_join_wrappers):
    '''
    :param wrappers: {
        item_type: wrapper_type
    }
    '''

    items1, items2 = tee((icalendar.cal.Component.from_ical(x)
                          for x in items), 2)
    item_type, wrapper_type = _get_item_type(items1, wrappers)

    def _get_item_components(x):
        return x.name == wrapper_type and x.subcomponents or [x]

    components = chain(*(_get_item_components(x) for x in items2))
    lines = chain(*uniq(tuple(to_unicode_lines(x)) for x in components))

    if wrapper_type is not None:
        start = [u'BEGIN:{}'.format(wrapper_type)]
        end = [u'END:{}'.format(wrapper_type)]
        lines = chain(start, lines, end)
    return u''.join(line + u'\r\n' for line in lines)


def _get_item_type(components, wrappers):
    for component in components:
        try:
            item_type = component.name
            wrapper_type = wrappers[item_type]
        except KeyError:
            pass
        else:
            return item_type, wrapper_type
    return None, None
