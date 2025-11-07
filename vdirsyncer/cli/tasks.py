from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from vdirsyncer import exceptions
from vdirsyncer import sync

from .config import CollectionConfig
from .discover import DiscoverResult
from .discover import collections_for_pair
from .discover import storage_instance_from_config
from .utils import JobFailed
from .utils import cli_logger
from .utils import get_status_name
from .utils import handle_cli_error
from .utils import load_status
from .utils import manage_sync_status
from .utils import save_status


async def prepare_pair(
    pair_name: str, collections: Any, config: Any, *, connector: aiohttp.TCPConnector
) -> AsyncIterator[tuple[CollectionConfig, Any]]:
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
                f"Pair {pair_name}: Collection {json.dumps(collection_name)} not found."
                f"These are the configured collections:\n{list(all_collections)}"
            )

        collection = CollectionConfig(pair, collection_name, config_a, config_b)
        yield collection, config.general


async def sync_collection(
    collection: CollectionConfig,
    general: Any,
    force_delete: bool,
    *,
    connector: aiohttp.TCPConnector,
) -> None:
    pair = collection.pair
    status_name = get_status_name(pair.name, collection.name)

    try:
        cli_logger.info(f"Syncing {status_name}")

        a = await storage_instance_from_config(collection.config_a, connector=connector)
        b = await storage_instance_from_config(collection.config_b, connector=connector)

        sync_failed = False

        def error_callback(e: Exception) -> None:
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
            raise JobFailed
    except JobFailed:
        raise
    except BaseException:
        handle_cli_error(status_name)
        raise JobFailed


async def discover_collections(pair: Any, **kwargs: Any) -> None:
    rv = await collections_for_pair(pair=pair, **kwargs)
    collections: list[Any] | None = [c for c, (a, b) in rv]
    if collections == [None]:
        collections = None
    cli_logger.info(f"Saved for {pair.name}: collections = {json.dumps(collections)}")


async def repair_collection(
    config: Any,
    collection: str,
    repair_unsafe_uid: bool,
    *,
    connector: aiohttp.TCPConnector,
) -> None:
    from vdirsyncer.repair import repair_storage

    storage_name: str
    collection_name: str | None
    storage_name, collection_name = collection, None
    if "/" in storage_name:
        storage_name, collection_name = storage_name.split("/")

    config = config.get_storage_args(storage_name)
    # If storage type has a slash, ignore it and anything after it.
    storage_type = config["type"].split("/")[0]

    if collection_name is not None:
        cli_logger.info("Discovering collections (skipping cache).")
        get_discovered = DiscoverResult(config, connector=connector)
        discovered = await get_discovered.get_self()
        for config in discovered.values():
            if config["collection"] == collection_name:
                break
        else:
            raise exceptions.UserError(
                f"Couldn't find collection {collection_name} for "
                f"storage {storage_name}."
            )

    config["type"] = storage_type
    storage = await storage_instance_from_config(config, connector=connector)

    cli_logger.info(f"Repairing {storage_name}/{collection_name}")
    cli_logger.warning("Make sure no other program is talking to the server.")
    await repair_storage(storage, repair_unsafe_uid=repair_unsafe_uid)


async def metasync_collection(
    collection: CollectionConfig, general: Any, *, connector: aiohttp.TCPConnector
) -> None:
    from vdirsyncer.metasync import metasync

    pair = collection.pair
    status_name = get_status_name(pair.name, collection.name)

    try:
        cli_logger.info(f"Metasyncing {status_name}")

        status = load_status(
            general["status_path"],
            pair.name,
            collection.name,
            data_type="metadata",
        )

        a = await storage_instance_from_config(collection.config_a, connector=connector)
        b = await storage_instance_from_config(collection.config_b, connector=connector)

        metadata_keys: list[str] = list(pair.metadata) if pair.metadata else []
        await metasync(
            a,
            b,
            status,
            conflict_resolution=pair.conflict_resolution,
            keys=metadata_keys,
        )
    except BaseException:
        handle_cli_error(status_name)
        raise JobFailed

    save_status(
        base_path=general["status_path"],
        pair=pair.name,
        data_type="metadata",
        data=status,
        collection=collection.name,
    )
