from __future__ import annotations

import hashlib
from functools import cached_property
from itertools import chain
from itertools import tee

from .utils import uniq

IGNORE_PROPS = (
    # PRODID is changed by radicale for some reason after upload
    "PRODID",
    # Sometimes METHOD:PUBLISH is added by WebCAL providers, for us it doesn't
    # make a difference
    "METHOD",
    # X-RADICALE-NAME is used by radicale, because hrefs don't really exist in
    # their filesystem backend
    "X-RADICALE-NAME",
    # Apparently this is set by Horde?
    # https://github.com/pimutils/vdirsyncer/issues/318
    "X-WR-CALNAME",
    # Those are from the VCARD specification and is supposed to change when the
    # item does -- however, we can determine that ourselves
    "REV",
    "LAST-MODIFIED",
    "CREATED",
    # Some iCalendar HTTP calendars generate the DTSTAMP at request time, so
    # this property always changes when the rest of the item didn't. Some do
    # the same with the UID.
    #
    # - Google's read-only calendar links
    # - http://www.feiertage-oesterreich.at/
    "DTSTAMP",
    "UID",
)

CALDAV_SCHEDULING_MODES = frozenset({"preserve", "passive", "standalone"})


class Item:
    """Immutable wrapper class for VCALENDAR (VEVENT, VTODO) and
    VCARD"""

    def __init__(self, raw):
        assert isinstance(raw, str), type(raw)
        self._raw = raw

    def with_uid(self, new_uid):
        parsed = _Component.parse(self.raw)
        stack = [parsed]
        while stack:
            component = stack.pop()
            stack.extend(component.subcomponents)

            if component.name in ("VEVENT", "VTODO", "VJOURNAL", "VCARD"):
                del component["UID"]
                if new_uid:
                    component["UID"] = new_uid

        return Item("\r\n".join(parsed.dump_lines()))

    @cached_property
    def raw(self):
        """Raw content of the item, as unicode string.

        Vdirsyncer doesn't validate the content in any way.
        """
        return self._raw

    @cached_property
    def uid(self):
        """Global identifier of the item, across storages, doesn't change after
        a modification of the item."""
        # Don't actually parse component, but treat all lines as single
        # component, avoiding traversal through all subcomponents.
        x = _Component("TEMP", self.raw.splitlines(), [])
        try:
            return x["UID"].strip() or None
        except KeyError:
            return None

    @cached_property
    def hash(self):
        """Hash of self.raw, used for etags."""
        return hash_item(self.raw)

    @cached_property
    def ident(self):
        """Used for generating hrefs and matching up items during
        synchronization. This is either the UID or the hash of the item's
        content."""

        # We hash the item instead of directly using its raw content, because
        #
        # 1. The raw content might be really large, e.g. when it's a contact
        #    with a picture, which bloats the status file.
        #
        # 2. The status file would contain really sensitive information.
        return self.uid or self.hash

    @property
    def parsed(self):
        """Don't cache because the rv is mutable."""
        try:
            return _Component.parse(self.raw)
        except ValueError:
            return None


def prepare_calendar_for_caldav(
    item: Item, scheduling_mode: str = "preserve"
) -> Item:
    """Return a calendar object suitable for storage in a CalDAV collection.

    ``METHOD`` describes an iTIP message such as a request or a published
    event.  RFC 4791 section 4.1 forbids that property on calendar object
    resources stored in a CalDAV collection.  Some servers nevertheless
    expose stored objects containing it, so strip it at the destination
    boundary instead of forwarding invalid data to another server.

    ``scheduling_mode`` controls how organizer and attendee properties are
    written.  ``preserve`` keeps them unchanged, ``passive`` asks the server
    not to process scheduling messages, and ``standalone`` removes scheduling
    relationships so the destination stores a personal event copy.

    Keep malformed or non-calendar items untouched.  Validation remains the
    destination server's responsibility, as it was before this normalization.
    """
    if (
        not isinstance(scheduling_mode, str)
        or scheduling_mode not in CALDAV_SCHEDULING_MODES
    ):
        raise ValueError(f"Invalid scheduling mode: {scheduling_mode!r}")

    parsed = item.parsed
    if parsed is None or parsed.name != "VCALENDAR":
        return item

    changed = "METHOD" in parsed
    del parsed["METHOD"]

    components = list(_walk_components(parsed))
    if scheduling_mode == "passive":
        for component in components:
            changed |= component.set_property_parameter(
                "ORGANIZER", "SCHEDULE-AGENT", "NONE"
            )
            changed |= component.set_property_parameter(
                "ATTENDEE", "SCHEDULE-AGENT", "NONE"
            )
    elif scheduling_mode == "standalone":
        for component in components:
            for prop in ("ORGANIZER", "ATTENDEE", "X-MS-OLK-SENDER"):
                if prop in component:
                    changed = True
                    del component[prop]

    if not changed:
        return item
    return Item("\r\n".join(parsed.dump_lines()))


