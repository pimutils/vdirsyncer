import asyncio
import hashlib
import json
import logging
import sys

import aiohttp
import aiostream

from .. import exceptions
from .utils import handle_collection_not_found
from .utils import handle_storage_init_error
from .utils import load_status
from .utils import save_status
from .utils import storage_class_from_config
from .utils import storage_instance_from_config

# Increase whenever upgrade potentially breaks discovery cache and collections
# should be re-discovered
DISCOVERY_CACHE_VERSION = 1

logger = logging.getLogger(__name__)


def _get_collections_cache_key(pair):
    m = hashlib.sha256()
    j = json.dumps(
        [
            DISCOVERY_CACHE_VERSION,
            pair.collections,
            pair.config_a,
            pair.config_b,
        ],
        sort_keys=True,
    )
    m.update(j.encode("utf-8"))
    return m.hexdigest()


async def collections_for_pair(
    status_path,
    pair,
    from_cache=True,
    list_collections=False,
    *,
    connector: aiohttp.TCPConnector,
):
    """Determine all configured collections for a given pair. Takes care of
    shortcut expansion and result caching.

    :param status_path: The path to the status directory.
    :param from_cache: Whether to load from cache (aborting on cache miss) or
        discover and save to cache.

    :returns: iterable of (collection, (a_args, b_args))
    """
    cache_key = _get_collections_cache_key(pair)
    if from_cache:
        rv = load_status(status_path, pair.name, data_type="collections")
        if rv and rv.get("cache_key", None) == cache_key:
            return list(
                _expand_collections_cache(
                    rv["collections"], pair.config_a, pair.config_b
                )
            )
        elif rv:
            raise exceptions.UserError(
                "Detected change in config file, "
                "please run `vdirsyncer discover {}`.".format(pair.name)
            )
        else:
            raise exceptions.UserError(
                "Please run `vdirsyncer discover {}` "
                " before synchronization.".format(pair.name)
            )

    logger.info(f"Discovering collections for pair {pair.name}")

    a_discovered = _DiscoverResult(pair.config_a, connector=connector)
    b_discovered = _DiscoverResult(pair.config_b, connector=connector)

    if list_collections:
        # TODO: We should gather data and THEN print, so it can be async.
        await _print_collections(
            pair.config_a["instance_name"],
            a_discovered.get_self,
            connector=connector,
        )
        await _print_collections(
            pair.config_b["instance_name"],
            b_discovered.get_self,
            connector=connector,
        )

    # We have to use a list here because the special None/null value would get
    # mangled to string (because JSON objects always have string keys).
    rv = await aiostream.stream.list(
        expand_collections(
            shortcuts=pair.collections,
            config_a=pair.config_a,
            config_b=pair.config_b,
            get_a_discovered=a_discovered.get_self,
            get_b_discovered=b_discovered.get_self,
            _handle_collection_not_found=handle_collection_not_found,
        )
    )

    await _sanity_check_collections(rv, connector=connector)

    save_status(
        status_path,
        pair.name,
        data_type="collections",
        data={
            "collections": list(
                _compress_collections_cache(rv, pair.config_a, pair.config_b)
            ),
            "cache_key": cache_key,
        },
    )
    return rv


async def _sanity_check_collections(collections, *, connector):
    tasks = []

    for _, (a_args, b_args) in collections:
        tasks.append(storage_instance_from_config(a_args, connector=connector))
        tasks.append(storage_instance_from_config(b_args, connector=connector))

    await asyncio.gather(*tasks)


def _compress_collections_cache(collections, config_a, config_b):
    def deduplicate(x, y):
        rv = {}
        for key, value in x.items():
            if key not in y or y[key] != value:
                rv[key] = value

        return rv

    for name, (a, b) in collections:
        yield name, (deduplicate(a, config_a), deduplicate(b, config_b))


def _expand_collections_cache(collections, config_a, config_b):
    for name, (a_delta, b_delta) in collections:
        a = dict(config_a)
        a.update(a_delta)

        b = dict(config_b)
        b.update(b_delta)

        yield name, (a, b)


class _DiscoverResult:
    def __init__(self, config, *, connector):
        self._cls, _ = storage_class_from_config(config)

        if self._cls.__name__ in [
            "CardDAVStorage",
            "CalDAVStorage",
            "GoogleCalendarStorage",
        ]:
            assert connector is not None
            config["connector"] = connector

        self._config = config
        self._discovered = None

    async def get_self(self):
        if self._discovered is None:
            self._discovered = await self._discover()
        return self._discovered

    async def _discover(self):
        try:
            discovered = await aiostream.stream.list(self._cls.discover(**self._config))
        except NotImplementedError:
            return {}
        except Exception:
            return handle_storage_init_error(self._cls, self._config)
        else:
            storage_type = self._config["type"]
            rv = {}
            for args in discovered:
                args["type"] = storage_type
                rv[args["collection"]] = args
            return rv


async def expand_collections(
    shortcuts,
    config_a,
    config_b,
    get_a_discovered,
    get_b_discovered,
    _handle_collection_not_found,
):
    handled_collections = set()

    if shortcuts is None:
        shortcuts = [None]

    for shortcut in shortcuts:
        if shortcut == "from a":
            collections = await get_a_discovered()
        elif shortcut == "from b":
            collections = await get_b_discovered()
        else:
            collections = [shortcut]

        for collection in collections:
            if isinstance(collection, list):
                collection, collection_a, collection_b = collection
            else:
                collection_a = collection_b = collection

            if collection in handled_collections:
                continue
            handled_collections.add(collection)

            a_args = await _collection_from_discovered(
                get_a_discovered,
                collection_a,
                config_a,
                _handle_collection_not_found,
            )
            b_args = await _collection_from_discovered(
                get_b_discovered,
                collection_b,
                config_b,
                _handle_collection_not_found,
            )

            yield collection, (a_args, b_args)


async def _collection_from_discovered(
    get_discovered, collection, config, _handle_collection_not_found
):
    if collection is None:
        args = dict(config)
        args["collection"] = None
        return args

    try:
        return (await get_discovered())[collection]
    except KeyError:
        return await _handle_collection_not_found(config, collection)


async def _print_collections(
    instance_name: str,
    get_discovered,
    *,
    connector: aiohttp.TCPConnector,
):
    try:
        discovered = await get_discovered()
    except exceptions.UserError:
        raise
    except Exception:
        # Unless discovery failed due to a user-inflicted error (instanceof
        # UserError), we don't even know if the storage supports discovery
        # properly. So we can't abort.
        import traceback

        logger.debug("".join(traceback.format_tb(sys.exc_info()[2])))
        logger.warning(
            "Failed to discover collections for {}, use `-vdebug` "
            "to see the full traceback.".format(instance_name)
        )
        return
    logger.info(f"{instance_name}:")
    tasks = []
    for args in discovered.values():
        tasks.append(_print_single_collection(args, instance_name, connector))

    await asyncio.gather(*tasks)


async def _print_single_collection(args, instance_name, connector):
    collection = args["collection"]
    if collection is None:
        return

    args["instance_name"] = instance_name
    try:
        storage = await storage_instance_from_config(
            args,
            create=False,
            connector=connector,
        )
        displayname = await storage.get_meta("displayname")
    except Exception:
        displayname = ""

    logger.info(
        "  - {}{}".format(
            json.dumps(collection),
            f' ("{displayname}")' if displayname and displayname != collection else "",
        )
    )
