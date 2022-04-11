import logging

import click

from .. import exceptions
from ..utils import expand_path
from ..utils import synchronized
from . import AppContext

SUFFIX = ".fetch"

logger = logging.getLogger(__name__)


def expand_fetch_params(config):
    config = dict(config)
    for key in list(config):
        if not key.endswith(SUFFIX):
            continue

        newkey = key[: -len(SUFFIX)]
        if newkey in config:
            raise ValueError(f"Can't set {key} and {newkey}.")
        config[newkey] = _fetch_value(config[key], key)
        del config[key]

    return config


@synchronized()
def _fetch_value(opts, key):
    if not isinstance(opts, list):
        raise ValueError(f"Invalid value for {key}: Expected a list, found {opts!r}.")
    if not opts:
        raise ValueError("Expected list of length > 0.")

    try:
        ctx = click.get_current_context().find_object(AppContext)
        if ctx is None:
            raise RuntimeError()
        password_cache = ctx.fetched_params
    except RuntimeError:
        password_cache = {}

    cache_key = tuple(opts)
    if cache_key in password_cache:
        rv = password_cache[cache_key]
        logger.debug(f"Found cached value for {opts!r}.")
        if isinstance(rv, BaseException):
            raise rv
        return rv

    strategy = opts[0]
    try:
        strategy_fn = STRATEGIES[strategy]
    except KeyError:
        raise exceptions.UserError(f"Unknown strategy: {strategy}")

    logger.debug(f"Fetching value for {key} with {strategy} strategy.")
    try:
        rv = strategy_fn(*opts[1:])
    except (click.Abort, KeyboardInterrupt) as e:
        password_cache[cache_key] = e
        raise
    else:
        if not rv:
            raise exceptions.UserError(
                "Empty value for {}, this most likely "
                "indicates an error.".format(key)
            )
        password_cache[cache_key] = rv
        return rv


def _strategy_command(*command: str, shell: bool = False):
    """Execute a user-specified command and return its output."""
    import subprocess

    # Normalize path of every path member.
    # If there is no path specified then nothing will happen.
    # Makes this a list to avoid it being exhausted on the first iteration.
    expanded_command = list(map(expand_path, command))

    try:
        stdout = subprocess.check_output(expanded_command, text=True, shell=shell)
        return stdout.strip("\n")
    except OSError as e:
        cmd = " ".join(expanded_command)
        raise exceptions.UserError(f"Failed to execute command: {cmd}\n{str(e)}")


def _strategy_shell(*command: str):
    """Execute a user-specified command string in a shell and return its output."""
    return _strategy_command(*command, shell=True)


def _strategy_prompt(text):
    return click.prompt(text, hide_input=True)


STRATEGIES = {
    "command": _strategy_command,
    "shell": _strategy_shell,
    "prompt": _strategy_prompt,
}
