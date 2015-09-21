# -*- coding: utf-8 -*-

import functools
import sys
from multiprocessing import cpu_count

import click

import click_log

from .. import __version__, log


cli_logger = log.get(__name__)


class AppContext(object):
    def __init__(self):
        self.config = None
        self.fetched_params = {}
        self.logger = None


pass_context = click.make_pass_decorator(AppContext, ensure=True)


class CliError(RuntimeError):
    def __init__(self, msg, problems=None):
        self.msg = msg
        self.problems = problems
        RuntimeError.__init__(self, msg)

    def format_cli(self):
        msg = self.msg.rstrip(u'.:')
        if self.problems:
            msg += u':'
            if len(self.problems) == 1:
                msg += u' {}'.format(self.problems[0])
            else:
                msg += u'\n' + u'\n  - '.join(self.problems) + u'\n\n'

        return msg


def catch_errors(f):
    @functools.wraps(f)
    def inner(*a, **kw):
        try:
            f(*a, **kw)
        except:
            from .utils import handle_cli_error
            handle_cli_error()
            sys.exit(1)

    return inner


def validate_verbosity(ctx, param, value):
    x = getattr(log.logging, value.upper(), None)
    if x is None:
        raise click.BadParameter(
            'Must be CRITICAL, ERROR, WARNING, INFO or DEBUG, not {}'
            .format(value)
        )
    return x


@click.group()
@click_log.init('vdirsyncer')
@click_log.simple_verbosity_option()
@click.version_option(version=__version__)
@pass_context
@catch_errors
def app(ctx):
    '''
    vdirsyncer -- synchronize calendars and contacts
    '''
    from .config import load_config

    if not ctx.config:
        ctx.config = load_config()

main = app


def max_workers_callback(ctx, param, value):
    if value == 0:
        if click_log.get_level() == log.logging.DEBUG:
            value = 1
        else:
            value = cpu_count() * 5

    cli_logger.debug('Using {} maximal workers.'.format(value))
    return value


max_workers_option = click.option(
    '--max-workers', default=0, type=click.IntRange(min=0, max=None),
    callback=max_workers_callback,
    help=('Use at most this many connections. With debug messages enabled, '
          'the default is 1, otherwise one connection per collection is '
          'opened.')
)


def collections_arg_callback(ctx, param, value):
    '''
    Expand the various CLI shortforms ("pair, pair/collection") to an iterable
    of (pair, collections).
    '''
    # XXX: Ugly! pass_context should work everywhere.
    config = ctx.find_object(AppContext).config
    rv = {}
    for pair_and_collection in (value or config.pairs):
        pair, collection = pair_and_collection, None
        if '/' in pair:
            pair, collection = pair.split('/')

        collections = rv.setdefault(pair, set())
        if collection:
            collections.add(collection)

    return rv.items()


collections_arg = click.argument('collections', nargs=-1,
                                 callback=collections_arg_callback)


@app.command()
@collections_arg
@click.option('--force-delete/--no-force-delete',
              help=('Do/Don\'t abort synchronization when all items are about '
                    'to be deleted from both sides.'))
@max_workers_option
@pass_context
@catch_errors
def sync(ctx, collections, force_delete, max_workers):
    '''
    Synchronize the given collections or pairs. If no arguments are given, all
    will be synchronized.

    This command will not synchronize metadata, use `vdirsyncer metasync` for
    that.

    Examples:

        `vdirsyncer sync` will sync everything configured.

        `vdirsyncer sync bob frank` will sync the pairs "bob" and "frank".

        `vdirsyncer sync bob/first_collection` will sync "first_collection"
        from the pair "bob".
    '''
    from .tasks import prepare_pair, sync_collection
    from .utils import WorkerQueue

    wq = WorkerQueue(max_workers)

    with wq.join():
        for pair_name, collections in collections:
            wq.put(functools.partial(prepare_pair, pair_name=pair_name,
                                     collections=collections,
                                     config=ctx.config,
                                     force_delete=force_delete,
                                     callback=sync_collection))


@app.command()
@collections_arg
@max_workers_option
@pass_context
@catch_errors
def metasync(ctx, collections, max_workers):
    '''
    Synchronize metadata of the given collections or pairs.

    See the `sync` command regarding the PAIRS argument.
    '''
    from .tasks import prepare_pair, metasync_collection
    from .utils import WorkerQueue

    wq = WorkerQueue(max_workers)

    with wq.join():
        for pair_name, collections in collections:
            wq.put(functools.partial(prepare_pair, pair_name=pair_name,
                                     collections=collections,
                                     config=ctx.config,
                                     callback=metasync_collection))


@app.command()
@click.argument('pairs', nargs=-1)
@max_workers_option
@pass_context
@catch_errors
def discover(ctx, pairs, max_workers):
    '''
    Refresh collection cache for the given pairs.
    '''
    from .tasks import discover_collections
    from .utils import WorkerQueue
    config = ctx.config
    wq = WorkerQueue(max_workers)

    with wq.join():
        for pair_name in (pairs or config.pairs):
            pair = config.get_pair(pair_name)

            wq.put(functools.partial(
                discover_collections,
                status_path=config.general['status_path'],
                pair=pair,
                skip_cache=True,
            ))


@app.command()
@click.argument('collection')
@pass_context
@catch_errors
def repair(ctx, collection):
    '''
    Repair a given collection.

    Runs a few checks on the collection and applies some fixes to individual
    items that may improve general stability, also with other CalDAV/CardDAV
    clients. In particular, if you encounter URL-encoding-related issues with
    other clients, this command might help.

    Example: `vdirsyncer repair calendars_local/foo` repairs the `foo`
    collection of the `calendars_local` storage.
    '''
    from .tasks import repair_collection

    cli_logger.warning('This operation will take a very long time.')
    cli_logger.warning('It\'s recommended to turn off other client\'s '
                       'synchronization features.')
    click.confirm('Do you want to continue?', abort=True)
    repair_collection(ctx.config, collection)

# Not sure if useful. I originally wanted it because:
# * my password manager has a timeout for caching the master password
# * when calling vdirsyncer in a cronjob, the master password prompt would
#   randomly pop up
# So I planned on piping a FIFO to vdirsyncer, and writing to that FIFO from a
# cronjob.

try:
    import click_repl
    click_repl.register_repl(app)
except ImportError:
    pass
