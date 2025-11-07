from __future__ import annotations

import hashlib
from collections.abc import Generator
from collections.abc import Iterator
from functools import cached_property
from itertools import chain
from itertools import tee
from typing import Any

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


class Item:
    """Immutable wrapper class for VCALENDAR (VEVENT, VTODO) and
    VCARD"""

    def __init__(self, raw: str) -> None:
        assert isinstance(raw, str), type(raw)
        self._raw = raw

    def with_uid(self, new_uid: str | None) -> Item:
        parsed = _Component.parse(self.raw)
        assert isinstance(
            parsed, _Component
        )  # parse() without multiple=True returns single component
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
    def raw(self) -> str:
        """Raw content of the item, as unicode string.

        Vdirsyncer doesn't validate the content in any way.
        """
        return self._raw

    @cached_property
    def uid(self) -> str | None:
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
    def hash(self) -> str:
        """Hash of self.raw, used for etags."""
        return hash_item(self.raw)

    @cached_property
    def ident(self) -> str:
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
    def parsed(self) -> _Component | None:
        """Don't cache because the rv is mutable."""
        try:
            result = _Component.parse(self.raw)
            assert isinstance(
                result, _Component
            )  # parse() without multiple=True returns single component
            return result
        except Exception:
            return None


def normalize_item(
    item: str | Item, ignore_props: tuple[str, ...] = IGNORE_PROPS
) -> str:
    """Create syntactically invalid mess that is equal for similar items."""
    if not isinstance(item, Item):
        item = Item(item)

    item = _strip_timezones(item)

    x = _Component("TEMP", item.raw.splitlines(), [])
    for prop in IGNORE_PROPS:
        del x[prop]

    x.props.sort()
    return "\r\n".join(filter(bool, (line.strip() for line in x.props)))


def _strip_timezones(item: Item) -> Item:
    parsed = item.parsed
    if not parsed or parsed.name != "VCALENDAR":
        return item

    parsed.subcomponents = [c for c in parsed.subcomponents if c.name != "VTIMEZONE"]

    return Item("\r\n".join(parsed.dump_lines()))


def hash_item(text: str | Item) -> str:
    return hashlib.sha256(normalize_item(text).encode("utf-8")).hexdigest()


def split_collection(text: str) -> Generator[str, None, None]:
    assert isinstance(text, str)
    inline: list[_Component] = []
    items: dict[str, _Component] = {}  # uid => item
    ungrouped_items: list[_Component] = []

    parsed = _Component.parse(text, multiple=True)
    assert isinstance(parsed, list)  # parse() with multiple=True returns list
    for main in parsed:
        _split_collection_impl(main, main, inline, items, ungrouped_items)

    for item in chain(items.values(), ungrouped_items):
        item.subcomponents.extend(inline)
        yield "\r\n".join(item.dump_lines())


def _split_collection_impl(
    item: _Component,
    main: _Component,
    inline: list[_Component],
    items: dict[str, _Component],
    ungrouped_items: list[_Component],
) -> None:
    if item.name == "VTIMEZONE":
        inline.append(item)
    elif item.name == "VCARD":
        ungrouped_items.append(item)
    elif item.name in ("VTODO", "VEVENT", "VJOURNAL"):
        uid = item.get("UID", "")
        wrapper = _Component(main.name, main.props[:], [])

        if uid and uid.strip():
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


def join_collection(
    items: Iterator[str], wrappers: dict[str, str] = _default_join_wrappers
) -> str:
    """
    :param wrappers: {
        item_type: wrapper_type
    }
    """

    def _parse_single(x: str) -> _Component:
        result = _Component.parse(x)
        assert isinstance(
            result, _Component
        )  # parse() without multiple=True returns single component
        return result

    items1, items2 = tee((_parse_single(x) for x in items), 2)
    _item_type, wrapper_type = _get_item_type(items1, wrappers)
    wrapper_props: list[str] = []

    def _get_item_components(x: _Component) -> list[_Component]:
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


def _get_item_type(
    components: Iterator[_Component], wrappers: dict[str, str]
) -> tuple[str | None, str | None]:
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

    def __init__(
        self, name: str, lines: list[str], subcomponents: list[_Component]
    ) -> None:
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
    def parse(
        cls, lines: bytes | str | list[str], multiple: bool = False
    ) -> _Component | list[_Component]:
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

    def dump_lines(self) -> Generator[str, None, None]:
        yield f"BEGIN:{self.name}"
        yield from self.props
        for c in self.subcomponents:
            yield from c.dump_lines()
        yield f"END:{self.name}"

    def __delitem__(self, key: str) -> None:
        prefix = (f"{key}:", f"{key};")
        new_lines = []
        lineiter = iter(self.props)
        while True:
            for line in lineiter:
                if line.startswith(prefix):
                    break
                new_lines.append(line)
            else:
                break

            for line in lineiter:
                if not line.startswith((" ", "\t", *prefix)):
                    new_lines.append(line)
                    break

        self.props = new_lines

    def __setitem__(self, key: str, val: str) -> None:
        assert isinstance(val, str)
        assert "\n" not in val
        del self[key]
        line = f"{key}:{val}"
        self.props.append(line)

    def __contains__(self, obj: Any) -> bool:  # noqa: ANN401
        if isinstance(obj, type(self)):
            return obj not in self.subcomponents and not any(
                obj in x for x in self.subcomponents
            )
        if isinstance(obj, str):
            return self.get(obj, None) is not None
        raise ValueError(obj)

    def __getitem__(self, key: str) -> str:
        prefix_without_params = f"{key}:"
        prefix_with_params = f"{key};"
        iterlines = iter(self.props)
        for line in iterlines:
            if line.startswith(prefix_without_params):
                rv = line[len(prefix_without_params) :]
                break
            if line.startswith(prefix_with_params):
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

    def get(self, key: str, default: str | None = None) -> str | None:
        try:
            return self[key]
        except KeyError:
            return default

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, type(self))
            and self.name == other.name
            and self.props == other.props
            and self.subcomponents == other.subcomponents
        )
