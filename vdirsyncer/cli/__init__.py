import asyncio
import functools
import json
import logging
import sys

import aiohttp
import click
import click_log

from .. import BUGTRACKER_HOME
from .. import __version__

cli_logger = logging.getLogger(__name__)
click_log.basic_config("vdirsyncer")


class AppContext:
    def __init__(self):
        self.config = None
        self.fetched_params = {}
        self.logger = None


pass_context = click.make_pass_decorator(AppContext, ensure=True)


def catch_errors(f):
    @functools.wraps(f)
    def inner(*a, **kw):
        try:
            f(*a, **kw)
        except BaseException:
            from .utils import handle_cli_error

            handle_cli_error()
            sys.exit(1)

    return inner


@click.group()
@click_log.simple_verbosity_option("vdirsyncer")
@click.version_option(version=__version__)
@click.option("--config", "-c", metavar="FILE", help="Config file to use.")
@pass_context
@catch_errors
def app(ctx, config):
    """
    Synchronize calendars and contacts
    """

    if sys.platform == "win32":
        cli_logger.warning(
            "Vdirsyncer currently does not support Windows. "
            "You will likely encounter bugs. "
            "See {}/535 for more information.".format(BUGTRACKER_HOME)
        )

    if not ctx.config:
        from .config import load_config

        ctx.config = load_config(config)


main = app


def collections_arg_callback(ctx, param, value):
    """
    Expand the various CLI shortforms ("pair, pair/collection") to an iterable
    of (pair, collections).
    """
    # XXX: Ugly! pass_context should work everywhere.
    config = ctx.find_object(AppContext).config
    rv = {}
    for pair_and_collection in value or config.pairs:
        pair, collection = pair_and_collection, None
        if "/" in pair:
            pair, collection = pair.split("/")

        collections = rv.setdefault(pair, set())
        if collection:
            collections.add(collection)

    return rv.items()


collections_arg = click.argument(
    "collections", nargs=-1, callback=collections_arg_callback
)


@app.command()
@collections_arg
@click.option(
    "--force-delete/--no-force-delete",
    help=(
        "Do/Don't abort synchronization when all items are about "
        "to be deleted from both sides."
    ),
)
@pass_context
@catch_errors
def sync(ctx, collections, force_delete):
    """
    Synchronize the given collections or pairs. If no arguments are given, all
    will be synchronized.

    This command will not synchronize metadata, use `vdirsyncer metasync` for
    that.

    \b
    \b\bExamples:
    # Sync everything configured
    vdirsyncer sync

    \b
    # Sync the pairs "bob" and "frank"
    vdirsyncer sync bob frank

    \b
    # Sync only "first_collection" from the pair "bob"
    vdirsyncer sync bob/first_collection
    """
    from .tasks import prepare_pair
    from .tasks import sync_collection

    async def main(collection_names):
        async with aiohttp.TCPConnector(limit_per_host=16) as conn:
            tasks = []
            for pair_name, collections in collection_names:
                async for collection, config in prepare_pair(
                    pair_name=pair_name,
                    collections=collections,
                    config=ctx.config,
                    connector=conn,
                ):
                    tasks.append(
                        sync_collection(
                            collection=collection,
                            general=config,
                            force_delete=force_delete,
                            connector=conn,
                        )
                    )

            await asyncio.gather(*tasks)

    asyncio.run(main(collections))


@app.command()
@collections_arg
@pass_context
@catch_errors
def metasync(ctx, collections):
    """
    Synchronize metadata of the given collections or pairs.

    See the `sync` command for usage.
    """
    from .tasks import metasync_collection
    from .tasks import prepare_pair

    async def main(collection_names):
        async with aiohttp.TCPConnector(limit_per_host=16) as conn:

            for pair_name, collections in collection_names:
                collections = prepare_pair(
                    pair_name=pair_name,
                    collections=collections,
                    config=ctx.config,
                    connector=conn,
                )

                await asyncio.gather(
                    *[
                        metasync_collection(
                            collection=collection,
                            general=config,
                            connector=conn,
                        )
                        async for collection, config in collections
                    ]
                )

    asyncio.run(main(collections))


@app.command()
@click.argument("pairs", nargs=-1)
@click.option(
    "--list/--no-list",
    default=True,
    help=(
        "Whether to list all collections from both sides during discovery, "
        "for debugging. This is slow and may crash for broken servers."
    ),
)
@pass_context
@catch_errors
def discover(ctx, pairs, list):
    """
    Refresh collection cache for the given pairs.
    """
    from .tasks import discover_collections

    config = ctx.config

    async def main():
        async with aiohttp.TCPConnector(limit_per_host=16) as conn:
            for pair_name in pairs or config.pairs:
                await discover_collections(
                    status_path=config.general["status_path"],
                    pair=config.get_pair(pair_name),
                    from_cache=False,
                    list_collections=list,
                    connector=conn,
                )

    asyncio.run(main())


@app.command()
@click.argument("collection")
@click.option(
    "--repair-unsafe-uid/--no-repair-unsafe-uid",
    default=False,
    help=(
        "Some characters in item UIDs and URLs may cause problems "
        "with buggy software. Adding this option will reassign "
        "new UIDs to those items. This is disabled by default, "
        "which is equivalent to `--no-repair-unsafe-uid`."
    ),
)
@pass_context
@catch_errors
def repair(ctx, collection, repair_unsafe_uid):
    """
    Repair a given collection.

    Runs a few checks on the collection and applies some fixes to individual
    items that may improve general stability, also with other CalDAV/CardDAV
    clients. In particular, if you encounter URL-encoding-related issues with
    other clients, this command with --repair-unsafe-uid might help.

    \b
    \b\bExamples:
    # Repair the `foo` collection of the `calendars_local` storage
    vdirsyncer repair calendars_local/foo
    """
    from .tasks import repair_collection

    cli_logger.warning("This operation will take a very long time.")
    cli_logger.warning(
        "It's recommended to make a backup and "
        "turn off other client's synchronization features."
    )
    click.confirm("Do you want to continue?", abort=True)

    async def main():
        async with aiohttp.TCPConnector(limit_per_host=16) as conn:
            await repair_collection(
                ctx.config,
                collection,
                repair_unsafe_uid=repair_unsafe_uid,
                connector=conn,
            )

    asyncio.run(main())


@app.command()
@pass_context
@catch_errors
def showconfig(ctx: AppContext):
    """Show the current configuration.

    This is mostly intended to be used by scripts or other integrations.
    If you need additional information in this dump, please reach out.
    """
    config = {"storages": list(ctx.config.storages.values())}
    click.echo(json.dumps(config, indent=2))