def _walk_components(component):
    yield component
    for subcomponent in component.subcomponents:
        yield from _walk_components(subcomponent)


def normalize_item(item, ignore_props=IGNORE_PROPS):
    """Create syntactically invalid mess that is equal for similar items."""
    if not isinstance(item, Item):
        item = Item(item)

    item = _strip_timezones(item)

    x = _Component("TEMP", item.raw.splitlines(), [])
    for prop in IGNORE_PROPS:
        del x[prop]

    x.props.sort()
    return "\r\n".join(filter(bool, (line.strip() for line in x.props)))


def _strip_timezones(item):
    parsed = item.parsed
    if not parsed or parsed.name != "VCALENDAR":
        return item

    parsed.subcomponents = [c for c in parsed.subcomponents if c.name != "VTIMEZONE"]

    return Item("\r\n".join(parsed.dump_lines()))


def hash_item(text):
    return hashlib.sha256(normalize_item(text).encode("utf-8")).hexdigest()


def split_collection(text):
    assert isinstance(text, str)
    inline = []
    items = {}  # uid => item
    ungrouped_items = []

    for main in _Component.parse(text, multiple=True):
        _split_collection_impl(main, main, inline, items, ungrouped_items)

    for item in chain(items.values(), ungrouped_items):
        item.subcomponents.extend(inline)
        yield "\r\n".join(item.dump_lines())


def _split_collection_impl(item, main, inline, items, ungrouped_items):
    if item.name == "VTIMEZONE":
        inline.append(item)
    elif item.name == "VCARD":
        ungrouped_items.append(item)
    elif item.name in ("VTODO", "VEVENT", "VJOURNAL"):
        uid = item.get("UID", "")
        wrapper = _Component(main.name, main.props[:], [])

        if uid.strip():
            wrapper = items.setdefault(uid, wrapper)
        else:
            ungrouped_items.append(wrapper)

        wrapper.subcomponents.append(item)
    elif item.name in ("VCALENDAR", "VADDRESSBOOK"):
        if item.name == "VCALENDAR":
            del item["METHOD"]
        for subitem in item.subcomponents:
            _split_collection_impl(subitem, item, inline, items, ungrouped_items)
    else:
        raise ValueError(f"Unknown component: {item.name}")


_default_join_wrappers = {
    "VCALENDAR": "VCALENDAR",
    "VEVENT": "VCALENDAR",
    "VTODO": "VCALENDAR",
    "VCARD": "VADDRESSBOOK",
}


def join_collection(items, wrappers=_default_join_wrappers):
    """
    :param wrappers: {
        item_type: wrapper_type
    }
    """

    items1, items2 = tee((_Component.parse(x) for x in items), 2)
    _item_type, wrapper_type = _get_item_type(items1, wrappers)
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
        lines = chain(
            *(
                [f"BEGIN:{wrapper_type}"],
                # XXX: wrapper_props is a list of lines (with line-wrapping), so
                # filtering out duplicate lines will almost certainly break
                # multiline-values.  Since the only props we usually need to
                # support are PRODID and VERSION, I don't care.
                uniq(wrapper_props),
                lines,
                [f"END:{wrapper_type}"],
            )
        )
    return "".join(line + "\r\n" for line in lines)


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
    raise ValueError("Not sure how to join components.")


