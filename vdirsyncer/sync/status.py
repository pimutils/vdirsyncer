from __future__ import annotations

import abc
import contextlib
import sqlite3
import sys
from collections.abc import Generator
from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Any

from .exceptions import IdentAlreadyExists


@contextlib.contextmanager
def _exclusive_transaction(
    conn: sqlite3.Connection,
) -> Generator[sqlite3.Cursor, None, None]:
    c = None
    try:
        c = conn.execute("BEGIN EXCLUSIVE TRANSACTION")
        yield c
        c.execute("COMMIT")
    except BaseException:
        if c is None:
            raise
        _, e, tb = sys.exc_info()
        c.execute("ROLLBACK")
        if e is not None:
            raise e.with_traceback(tb)
        raise


class _StatusBase(metaclass=abc.ABCMeta):
    def load_legacy_status(self, status: dict[str, Any]) -> None:
        with self.transaction():
            for ident, metadata in status.items():
                if len(metadata) == 4:
                    href_a, etag_a, href_b, etag_b = metadata
                    props_a = ItemMetadata(href=href_a, hash="UNDEFINED", etag=etag_a)
                    props_b = ItemMetadata(href=href_b, hash="UNDEFINED", etag=etag_b)
                else:
                    a, b = metadata
                    a.setdefault("hash", "UNDEFINED")
                    b.setdefault("hash", "UNDEFINED")
                    props_a = ItemMetadata(**a)
                    props_b = ItemMetadata(**b)

                self.insert_ident_a(ident, props_a)
                self.insert_ident_b(ident, props_b)

    def to_legacy_status(
        self,
    ) -> Generator[tuple[str, tuple[dict[str, Any], dict[str, Any]]], None, None]:
        for ident in self.iter_old():
            a = self.get_a(ident)
            b = self.get_b(ident)
            assert a is not None
            assert b is not None
            yield ident, (a.to_status(), b.to_status())

    @abc.abstractmethod
    def transaction(self) -> AbstractContextManager[None]:
        raise NotImplementedError

    @abc.abstractmethod
    def insert_ident_a(self, ident: str, props: ItemMetadata) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def insert_ident_b(self, ident: str, props: ItemMetadata) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def update_ident_a(self, ident: str, props: ItemMetadata) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def update_ident_b(self, ident: str, props: ItemMetadata) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def remove_ident(self, ident: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_a(self, ident: str) -> ItemMetadata | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_b(self, ident: str) -> ItemMetadata | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_new_a(self, ident: str) -> ItemMetadata | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_new_b(self, ident: str) -> ItemMetadata | None:
        raise NotImplementedError

    @abc.abstractmethod
    def iter_old(self) -> Iterator[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def iter_new(self) -> Iterator[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_href_a(
        self, href: str, default: tuple[None, None] = (None, None)
    ) -> tuple[str | None, ItemMetadata | None]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_href_b(
        self, href: str, default: tuple[None, None] = (None, None)
    ) -> tuple[str | None, ItemMetadata | None]:
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self, ident: str) -> None:
        raise NotImplementedError


class SqliteStatus(_StatusBase):
    SCHEMA_VERSION = 1

    def __init__(self, path: str = ":memory:") -> None:
        self._path = path
        self._c = sqlite3.connect(path)
        self._c.isolation_level = None  # turn off idiocy of DB-API
        self._c.row_factory = sqlite3.Row
        self._update_schema()

    def _update_schema(self) -> None:
        if self._is_latest_version():
            return

        # If we ever bump the schema version, we will need a way to migrate
        # data.
        with _exclusive_transaction(self._c) as c:
            c.execute('CREATE TABLE meta ( "version" INTEGER PRIMARY KEY )')
            c.execute("INSERT INTO meta (version) VALUES (?)", (self.SCHEMA_VERSION,))

            # I know that this is a bad schema, but right there is just too
            # little gain in deduplicating the .._a and .._b columns.
            c.execute(
                """CREATE TABLE status (
                "ident" TEXT PRIMARY KEY NOT NULL,
                "href_a" TEXT,
                "href_b" TEXT,
                "hash_a" TEXT NOT NULL,
                "hash_b" TEXT NOT NULL,
                "etag_a" TEXT,
                "etag_b" TEXT
            ); """
            )
            c.execute("CREATE UNIQUE INDEX by_href_a ON status(href_a)")
            c.execute("CREATE UNIQUE INDEX by_href_b ON status(href_b)")

            # We cannot add NOT NULL here because data is first fetched for the
            # storage a, then storage b. Inbetween the `_b`-columns are filled
            # with NULL.
            #
            # In an ideal world we would be able to start a transaction with
            # one cursor, write our new data into status and simultaneously
            # query the old status data using a different cursor.
            # Unfortunately sqlite enforces NOT NULL constraints immediately,
            # not just at commit. Since there is also no way to alter
            # constraints on a table (disable constraints on start of
            # transaction and reenable on end), it's a separate table now that
            # just gets copied over before we commit.  That's a lot of copying,
            # sadly.
            c.execute(
                """CREATE TABLE new_status (
                "ident" TEXT PRIMARY KEY NOT NULL,
                "href_a" TEXT,
                "href_b" TEXT,
                "hash_a" TEXT,
                "hash_b" TEXT,
                "etag_a" TEXT,
                "etag_b" TEXT
            ); """
            )

    def close(self) -> None:
        self._c.close()

    def _is_latest_version(self) -> bool:
        try:
            return bool(
                self._c.execute(
                    "SELECT version FROM meta WHERE version = ?", (self.SCHEMA_VERSION,)
                ).fetchone()
            )
        except sqlite3.OperationalError:
            return False

    @contextlib.contextmanager
    def transaction(self) -> Generator[None, None, None]:
        old_c = self._c
        try:
            with _exclusive_transaction(self._c) as cursor:
                self._c = cursor.connection
                yield
                cursor.execute("DELETE FROM status")
                cursor.execute("INSERT INTO status SELECT * FROM new_status")
                cursor.execute("DELETE FROM new_status")
        finally:
            self._c = old_c

    def insert_ident_a(self, ident: str, a_props: ItemMetadata) -> None:
        # FIXME: Super inefficient
        old_props = self.get_new_a(ident)
        if old_props is not None:
            raise IdentAlreadyExists(old_href=old_props.href, new_href=a_props.href)
        b_props = self.get_new_b(ident) or ItemMetadata()
        self._c.execute(
            "INSERT OR REPLACE INTO new_status VALUES(?, ?, ?, ?, ?, ?, ?)",
            (
                ident,
                a_props.href,
                b_props.href,
                a_props.hash,
                b_props.hash,
                a_props.etag,
                b_props.etag,
            ),
        )

    def insert_ident_b(self, ident: str, b_props: ItemMetadata) -> None:
        # FIXME: Super inefficient
        old_props = self.get_new_b(ident)
        if old_props is not None:
            raise IdentAlreadyExists(old_href=old_props.href, new_href=b_props.href)
        a_props = self.get_new_a(ident) or ItemMetadata()
        self._c.execute(
            "INSERT OR REPLACE INTO new_status VALUES(?, ?, ?, ?, ?, ?, ?)",
            (
                ident,
                a_props.href,
                b_props.href,
                a_props.hash,
                b_props.hash,
                a_props.etag,
                b_props.etag,
            ),
        )

    def update_ident_a(self, ident: str, props: ItemMetadata) -> None:
        cursor = self._c.execute(
            "UPDATE new_status SET href_a=?, hash_a=?, etag_a=? WHERE ident=?",
            (props.href, props.hash, props.etag, ident),
        )
        assert cursor.rowcount > 0

    def update_ident_b(self, ident: str, props: ItemMetadata) -> None:
        cursor = self._c.execute(
            "UPDATE new_status SET href_b=?, hash_b=?, etag_b=? WHERE ident=?",
            (props.href, props.hash, props.etag, ident),
        )
        assert cursor.rowcount > 0

    def remove_ident(self, ident: str) -> None:
        self._c.execute("DELETE FROM new_status WHERE ident=?", (ident,))

    def _get_impl(self, ident: str, side: str, table: str) -> ItemMetadata | None:
        res = self._c.execute(
            f"SELECT href_{side} AS href,"
            f"       hash_{side} AS hash,"
            f"       etag_{side} AS etag "
            f"FROM {table} WHERE ident=?",
            (ident,),
        ).fetchone()
        if res is None:
            return None

        if res["hash"] is None:  # FIXME: Implement as constraint in db
            assert res["href"] is None
            assert res["etag"] is None
            return None

        res = dict(res)
        return ItemMetadata(**res)

    def get_a(self, ident: str) -> ItemMetadata | None:
        return self._get_impl(ident, side="a", table="status")

    def get_b(self, ident: str) -> ItemMetadata | None:
        return self._get_impl(ident, side="b", table="status")

    def get_new_a(self, ident: str) -> ItemMetadata | None:
        return self._get_impl(ident, side="a", table="new_status")

    def get_new_b(self, ident: str) -> ItemMetadata | None:
        return self._get_impl(ident, side="b", table="new_status")

    def iter_old(self) -> Iterator[str]:
        return iter(
            res["ident"]
            for res in self._c.execute("SELECT ident FROM status").fetchall()
        )

    def iter_new(self) -> Iterator[str]:
        return iter(
            res["ident"]
            for res in self._c.execute("SELECT ident FROM new_status").fetchall()
        )

    def rollback(self, ident: str) -> None:
        a = self.get_a(ident)
        b = self.get_b(ident)
        assert (a is None) == (b is None)

        if a is None and b is None:
            self.remove_ident(ident)
            return

        assert a is not None
        assert b is not None
        self._c.execute(
            "INSERT OR REPLACE INTO new_status VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ident, a.href, b.href, a.hash, b.hash, a.etag, b.etag),
        )

    def _get_by_href_impl(
        self,
        href: str,
        default: tuple[None, None] = (None, None),
        side: str | None = None,
    ) -> tuple[str | None, ItemMetadata | None]:
        res = self._c.execute(
            f"SELECT ident, hash_{side} AS hash, etag_{side} AS etag "
            f"FROM status WHERE href_{side}=?",
            (href,),
        ).fetchone()
        if not res:
            return default
        return res["ident"], ItemMetadata(
            href=href,
            hash=res["hash"],
            etag=res["etag"],
        )

    def get_by_href_a(
        self, href: str, default: tuple[None, None] = (None, None)
    ) -> tuple[str | None, ItemMetadata | None]:
        return self._get_by_href_impl(href, default, side="a")

    def get_by_href_b(
        self, href: str, default: tuple[None, None] = (None, None)
    ) -> tuple[str | None, ItemMetadata | None]:
        return self._get_by_href_impl(href, default, side="b")


class SubStatus:
    def __init__(self, parent: SqliteStatus, side: str) -> None:
        from collections.abc import Callable

        self.parent = parent
        assert side in "ab"

        self.remove_ident: Callable[[str], None] = parent.remove_ident

        if side == "a":
            self.insert_ident: Callable[[str, ItemMetadata], None] = (
                parent.insert_ident_a
            )
            self.update_ident: Callable[[str, ItemMetadata], None] = (
                parent.update_ident_a
            )
            self.get: Callable[[str], ItemMetadata | None] = parent.get_a
            self.get_new: Callable[[str], ItemMetadata | None] = parent.get_new_a
            self.get_by_href = parent.get_by_href_a
        else:
            self.insert_ident = parent.insert_ident_b
            self.update_ident = parent.update_ident_b
            self.get = parent.get_b
            self.get_new = parent.get_new_b
            self.get_by_href = parent.get_by_href_b


class ItemMetadata:
    href = None
    hash = None
    etag = None

    def __init__(self, **kwargs: str | None) -> None:
        for k, v in kwargs.items():
            assert hasattr(self, k)
            setattr(self, k, v)

    def to_status(self) -> dict[str, str | None]:
        return {"href": self.href, "etag": self.etag, "hash": self.hash}
