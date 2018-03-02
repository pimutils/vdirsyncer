# -*- coding: utf-8 -*-

from itertools import chain, tee

from .utils import cached_property, uniq
from . import native


class Item(object):

    '''Immutable wrapper class for VCALENDAR (VEVENT, VTODO) and
    VCARD'''

    def __init__(self, raw, _native=None):
        if raw is None:
            assert _native
            self._native = _native
            return

        assert isinstance(raw, str), type(raw)
        assert _native is None
        self._native = native.item_rv(
            native.lib.vdirsyncer_item_from_raw(raw.encode('utf-8'))
        )

    def with_uid(self, new_uid):
        new_uid = new_uid or ''
        assert isinstance(new_uid, str), type(new_uid)

        e = native.get_error_pointer()
        rv = native.lib.vdirsyncer_with_uid(self._native,
                                            new_uid.encode('utf-8'),
                                            e)
        native.check_error(e)
        return Item(None, _native=native.item_rv(rv))

    @cached_property
    def is_parseable(self):
        return native.lib.vdirsyncer_item_is_parseable(self._native)

    @cached_property
    def raw(self):
        return native.string_rv(native.lib.vdirsyncer_get_raw(self._native))

    @cached_property
    def uid(self):
        rv = native.string_rv(native.lib.vdirsyncer_get_uid(self._native))
        return rv or None

    @cached_property
    def hash(self):
        e = native.get_error_pointer()
        rv = native.lib.vdirsyncer_get_hash(self._native, e)
        native.check_error(e)
        return native.string_rv(rv)

    @cached_property
    def ident(self):
        return self.uid or self.hash


def split_collection(text):
    assert isinstance(text, str)
    inline = []
    items = {}  # uid => item
    ungrouped_items = []

    for main in _Component.parse(text, multiple=True):
        _split_collection_impl(main, main, inline, items, ungrouped_items)

    for item in chain(items.values(), ungrouped_items):
        item.subcomponents.extend(inline)
        yield u'\r\n'.join(item.dump_lines())


def _split_collection_impl(item, main, inline, items, ungrouped_items):
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
        if item.name == 'VCALENDAR':
            del item['METHOD']
        for subitem in item.subcomponents:
            _split_collection_impl(subitem, item, inline, items,
                                   ungrouped_items)
    else:
        raise ValueError('Unknown component: {}'
                         .format(item.name))


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
        if isinstance(lines, str):
            lines = lines.splitlines()

        stack = []
        rv = []
        try:
            for _i, line in enumerate(lines):
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
            raise ValueError('Parsing error at line {}'.format(_i + 1))

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
        prefix = (u'{}:'.format(key), u'{};'.format(key))
        new_lines = []
        lineiter = iter(self.props)
        while True:
            for line in lineiter:
                if line.startswith(prefix):
                    break
                else:
                    new_lines.append(line)
            else:
                break

            for line in lineiter:
                if not line.startswith((u' ', u'\t')):
                    new_lines.append(line)
                    break

        self.props = new_lines

    def __setitem__(self, key, val):
        assert isinstance(val, str)
        assert u'\n' not in val
        del self[key]
        line = u'{}:{}'.format(key, val)
        self.props.append(line)

    def __contains__(self, obj):
        if isinstance(obj, type(self)):
            return obj not in self.subcomponents and \
                not any(obj in x for x in self.subcomponents)
        elif isinstance(obj, str):
            return self.get(obj, None) is not None
        else:
            raise ValueError(obj)

    def __getitem__(self, key):
        prefix_without_params = '{}:'.format(key)
        prefix_with_params = '{};'.format(key)
        iterlines = iter(self.props)
        for line in iterlines:
            if line.startswith(prefix_without_params):
                rv = line[len(prefix_without_params):]
                break
            elif line.startswith(prefix_with_params):
                rv = line[len(prefix_with_params):].split(':', 1)[-1]
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

    def __eq__(self, other):
        return (
            isinstance(other, type(self)) and
            self.name == other.name and
            self.props == other.props and
            self.subcomponents == other.subcomponents
        )
