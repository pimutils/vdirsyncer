# -*- coding: utf-8 -*-

import hashlib
from itertools import chain, tee

from . import cached_property, uniq
from .compat import itervalues, text_type


def _process_properties(*s):
    rv = set()
    for key in s:
        rv.add(key + ':')
        rv.add(key + ';')

    return tuple(rv)

IGNORE_PROPS = _process_properties(
    # PRODID is changed by radicale for some reason after upload
    'PRODID',
    # X-RADICALE-NAME is used by radicale, because hrefs don't really exist in
    # their filesystem backend
    'X-RADICALE-NAME',
    # Apparently this is set by Horde?
    # https://github.com/pimutils/vdirsyncer/issues/318
    'X-WR-CALNAME',
    # REV is from the VCARD specification and is supposed to change when the
    # item does -- however, we can determine that ourselves
    # Same with LAST-MODIFIED
    'REV',
    'LAST-MODIFIED',
    # Added those because e.g. http://www.feiertage-oesterreich.at/ is
    # generating those randomly on every request.
    # Some iCalendar HTTP calendars (Google's read-only calendar links)
    # generate the DTSTAMP at request time, so this property always changes
    # when the rest of the item didn't.
    # Some do the same with the UID.
    'DTSTAMP',
    'UID',
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


def split_collection(text):
    assert isinstance(text, text_type)
    inline = []
    items = {}  # uid => item
    ungrouped_items = []

    def inner(item, main):
        if item.name == u'VTIMEZONE':
            inline.append(item)
        elif item.name == u'VCARD':
            ungrouped_items.append(item)
        elif item.name in (u'VTODO', u'VEVENT', u'VJOURNAL'):
            uid = item.get(u'UID', u'')
            wrapper = _Component(main.name, main.props[:], [])

            if uid.strip():
                wrapper = items.setdefault(uid, wrapper)
            else:
                ungrouped_items.append(wrapper)

            wrapper.subcomponents.append(item)
        elif item.name in (u'VCALENDAR', u'VADDRESSBOOK'):
            for subitem in item.subcomponents:
                inner(subitem, item)
        else:
            raise ValueError('Unknown component: {}'
                             .format(item.name))

    for main in _Component.parse(text, multiple=True):
        inner(main, main)

    for item in chain(itervalues(items), ungrouped_items):
        item.subcomponents.extend(inline)
        yield u'\r\n'.join(item.dump_lines())

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
    wrapper_props = []

    def _get_item_components(x):
        if x.name == wrapper_type:
            wrapper_props.extend(x.props)
            return x.subcomponents
        else:
            return [x]

    components = chain(*(_get_item_components(x) for x in items2))
    lines = chain(*uniq(tuple(x.dump_lines()) for x in components))

    if wrapper_type is not None:
        lines = chain(*(
            [u'BEGIN:{}'.format(wrapper_type)],
            # XXX: wrapper_props is a list of lines (with line-wrapping), so
            # filtering out duplicate lines will almost certainly break
            # multiline-values.  Since the only props we usually need to
            # support are PRODID and VERSION, I don't care.
            uniq(wrapper_props),
            lines,
            [u'END:{}'.format(wrapper_type)]
        ))
    return u''.join(line + u'\r\n' for line in lines)


def _get_item_type(components, wrappers):
    i = 0
    for component in components:
        i += 1
        try:
            item_type = component.name
            wrapper_type = wrappers[item_type]
        except KeyError:
            pass
        else:
            return item_type, wrapper_type

    if not i:
        return None, None
    else:
        raise ValueError('Not sure how to join components.')


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
        self.props = lines
        self.subcomponents = subcomponents

    @classmethod
    def parse(cls, lines, multiple=False):
        if isinstance(lines, bytes):
            lines = lines.decode('utf-8')
        if isinstance(lines, text_type):
            lines = lines.splitlines()

        stack = []
        rv = []
        try:
            for i, line in enumerate(lines):
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
                        stack[-1].props.append(line)
        except IndexError:
            raise ValueError('Parsing error at line {}. Check the debug log '
                             'for more information.'.format(i + 1))

        if multiple:
            return rv
        elif len(rv) != 1:
            raise ValueError('Found {} components, expected one.'
                             .format(len(rv)))
        else:
            return rv[0]

    def dump_lines(self):
        yield u'BEGIN:{}'.format(self.name)
        for line in self.props:
            yield line
        for c in self.subcomponents:
            for line in c.dump_lines():
                yield line
        yield u'END:{}'.format(self.name)

    def __delitem__(self, key):
        prefix = u'{}:'.format(key)
        new_lines = []
        lineiter = iter(self.props)
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
        self.props = new_lines

    def __setitem__(self, key, val):
        assert isinstance(val, text_type)
        assert u'\n' not in val
        del self[key]
        line = u'{}:{}'.format(key, val)
        self.props.append(line)

    def __getitem__(self, key):
        prefix = u'{}:'.format(key)
        iterlines = iter(self.props)
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

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
