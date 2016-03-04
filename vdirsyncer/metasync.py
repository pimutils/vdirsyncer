from . import exceptions, log
from .utils.compat import text_type

logger = log.get(__name__)


class MetaSyncError(exceptions.Error):
    pass


class MetaSyncConflict(MetaSyncError):
    key = None


def metasync(storage_a, storage_b, status, keys, conflict_resolution=None):
    def _a_to_b():
        logger.info(u'Copying {} to {}'.format(key, storage_b))
        storage_b.set_meta(key, a)
        status[key] = a

    def _b_to_a():
        logger.info(u'Copying {} to {}'.format(key, storage_a))
        storage_a.set_meta(key, b)
        status[key] = b

    def _resolve_conflict():
        if a == b:
            status[key] = a
        elif conflict_resolution is None:
            raise MetaSyncConflict(key=key)
        elif conflict_resolution == 'a wins':
            _a_to_b()
        elif conflict_resolution == 'b wins':
            _b_to_a()

    for key in keys:
        a = _normalize_value(storage_a.get_meta(key))
        b = _normalize_value(storage_b.get_meta(key))
        s = status.get(key)
        logger.debug(u'Key: {}'.format(key))
        logger.debug(u'A: {}'.format(a))
        logger.debug(u'B: {}'.format(b))
        logger.debug(u'S: {}'.format(s))

        if a != s and b != s:
            _resolve_conflict()
        elif a != s and b == s:
            _a_to_b()
        elif a == s and b != s:
            _b_to_a()
        else:
            assert a == b

    for key in set(status) - set(keys):
        del status[key]


def _normalize_value(value):
    if value is None:
        return value
    else:
        assert isinstance(value, text_type)
        return value.strip()
