import abc
import contextlib
import sqlite3
import sys

from .exceptions import IdentAlreadyExists


@contextlib.contextmanager
def _exclusive_transaction(conn):
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
        raise e.with_traceback(tb)


class _StatusBase(metaclass=abc.ABCMeta):
    def load_legacy_status(self, status):
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

    def to_legacy_status(self):
        for ident in self.iter_old():
            a = self.get_a(ident)
            b = self.get_b(ident)
            yield ident, (a.to_status(), b.to_status())

    @abc.abstractmethod
    def transaction(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def insert_ident_a(self, ident, props):
        raise NotImplementedError()

    @abc.abstractmethod
    def insert_ident_b(self, ident, props):
        raise NotImplementedError()

    @abc.abstractmethod
    def update_ident_a(self, ident, props):
        raise NotImplementedError()

    @abc.abstractmethod
    def update_ident_b(self, ident, props):
        raise NotImplementedError()

    @abc.abstractmethod
    def remove_ident(self, ident):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_a(self, ident):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_b(self, ident):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_new_a(self, ident):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_new_b(self, ident):
        raise NotImplementedError()

    @abc.abstractmethod
    def iter_old(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def iter_new(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_by_href_a(self, href, default=(None, None)):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_by_href_b(self, href, default=(None, None)):
        raise NotImplementedError()

    @abc.abstractmethod
    def rollback(self, ident):
        raise NotImplementedError()


class SqliteStatus(_StatusBase):
    SCHEMA_VERSION = 1

    def __init__(self, path=":memory:"):
        self._path = path
        self._c = sqlite3.connect(path)
        self._c.isolation_level = None  # turn off idiocy of DB-API
        self._c.row_factory = sqlite3.Row
        self._update_schema()

    def _update_schema(self):
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

    def _is_latest_version(self):
        try:
            return bool(
                self._c.execute(
                    "SELECT version FROM meta WHERE version = ?", (self.SCHEMA_VERSION,)
                ).fetchone()
            )
        except sqlite3.OperationalError:
            return False

    @contextlib.contextmanager
    def transaction(self):
        old_c = self._c
        try:
            with _exclusive_transaction(self._c) as new_c:
                self._c = new_c
                yield
                self._c.execute("DELETE FROM status")
                self._c.execute("INSERT INTO status " "SELECT * FROM new_status")
                self._c.execute("DELETE FROM new_status")
        finally:
            self._c = old_c

    def insert_ident_a(self, ident, a_props):
        # FIXME: Super inefficient
        old_props = self.get_new_a(ident)
        if old_props is not None:
            raise IdentAlreadyExists(old_href=old_props.href, new_href=a_props.href)
        b_props = self.get_new_b(ident) or ItemMetadata()
        self._c.execute(
            "INSERT OR REPLACE INTO new_status " "VALUES(?, ?, ?, ?, ?, ?, ?)",
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

    def insert_ident_b(self, ident, b_props):
        # FIXME: Super inefficient
        old_props = self.get_new_b(ident)
        if old_props is not None:
            raise IdentAlreadyExists(old_href=old_props.href, new_href=b_props.href)
        a_props = self.get_new_a(ident) or ItemMetadata()
        self._c.execute(
            "INSERT OR REPLACE INTO new_status " "VALUES(?, ?, ?, ?, ?, ?, ?)",
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

    def update_ident_a(self, ident, props):
        self._c.execute(
            "UPDATE new_status" " SET href_a=?, hash_a=?, etag_a=?" " WHERE ident=?",
            (props.href, props.hash, props.etag, ident),
        )
        assert self._c.rowcount > 0

    def update_ident_b(self, ident, props):
        self._c.execute(
            "UPDATE new_status" " SET href_b=?, hash_b=?, etag_b=?" " WHERE ident=?",
            (props.href, props.hash, props.etag, ident),
        )
        assert self._c.rowcount > 0

    def remove_ident(self, ident):
        self._c.execute("DELETE FROM new_status WHERE ident=?", (ident,))

    def _get_impl(self, ident, side, table):
        res = self._c.execute(
            "SELECT href_{side} AS href,"
            "       hash_{side} AS hash,"
            "       etag_{side} AS etag "
            "FROM {table} WHERE ident=?".format(side=side, table=table),
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

    def get_a(self, ident):
        return self._get_impl(ident, side="a", table="status")

    def get_b(self, ident):
        return self._get_impl(ident, side="b", table="status")

    def get_new_a(self, ident):
        return self._get_impl(ident, side="a", table="new_status")

    def get_new_b(self, ident):
        return self._get_impl(ident, side="b", table="new_status")

    def iter_old(self):
        return iter(
            res["ident"]
            for res in self._c.execute("SELECT ident FROM status").fetchall()
        )

    def iter_new(self):
        return iter(
            res["ident"]
            for res in self._c.execute("SELECT ident FROM new_status").fetchall()
        )

    def rollback(self, ident):
        a = self.get_a(ident)
        b = self.get_b(ident)
        assert (a is None) == (b is None)

        if a is None and b is None:
            self.remove_ident(ident)
            return

        self._c.execute(
            "INSERT OR REPLACE INTO new_status" " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ident, a.href, b.href, a.hash, b.hash, a.etag, b.etag),
        )

    def _get_by_href_impl(self, href, default=(None, None), side=None):
        res = self._c.execute(
            "SELECT ident, hash_{side} AS hash, etag_{side} AS etag "
            "FROM status WHERE href_{side}=?".format(side=side),
            (href,),
        ).fetchone()
        if not res:
            return default
        return res["ident"], ItemMetadata(
            href=href,
            hash=res["hash"],
            etag=res["etag"],
        )

    def get_by_href_a(self, *a, **kw):
        kw["side"] = "a"
        return self._get_by_href_impl(*a, **kw)

    def get_by_href_b(self, *a, **kw):
        kw["side"] = "b"
        return self._get_by_href_impl(*a, **kw)


class SubStatus:
    def __init__(self, parent, side):
        self.parent = parent
        assert side in "ab"

        self.remove_ident = parent.remove_ident

        if side == "a":
            self.insert_ident = parent.insert_ident_a
            self.update_ident = parent.update_ident_a
            self.get = parent.get_a
            self.get_new = parent.get_new_a
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

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            assert hasattr(self, k)
            setattr(self, k, v)

    def to_status(self):
        return {"href": self.href, "etag": self.etag, "hash": self.hash}
