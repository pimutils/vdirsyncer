from __future__ import annotations

import contextlib
import functools
import os
import sys
import tempfile
import uuid
from collections.abc import Generator
from inspect import FullArgSpec
from inspect import getfullargspec
from typing import IO
from typing import Any
from typing import Callable

from . import exceptions

# This is only a subset of the chars allowed per the spec. In particular `@` is
# not included, because there are some servers that (incorrectly) encode it to
# `%40` when it's part of a URL path, and reject or "repair" URLs that contain
# `@` in the path. So it's better to just avoid it.
SAFE_UID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-+"


_missing = object()


def expand_path(p: str) -> str:
    """Expand $HOME in a path and normalise slashes."""
    p = os.path.expanduser(p)
    return os.path.normpath(p)


def split_dict(
    d: dict[Any, Any],
    f: Callable[[Any], bool],
) -> tuple[dict[Any, Any], dict[Any, Any]]:
    """Puts key into first dict if f(key), otherwise in second dict"""
    a = {}
    b = {}
    for k, v in d.items():
        if f(k):
            a[k] = v
        else:
            b[k] = v
    return a, b


def uniq(s: Any) -> Generator[Any, None, None]:  # noqa: ANN401
    """Filter duplicates while preserving order. ``set`` can almost always be
    used instead of this, but preserving order might prove useful for
    debugging."""
    d = set()
    for x in s:
        if x not in d:
            d.add(x)
            yield x


def get_etag_from_file(f: str | IO[Any]) -> str:
    """Get etag from a filepath or file-like object.

    This function will flush/sync the file as much as necessary to obtain a
    correct value.
    """
    if isinstance(f, str):
        stat = os.stat(f)
    else:
        f.flush()  # Only this is necessary on Linux
        if sys.platform == "win32":
            os.fsync(f.fileno())  # Apparently necessary on Windows
        stat = os.fstat(f.fileno())

    mtime = getattr(stat, "st_mtime_ns", None)
    if mtime is None:
        mtime = stat.st_mtime
    return f"{mtime:.9f};{stat.st_ino}"


def get_storage_init_specs(
    cls: type,
    stop_at: type = object,
) -> tuple[FullArgSpec, ...]:
    if cls is stop_at:
        return ()

    spec = getfullargspec(cls.__init__)  # type: ignore[misc]
    traverse_superclass = getattr(cls.__init__, "_traverse_superclass", True)  # type: ignore[misc]
    if traverse_superclass:
        if traverse_superclass is True:
            supercls = next(
                getattr(x.__init__, "__objclass__", x)  # type: ignore[misc]
                for x in cls.__mro__[1:]
            )
        else:
            supercls = traverse_superclass
        superspecs = get_storage_init_specs(supercls, stop_at=stop_at)
    else:
        superspecs = ()

    return (spec, *superspecs)


def get_storage_init_args(
    cls: type,
    stop_at: type = object,
) -> tuple[set[str], set[str]]:
    """
    Get args which are taken during class initialization. Assumes that all
    classes' __init__ calls super().__init__ with the rest of the arguments.

    :param cls: The class to inspect.
    :returns: (all, required), where ``all`` is a set of all arguments the
        class can take, and ``required`` is the subset of arguments the class
        requires.
    """
    all, required = set(), set()
    for spec in get_storage_init_specs(cls, stop_at=stop_at):
        all.update(spec.args[1:])
        last = -len(spec.defaults) if spec.defaults else len(spec.args)
        required.update(spec.args[1:last])

    return all, required


def checkdir(path: str, create: bool = False, mode: int = 0o750) -> None:
    """Check whether ``path`` is a directory.

    :param create: Whether to create the directory (and all parent directories)
        if it does not exist.
    :param mode: Mode to create missing directories with.
    """

    if not os.path.isdir(path):
        if os.path.exists(path):
            raise OSError(f"{path} is not a directory.")
        if create:
            os.makedirs(path, mode)
        else:
            raise exceptions.CollectionNotFound(f"Directory {path} does not exist.")


def checkfile(path: str, create: bool = False) -> None:
    """Check whether ``path`` is a file.

    :param create: Whether to create the file's parent directories if they do
        not exist.
    :raises CollectionNotFound: if path does not exist.
    :raises OSError: if path exists but is not a file.
    """
    checkdir(os.path.dirname(path), create=create)
    if not os.path.isfile(path):
        if os.path.exists(path):
            raise OSError(f"{path} is not a file.")
        if create:
            with open(path, "wb"):
                pass
        else:
            raise exceptions.CollectionNotFound(f"File {path} does not exist.")


def href_safe(ident: str, safe: str = SAFE_UID_CHARS) -> bool:
    return not bool(set(ident) - set(safe))


def generate_href(ident: str | None = None, safe: str = SAFE_UID_CHARS) -> str:
    """
    Generate a safe identifier, suitable for URLs, storage hrefs or UIDs.

    If the given ident string is safe, it will be returned, otherwise a random
    UUID.
    """
    if not ident or not href_safe(ident, safe):
        return str(uuid.uuid4())
    return ident


def synchronized(
    lock: Any = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:  # noqa: ANN401
    if lock is None:
        from threading import Lock

        lock = Lock()

    def inner(f: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            with lock:
                return f(*args, **kwargs)

        return wrapper

    return inner


def open_graphical_browser(url: str, new: int = 0, autoraise: bool = True) -> None:
    """Open a graphical web browser.

    This is basically like `webbrowser.open`, but without trying to launch CLI
    browsers at all. We're excluding those since it's undesirable to launch
    those when you're using vdirsyncer on a server. Rather copypaste the URL
    into the local browser, or use the URL-yanking features of your terminal
    emulator.
    """
    import webbrowser

    cli_names = {"www-browser", "links", "links2", "elinks", "lynx", "w3m"}

    # Accessing webbrowser private attributes for filtering CLI browsers
    if webbrowser._tryorder is None:  # type: ignore[attr-defined]
        webbrowser.register_standard_browsers()  # type: ignore[attr-defined]

    for name in webbrowser._tryorder:  # type: ignore[attr-defined]
        if name in cli_names:
            continue

        browser = webbrowser.get(name)
        if browser.open(url, new, autoraise):
            return

    raise RuntimeError("No graphical browser found. Please open the URL manually.")


@contextlib.contextmanager
def atomic_write(
    dest: str,
    mode: str = "wb",
    overwrite: bool = False,
) -> Generator[IO[Any], None, None]:
    if "w" not in mode:
        raise RuntimeError("`atomic_write` requires write access")

    fd, src = tempfile.mkstemp(prefix=os.path.basename(dest), dir=os.path.dirname(dest))
    file = os.fdopen(fd, mode=mode)

    try:
        yield file
    except Exception:
        os.unlink(src)
        raise
    else:
        file.flush()
        file.close()

        if overwrite:
            os.rename(src, dest)
        else:
            os.link(src, dest)
            os.unlink(src)