class _Component:
    """
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
    """

    def __init__(self, name, lines, subcomponents):
        """
        :param name: The component name.
        :param lines: The component's own properties, as list of lines
            (strings).
        :param subcomponents: List of components.
        """
        self.name = name
        self.props = lines
        self.subcomponents = subcomponents

    @classmethod
    def parse(cls, lines, multiple=False):
        if isinstance(lines, bytes):
            lines = lines.decode("utf-8")
        if isinstance(lines, str):
            lines = lines.splitlines()

        stack = []
        rv = []
        try:
            for _i, line in enumerate(lines):
                if line.startswith("BEGIN:"):
                    c_name = line[len("BEGIN:") :].strip().upper()
                    stack.append(cls(c_name, [], []))
                elif line.startswith("END:"):
                    component = stack.pop()
                    c_name = line[len("END:") :].strip().upper()
                    if c_name != component.name:
                        raise ValueError(
                            f"Got END:{c_name}, expected END:{component.name}"
                            + f" at line {_i + 1}"
                        )
                    if stack:
                        stack[-1].subcomponents.append(component)
                    else:
                        rv.append(component)
                else:
                    if line.strip():
                        stack[-1].props.append(line)
        except IndexError:
            raise ValueError(f"Parsing error at line {_i + 1}")

        if len(stack) > 0:
            raise ValueError(
                f"Missing END for component(s): {', '.join(c.name for c in stack)}"
            )

        if multiple:
            return rv
        if len(rv) != 1:
            raise ValueError(f"Found {len(rv)} components, expected one.")
        return rv[0]

    def dump_lines(self):
        yield f"BEGIN:{self.name}"
        yield from self.props
        for c in self.subcomponents:
            yield from c.dump_lines()
        yield f"END:{self.name}"

    def __delitem__(self, key):
        prefix = (f"{key}:", f"{key};")
        new_lines = []
        deleting = False

        for line in self.props:
            if line.startswith((" ", "\t")):
                if not deleting:
                    new_lines.append(line)
                continue

            deleting = any(_startswith_case_insensitive(line, x) for x in prefix)
            if not deleting:
                new_lines.append(line)

        self.props = new_lines

    def __setitem__(self, key, val):
        assert isinstance(val, str)
        assert "\n" not in val
        del self[key]
        line = f"{key}:{val}"
        self.props.append(line)

    def set_property_parameter(self, key, parameter, value):
        """Set a parameter on all matching properties.

        Property lines are unfolded only when they need to be changed.  This
        keeps unrelated, possibly vendor-specific iCalendar data byte-for-byte
        stable while still handling folded ORGANIZER and ATTENDEE lines.
        """
        groups = []
        for line in self.props:
            if line.startswith((" ", "\t")) and groups:
                groups[-1].append(line)
            else:
                groups.append([line])

        changed = False
        new_lines = []
        for group in groups:
            logical_line = group[0] + "".join(line[1:] for line in group[1:])
            separator = _find_unquoted(logical_line, ":")
            if separator < 0:
                new_lines.extend(group)
                continue

            head = logical_line[:separator]
            parts = _split_unquoted(head, ";")
            if not parts or parts[0].upper() != key.upper():
                new_lines.extend(group)
                continue

            replacement = f"{parameter.upper()}={value}"
            group_changed = False
            new_parts = [parts[0]]
            parameter_found = False
            for part in parts[1:]:
                name, equals, _old_value = part.partition("=")
                if equals and name.upper() == parameter.upper():
                    if parameter_found:
                        group_changed = True
                        continue
                    parameter_found = True
                    new_parts.append(replacement)
                    group_changed |= part != replacement
                else:
                    new_parts.append(part)
            if not parameter_found:
                new_parts.append(replacement)
                group_changed = True

            if group_changed:
                new_lines.append(";".join(new_parts) + logical_line[separator:])
            else:
                new_lines.extend(group)
            changed |= group_changed

        if changed:
            self.props = new_lines
        return changed

    def __contains__(self, obj):
        if isinstance(obj, type(self)):
            return obj not in self.subcomponents and not any(
                obj in x for x in self.subcomponents
            )
        if isinstance(obj, str):
            return self.get(obj, None) is not None
        raise ValueError(obj)

    def __getitem__(self, key):
        prefix_without_params = f"{key}:"
        prefix_with_params = f"{key};"
        iterlines = iter(self.props)
        for line in iterlines:
            if _startswith_case_insensitive(line, prefix_without_params):
                rv = line[len(prefix_without_params) :]
                break
            if _startswith_case_insensitive(line, prefix_with_params):
                rv = line[len(prefix_with_params) :].split(":", 1)[-1]
                break
        else:
            raise KeyError

        for line in iterlines:
            if line.startswith((" ", "\t")):
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
            isinstance(other, type(self))
            and self.name == other.name
            and self.props == other.props
            and self.subcomponents == other.subcomponents
        )


def _find_unquoted(value, needle):
    quoted = False
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif char == needle and not quoted:
            return index
    return -1


def _startswith_case_insensitive(value, prefix):
    if len(value) < len(prefix):
        return False
    return all(
        actual.upper() == expected.upper()
        for actual, expected in zip(value[: len(prefix)], prefix, strict=True)
    )


def _split_unquoted(value, separator):
    parts = []
    start = 0
    while True:
        offset = _find_unquoted(value[start:], separator)
        if offset < 0:
            parts.append(value[start:])
            return parts
        end = start + offset
        parts.append(value[start:end])
        start = end + 1
