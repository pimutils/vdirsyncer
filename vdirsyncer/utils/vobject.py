# -*- coding: utf-8 -*-
'''
    vdirsyncer.utils.vobject
    ~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
import hashlib

import icalendar.cal
import icalendar.parser

from . import text_type, itervalues


def hash_item(text):
    try:
        lines = to_unicode_lines(icalendar.cal.Component.from_ical(text))
    except Exception:
        lines = sorted(text.splitlines())

    hashable = u'\r\n'.join(line.strip() for line in lines
                            if line.strip() and
                            u'PRODID' not in line and
                            u'VERSION' not in line)
    return hashlib.sha256(hashable.encode('utf-8')).hexdigest()


def split_collection(text, inline=(u'VTIMEZONE',),
                     wrap_items_with=(u'VCALENDAR',)):
    '''Emits items in the order they occur in the text.'''
    assert isinstance(text, text_type)
    collection = icalendar.cal.Component.from_ical(text)
    items = collection.subcomponents

    if collection.name in wrap_items_with:
        start = u'BEGIN:{}'.format(collection.name)
        end = u'END:{}'.format(collection.name)
    else:
        start = end = u''

    inlined_items = {}
    for item in items:
        if item.name in inline:
            inlined_items[item.name] = item

    for item in items:
        if item.name not in inline:
            lines = []
            lines.append(start)
            for inlined_item in itervalues(inlined_items):
                lines.extend(to_unicode_lines(inlined_item))

            lines.extend(to_unicode_lines(item))
            lines.append(end)

            yield u''.join(line + u'\r\n' for line in lines if line)


def to_unicode_lines(item):
    '''icalendar doesn't provide an efficient way of getting the ical data as
    unicode. So let's do it ourselves.'''

    for content_line in item.content_lines():
        if content_line:
            yield icalendar.parser.foldline(content_line)


def join_collection(items, wrapper=None):
    timezones = {}
    components = []

    for item in items:
        component = icalendar.cal.Component.from_ical(item)
        if component.name == u'VCALENDAR':
            assert wrapper is None or wrapper == u'VCALENDAR'
            wrapper = u'VCALENDAR'
            for subcomponent in component.subcomponents:
                if subcomponent.name == u'VTIMEZONE':
                    timezones[subcomponent['TZID']] = subcomponent
                else:
                    components.append(subcomponent)
        else:
            if component.name == u'VCARD':
                assert wrapper is None or wrapper == u'VADDRESSBOOK'
                wrapper = u'VADDRESSBOOK'
            components.append(component)

    start = end = u''
    if wrapper is not None:
        start = u'BEGIN:{}'.format(wrapper)
        end = u'END:{}'.format(wrapper)

    lines = [start]
    for timezone in itervalues(timezones):
        lines.extend(to_unicode_lines(timezone))
    for component in components:
        lines.extend(to_unicode_lines(component))
    lines.append(end)

    return u''.join(line + u'\r\n' for line in lines if line)
