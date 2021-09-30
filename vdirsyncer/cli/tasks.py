import json

import aiohttp

from .. import exceptions
from .. import sync
from .config import CollectionConfig
from .discover import collections_for_pair
from .discover import storage_class_from_config
from .discover import storage_instance_from_config
from .utils import JobFailed
from .utils import cli_logger
from .utils import get_status_name
from .utils import handle_cli_error
from .utils import load_status
from .utils import manage_sync_status
from .utils import save_status


async def prepare_pair(pair_name, collections, config, *, connector):
    pair = config.get_pair(pair_name)

    all_collections = dict(
        await collections_for_pair(
            status_path=config.general["status_path"],
            pair=pair,
            connector=connector,
        )
    )

    for collection_name in collections or all_collections:
        try:
            config_a, config_b = all_collections[collection_name]
        except KeyError:
            raise exceptions.UserError(
                "Pair {}: Collection {} not found. These are the "
                "configured collections:\n{}".format(
                    pair_name, json.dumps(collection_name), list(all_collections)
                )
            )

        collection = CollectionConfig(pair, collection_name, config_a, config_b)
        yield collection, config.general


async def sync_collection(
    collection,
    general,
    force_delete,
    *,
    connector: aiohttp.TCPConnector,
):
    pair = collection.pair
    status_name = get_status_name(pair.name, collection.name)

    try:
        cli_logger.info(f"Syncing {status_name}")

        a = await storage_instance_from_config(collection.config_a, connector=connector)
        b = await storage_instance_from_config(collection.config_b, connector=connector)

        sync_failed = False

        def error_callback(e):
            nonlocal sync_failed
            sync_failed = True
            handle_cli_error(status_name, e)

        with manage_sync_status(
            general["status_path"], pair.name, collection.name
        ) as status:
            await sync.sync(
                a,
                b,
                status,
                conflict_resolution=pair.conflict_resolution,
                force_delete=force_delete,
                error_callback=error_callback,
                partial_sync=pair.partial_sync,
            )

        if sync_failed:
            raise JobFailed()
    except JobFailed:
        raise
    except BaseException:
        handle_cli_error(status_name)
        raise JobFailed()


async def discover_collections(pair, **kwargs):
    rv = await collections_for_pair(pair=pair, **kwargs)
    collections = [c for c, (a, b) in rv]
    if collections == [None]:
        collections = None
    cli_logger.info(f"Saved for {pair.name}: collections = {json.dumps(collections)}")


async def repair_collection(
    config,
    collection,
    repair_unsafe_uid,
    *,
    connector: aiohttp.TCPConnector,
):
    from ..repair import repair_storage

    storage_name, collection = collection, None
    if "/" in storage_name:
        storage_name, collection = storage_name.split("/")

    config = config.get_storage_args(storage_name)
    storage_type = config["type"]

    if collection is not None:
        cli_logger.info("Discovering collections (skipping cache).")
        cls, config = storage_class_from_config(config)
        async for config in cls.discover(**config):
            if config["collection"] == collection:
                break
        else:
            raise exceptions.UserError(
                "Couldn't find collection {} for storage {}.".format(
                    collection, storage_name
                )
            )

    config["type"] = storage_type
    storage = await storage_instance_from_config(config, connector=connector)

    cli_logger.info(f"Repairing {storage_name}/{collection}")
    cli_logger.warning("Make sure no other program is talking to the server.")
    await repair_storage(storage, repair_unsafe_uid=repair_unsafe_uid)


async def metasync_collection(collection, general, *, connector: aiohttp.TCPConnector):
    from ..metasync import metasync

    pair = collection.pair
    status_name = get_status_name(pair.name, collection.name)

    try:
        cli_logger.info(f"Metasyncing {status_name}")

        status = (
            load_status(
                general["status_path"], pair.name, collection.name, data_type="metadata"
            )
            or {}
        )

        a = await storage_instance_from_config(collection.config_a, connector=connector)
        b = await storage_instance_from_config(collection.config_b, connector=connector)

        await metasync(
            a,
            b,
            status,
            conflict_resolution=pair.conflict_resolution,
            keys=pair.metadata,
        )
    except BaseException:
        handle_cli_error(status_name)
        raise JobFailed()

    save_status(
        general["status_path"],
        pair.name,
        collection.name,
        data_type="metadata",
        data=status,
    )
