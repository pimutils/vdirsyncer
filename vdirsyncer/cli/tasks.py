import functools
import json

from .. import exceptions
from .. import sync
from .config import CollectionConfig
from .discover import collections_for_pair
from .discover import storage_class_from_config
from .discover import storage_instance_from_config
from .utils import cli_logger
from .utils import get_status_name
from .utils import handle_cli_error
from .utils import JobFailed
from .utils import load_status
from .utils import manage_sync_status
from .utils import save_status


def prepare_pair(wq, pair_name, collections, config, callback, **kwargs):
    pair = config.get_pair(pair_name)

    all_collections = dict(
        collections_for_pair(status_path=config.general["status_path"], pair=pair)
    )

    # spawn one worker less because we can reuse the current one
    new_workers = -1
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
        new_workers += 1

        collection = CollectionConfig(pair, collection_name, config_a, config_b)
        wq.put(
            functools.partial(
                callback, collection=collection, general=config.general, **kwargs
            )
        )

    for _ in range(new_workers):
        wq.spawn_worker()


def sync_collection(wq, collection, general, force_delete):
    pair = collection.pair
    status_name = get_status_name(pair.name, collection.name)

    try:
        cli_logger.info(f"Syncing {status_name}")

        a = storage_instance_from_config(collection.config_a)
        b = storage_instance_from_config(collection.config_b)

        sync_failed = False

        def error_callback(e):
            nonlocal sync_failed
            sync_failed = True
            handle_cli_error(status_name, e)

        with manage_sync_status(
            general["status_path"], pair.name, collection.name
        ) as status:
            sync.sync(
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


def discover_collections(wq, pair, **kwargs):
    rv = collections_for_pair(pair=pair, **kwargs)
    collections = list(c for c, (a, b) in rv)
    if collections == [None]:
        collections = None
    cli_logger.info(
        "Saved for {}: collections = {}".format(pair.name, json.dumps(collections))
    )


def repair_collection(config, collection, repair_unsafe_uid):
    from ..repair import repair_storage

    storage_name, collection = collection, None
    if "/" in storage_name:
        storage_name, collection = storage_name.split("/")

    config = config.get_storage_args(storage_name)
    storage_type = config["type"]

    if collection is not None:
        cli_logger.info("Discovering collections (skipping cache).")
        cls, config = storage_class_from_config(config)
        for config in cls.discover(**config):
            if config["collection"] == collection:
                break
        else:
            raise exceptions.UserError(
                "Couldn't find collection {} for storage {}.".format(
                    collection, storage_name
                )
            )

    config["type"] = storage_type
    storage = storage_instance_from_config(config)

    cli_logger.info(f"Repairing {storage_name}/{collection}")
    cli_logger.warning("Make sure no other program is talking to the server.")
    repair_storage(storage, repair_unsafe_uid=repair_unsafe_uid)


def metasync_collection(wq, collection, general):
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

        a = storage_instance_from_config(collection.config_a)
        b = storage_instance_from_config(collection.config_b)

        metasync(
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
