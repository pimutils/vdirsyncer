# -*- coding: utf-8 -*-

import hashlib
from itertools import chain, tee

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
        # Don't actually parse component, but treat all lines as single
        # component, avoiding traversal through all subcomponents.
        x = _Component('TEMP', self.raw.splitlines(), [])
        try:
            return x['UID'].strip() or None
        except KeyError:
            return None

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
            return _Component.parse(self.raw)
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
    collections = _Component.parse(text, multiple=True)
    collection_name = None

    for collection in collections:
        if collection_name is None:
            collection_name = collection.name
            start = end = ()
            if collection_name in wrap_items_with:
                start = (u'BEGIN:{0}'.format(collection_name),)
                end = (u'END:{0}'.format(collection_name),)

        elif collection.name != collection_name:
            raise ValueError('Different types of components at top-level. '
                             'Expected {0}, got {1}.'
                             .format(collection_name, collection.name))

        inlined_items, normal_items = split_sequence(
            collection.subcomponents,
            lambda item: item.name in inline
        )
        inlined_lines = list(chain(*(inlined_item.dump_lines()
                                     for inlined_item in inlined_items)))

        for item in normal_items:
            lines = chain(start, inlined_lines, item.dump_lines(), end)
            yield u''.join(line + u'\r\n' for line in lines if line)


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

    items1, items2 = tee((_Component.parse(x)
                          for x in items), 2)
    item_type, wrapper_type = _get_item_type(items1, wrappers)

    def _get_item_components(x):
        return x.name == wrapper_type and x.subcomponents or [x]

    components = chain(*(_get_item_components(x) for x in items2))
    lines = chain(*uniq(tuple(x.dump_lines()) for x in components))

    if wrapper_type is not None:
        start = [u'BEGIN:{0}'.format(wrapper_type)]
        end = [u'END:{0}'.format(wrapper_type)]
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


class _Component(object):
    '''
    Raw outline of the components.

    Vdirsyncer's operations on iCalendar and VCard objects are limited to
    retrieving the UID and splitting larger files into items. Consequently this
    parser is very lazy, with the downside that manipulation of item properties
    are extremely costly.

    Other features:

    - Preserve the original property order and wrapping.
    - Don't choke on irrelevant details like invalid datetime formats.

    Original version from https://github.com/collective/icalendar/, but apart
    from the similar API, very few parts have been reused.
    '''

    def __init__(self, name, lines, subcomponents):
        '''
        :param name: The component name.
        :param lines: The component's own properties, as list of lines
            (strings).
        :param subcomponents: List of components.
        '''
        self.name = name
        self.lines = lines
        self.subcomponents = subcomponents

    @classmethod
    def parse(cls, lines, multiple=False):
        if isinstance(lines, bytes):
            lines = lines.decode('utf-8')
        if isinstance(lines, text_type):
            lines = lines.splitlines()

        stack = []
        rv = []
        for line in lines:
            if line.startswith(u'BEGIN:'):
                c_name = line[len(u'BEGIN:'):].strip().upper()
                stack.append(cls(c_name, [], []))
            elif line.startswith(u'END:'):
                component = stack.pop()
                if stack:
                    stack[-1].subcomponents.append(component)
                else:
                    rv.append(component)
            else:
                if line.strip():
                    stack[-1].lines.append(line)

        if multiple:
            return rv
        elif len(rv) != 1:
            raise ValueError('Found {0} components, expected one.'
                             .format(len(rv)))
        else:
            return rv[0]

    def dump_lines(self):
        yield u'BEGIN:{0}'.format(self.name)
        for line in self.lines:
            yield line
        for c in self.subcomponents:
            for line in c.dump_lines():
                yield line
        yield u'END:{0}'.format(self.name)

    def __delitem__(self, key):
        prefix = u'{0}:'.format(key)
        new_lines = []
        lineiter = iter(self.lines)
        for line in lineiter:
            if line.startswith(prefix):
                break
            else:
                new_lines.append(line)

        for line in lineiter:
            if not line.startswith((u' ', u'\t')):
                new_lines.append(line)
                break

        new_lines.extend(lineiter)
        self.lines = new_lines

    def __setitem__(self, key, val):
        del self[key]
        line = u'{0}:{1}'.format(key, val)
        self.lines.append(line)

    def __getitem__(self, key):
        prefix = u'{0}:'.format(key)
        iterlines = iter(self.lines)
        for line in iterlines:
            if line.startswith(prefix):
                rv = line[len(prefix):]
                break
        else:
            raise KeyError()

        for line in iterlines:
            if line.startswith((u' ', u'\t')):
                rv += line[1:]
            else:
                break

        return rv
