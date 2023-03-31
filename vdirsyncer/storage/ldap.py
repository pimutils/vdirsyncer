import logging

import ldap3
import vobject

from .. import exceptions
from ..vobject import Item
from .base import Storage

logger = logging.getLogger(__name__)


class LDAPStorage(Storage):
    storage_name = "ldap"
    _synced = [
        "cn",
        "sn",
        "givenName",
        "mail",
        "telephoneNumber",
        "homePhone",
        "mobile",
        "fax",
        "pager",
    ]

    def __init__(
        self,
        url="ldap://localhost",
        user=None,
        password=None,
        search_base=None,
        search_filter=None,
        _conn=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._converter = LDAPConverter()
        if search_filter is None:
            self.search_filter = "(objectClass=inetOrgPerson)"
        else:
            self.search_filter = search_filter

        if _conn is None:
            server = ldap3.Server(url, get_info=ldap3.DSA)
            self._conn = ldap3.Connection(server, user=user, password=password)

        else:
            # Tests
            self._conn = _conn

        logger.debug(f"Connection: {self._conn}")
        self._conn.bind()

        if search_base is None:
            # Fallback to default root entry
            self.search_base = self._conn.server.info.naming_contexts[0]
        else:
            self.search_base = search_base

    async def list(self):
        logger.debug(f"Search base: {self.search_base}")
        logger.debug(f"Search filter: {self.search_filter}")
        self._conn.search(
            self.search_base, self.search_filter, attributes=["modifyTimestamp"]
        )
        for entry in self._conn.entries:
            logger.debug(f"Found: {entry.entry_dn}")
            yield entry.entry_dn, entry.modifyTimestamp.value

    async def get(self, href):
        self._conn.search(
            href,
            "(objectClass=*)",
            search_scope=ldap3.BASE,
            attributes=self._synced + ["modifyTimestamp"],
        )

        if not len(self._conn.entries):
            raise exceptions.NotFoundError(href)

        entry = self._conn.entries[0]
        vcard = self._converter.to_vcard(entry.entry_attributes_as_dict)
        return Item(vcard.serialize()), entry.modifyTimestamp.value

    async def upload(self, item):
        vcard = vobject.readOne(item.raw)
        dn = self._dn(vcard.fn.value)
        attributes = self._converter.to_ldap(vcard)
        logger.debug(attributes)
        success = self._conn.add(dn, "inetOrgPerson", attributes)
        if not success:
            r = self._conn.result
            raise exceptions.PreconditionFailed(
                f"Upload failed with code={r['result']}, message={r['message']}, "
                f"description={r['description']}"
            )

        etag = await self._fetch_etag(dn)
        return dn, etag

    async def update(self, href, item, etag):
        if etag is None:
            raise ValueError("etag must be given and must not be None.")

        vcard = vobject.readOne(item.raw)
        dn = self._dn(vcard.fn.value)

        actual_etag = await self._fetch_etag(dn)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        attributes = self._converter.to_ldap(vcard)
        logger.debug(f"LDAP attributes: {attributes}")

        changes = self._update_changes(attributes)
        if changes:
            logger.debug(f"LDAP changes: {changes}")
            success = self._conn.modify(dn, changes)
            if not success:
                r = self._conn.result
                raise exceptions.PreconditionFailed(
                    f"Update failed with code={r['result']}, message={r['message']}, "
                    f"description={r['description']}"
                )
            return await self._fetch_etag(dn)
        return actual_etag

    async def delete(self, href, _):
        success = self._conn.delete(href)
        if not success:
            r = self._conn.result
            raise exceptions.PreconditionFailed(
                f"Delete failed with code={r['result']}, message={r['message']}, "
                f"description={r['description']}"
            )

    async def _fetch_etag(self, href):
        self._conn.search(href, self.search_filter, attributes=["modifyTimestamp"])
        if not len(self._conn.entries):
            raise exceptions.NotFoundError(href)
        return self._conn.entries[0].modifyTimestamp.value

    def _dn(self, value):
        return f"cn={value},{self.search_base}"

    def _update_changes(self, attributes):
        changes = {}

        # Delete synced items
        for item in self._synced:
            changes[item] = [(ldap3.MODIFY_REPLACE, [])]

        # Except for the ones stored in attributes
        for k, v in attributes.items():
            changes[k] = [(ldap3.MODIFY_REPLACE, [v])]

        # Do not update the common name
        attributes.pop("cn")
        return changes


class LDAPConverter:
    def __init__(self):
        # Convert LDAP attribute to vcard entry
        self._ldap_map = {
            "mobile": (self._vcard_append, "tel", "CELL"),
            "telephoneNumber": (self._vcard_append, "tel", ["WORK", "VOICE"]),
            "homePhone": (self._vcard_append, "tel", ["HOME", "VOICE"]),
            "fax": (self._vcard_append, "tel", "FAX"),
            "pager": (self._vcard_append, "tel", "PAGER"),
            "mail": (self._vcard_append, "email", "INTERNET"),
        }
        # Convert vcard attribute to LDAP attribute
        self._vcard_map = {
            "fn": self._ldap_cn,
            "n": self._ldap_n,
            "tel": self._ldap_tel,
            "email": self._ldap_email,
        }

    def to_vcard(self, data):
        """Convert LDAP attribute :data: to vcard."""
        vcard = vobject.vCard()

        vo = vcard.add("fn")
        vo.value = data.pop("cn")[0]
        vcard.add("n")
        logger.warning(data)
        given = ""
        if data["givenName"]:
            given = data.pop("givenName")
        vcard.n.value = vobject.vcard.Name(family=data.pop("sn")[0], given=given)

        for k, v in data.items():
            if not v or k in ["modifyTimestamp"]:
                # No data or attribute not relevant for conversion
                continue
            try:
                converter, name, type_param = self._ldap_map[k]
                converter(vcard, name, v[0], type_param)
            except KeyError:
                logger.warning(f"Skipping unknown attribute: {k}")
        return vcard

    def to_ldap(self, vcard):
        """Convert vcard to LDAP attributes."""
        attributes = {}

        for k, v in vcard.contents.items():
            if k in ["version"]:
                # Not relevant for conversion
                continue
            try:
                converter = self._vcard_map[k]
                attributes.update(converter(v))
            except KeyError:
                logger.warning(f"Skipping unknown attribute: {k}")

        # The attribute sn is required for inetOrgPerson
        if "cn" in attributes and "sn" not in attributes:
            # Assumption: "FirstName LastName"
            attributes["sn"] = attributes["cn"].split(" ", maxsplit=1)[-1]

        return attributes

    def _ldap_cn(self, values):
        return {"cn": values[0].value}

    def _ldap_n(self, values):
        v = values[0]
        return {"sn": v.value.family, "givenName": v.value.given}

    def _ldap_tel(self, values):
        mapping = {
            "HOME": "homePhone",
            "WORK": "telephoneNumber",
            "CELL": "mobile",
            "FAX": "fax",
            "PAGER": "pager",
        }
        result = {}
        for v in values:
            t = {tp.upper().strip() for tp in v.type_paramlist}
            t.discard("VOICE")  # default
            try:
                result.update(self.__value(mapping[t.pop()], v.value))
            except KeyError:
                pass
        return result

    def _ldap_email(self, values):
        return self.__value("mail", values[0].value)

    def _vcard_append(self, vcard, name, value, type_param):
        """Add :name: entry with :value: and :type_param: to an existing vcard."""
        vo = vcard.add(name)
        vo.value = value
        vo.type_param = type_param

    def __value(self, key, value):
        result = {}
        if value:
            result[key] = value
        return result
