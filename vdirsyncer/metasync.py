import logging

from . import exceptions
from .storage.base import normalize_meta_value

logger = logging.getLogger(__name__)


class MetaSyncError(exceptions.Error):
    pass


class MetaSyncConflict(MetaSyncError):
    key = None


def status_set_key(status, key, value):
    if value is None:
        status.pop(key, None)
    else:
        status[key] = value


async def metasync(storage_a, storage_b, status, keys, conflict_resolution=None):
    async def _a_to_b():
        logger.info(f"Copying {key} to {storage_b}")
        await storage_b.set_meta(key, a)
        status_set_key(status, key, a)

    async def _b_to_a():
        logger.info(f"Copying {key} to {storage_a}")
        await storage_a.set_meta(key, b)
        status_set_key(status, key, b)

    async def _resolve_conflict():
        if a == b:
            status_set_key(status, key, a)
        elif conflict_resolution == "a wins":
            await _a_to_b()
        elif conflict_resolution == "b wins":
            await _b_to_a()
        else:
            if callable(conflict_resolution):
                logger.warning("Custom commands don't work on metasync.")
            elif conflict_resolution is not None:
                raise exceptions.UserError("Invalid conflict resolution setting.")
            raise MetaSyncConflict(key)

    for key in keys:
        a = await storage_a.get_meta(key)
        b = await storage_b.get_meta(key)
        s = normalize_meta_value(status.get(key))
        logger.debug(f"Key: {key}")
        logger.debug(f"A: {a}")
        logger.debug(f"B: {b}")
        logger.debug(f"S: {s}")

        if a != s and b != s or storage_a.read_only or storage_b.read_only:
            await _resolve_conflict()
        elif a != s and b == s:
            await _a_to_b()
        elif a == s and b != s:
            await _b_to_a()
        else:
            assert a == b

    for key in set(status) - set(keys):
        del status[key]
