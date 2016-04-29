import json
import os
import string
from itertools import chain

from . import cli_logger
from .fetchparams import expand_fetch_params
from .. import PROJECT_HOME, exceptions
from ..utils import cached_property, expand_path
from ..utils.compat import text_type

try:
    from ConfigParser import RawConfigParser
except ImportError:
    from configparser import RawConfigParser

GENERAL_ALL = frozenset(['status_path', 'python2'])  # XXX: Py2
GENERAL_REQUIRED = frozenset(['status_path'])
SECTION_NAME_CHARS = frozenset(chain(string.ascii_letters, string.digits, '_'))


def validate_section_name(name, section_type):
    invalid = set(name) - SECTION_NAME_CHARS
    if invalid:
        chars_display = ''.join(sorted(SECTION_NAME_CHARS))
        raise exceptions.UserError(
            'The {}-section "{}" contains invalid characters. Only '
            'the following characters are allowed for storage and '
            'pair names:\n{}'.format(section_type, name, chars_display))


def _validate_general_section(general_config):
    invalid = set(general_config) - GENERAL_ALL
    missing = GENERAL_REQUIRED - set(general_config)
    problems = []

    if invalid:
        problems.append(u'general section doesn\'t take the parameters: {}'
                        .format(u', '.join(invalid)))

    if missing:
        problems.append(u'general section is missing the parameters: {}'
                        .format(u', '.join(missing)))

    if problems:
        raise exceptions.UserError(
            u'Invalid general section. Copy the example '
            u'config from the repository and edit it: {}'
            .format(PROJECT_HOME), problems=problems)


def _validate_pair_section(pair_config):
    try:
        collections = pair_config['collections']
    except KeyError:
        raise ValueError('collections parameter missing.\n\n'
                         'As of 0.9.0 this parameter has no default anymore. '
                         'Set `collections = null` explicitly in your pair '
                         'config.')

    if collections is None:
        return

    if not isinstance(collections, list):
        raise ValueError('`collections` parameter must be a list or `null`.')

    collection_names = set()

    for i, collection in enumerate(collections):
        if isinstance(collection, (text_type, bytes)):
            collection_name = collection
        elif isinstance(collection, list) and \
                len(collection) == 3 and \
                all(isinstance(x, (text_type, bytes)) for x in collection):
            collection_name = collection[0]
        else:
            raise ValueError('`collections` parameter, position {i}:'
                             'Expected string or list of three strings.'
                             .format(i=i))

        if collection_name in collection_names:
            raise ValueError('Duplicate values in collections parameter.')
        collection_names.add(collection_name)


def load_config(fname=None):
    if fname is None:
        fname = os.environ.get('VDIRSYNCER_CONFIG', None)
    if fname is None:
        fname = expand_path('~/.vdirsyncer/config')
        if not os.path.exists(fname):
            xdg_config_dir = os.environ.get('XDG_CONFIG_HOME',
                                            expand_path('~/.config/'))
            fname = os.path.join(xdg_config_dir, 'vdirsyncer/config')

    try:
        with open(fname) as f:
            general, pairs, storages = read_config(f)
    except Exception as e:
        raise exceptions.UserError(
            'Error during reading config {}: {}'
            .format(fname, e)
        )

    return Config(general, pairs, storages)


def read_config(f):
    c = RawConfigParser()
    c.readfp(f)

    def get_options(s):
        return dict(parse_options(c.items(s), section=s))

    general = {}
    pairs = {}
    storages = {}

    def handle_storage(storage_name, options):
        storages.setdefault(storage_name, {}).update(options)
        storages[storage_name]['instance_name'] = storage_name

    def handle_pair(pair_name, options):
        _validate_pair_section(options)
        a, b = options.pop('a'), options.pop('b')
        pairs[pair_name] = a, b, options

    def handle_general(_, options):
        if general:
            raise exceptions.UserError(
                'More than one general section in config file.')
        general.update(options)

    def bad_section(name, options):
        cli_logger.error('Unknown section: {}'.format(name))

    handlers = {'storage': handle_storage, 'pair': handle_pair, 'general':
                handle_general}

    for section in c.sections():
        if ' ' in section:
            section_type, name = section.split(' ', 1)
        else:
            section_type = name = section

        try:
            validate_section_name(name, section_type)
            f = handlers.get(section_type, bad_section)
            f(name, get_options(section))
        except ValueError as e:
            raise exceptions.UserError(
                'Section `{}`: {}'.format(section, str(e)))

    _validate_general_section(general)
    if getattr(f, 'name', None):
        general['status_path'] = os.path.join(
            os.path.dirname(f.name),
            expand_path(general['status_path'])
        )
    return general, pairs, storages


def parse_config_value(value):
    try:
        return json.loads(value)
    except ValueError:
        pass

    for wrong, right in [
        (('on', 'yes'), 'true'),
        (('off', 'no'), 'false'),
        (('none',), 'null')
    ]:
        if value.lower() in wrong + (right,):
            cli_logger.warning('You probably meant {} instead of "{}", which '
                               'will now be interpreted as a literal string.'
                               .format(right, value))

    if '#' in value:
        raise ValueError('Invalid value:{}\n'
                         'Use double quotes (") if you want to use hashes in '
                         'your value.')

    if len(value.splitlines()) > 1:
        # ConfigParser's barrier for mistaking an arbitrary line for the
        # continuation of a value is awfully low. The following example will
        # also contain the second line in the value:
        #
        # foo = bar
        #  # my comment
        raise ValueError('No multiline-values allowed:\n{}'.format(value))

    return value


def parse_options(items, section=None):
    for key, value in items:
        try:
            yield key, parse_config_value(value)
        except ValueError as e:
            raise ValueError('Section "{}", option "{}": {}'
                             .format(section, key, e))


class Config(object):
    def __init__(self, general, pairs, storages):
        self.general = general
        self.pairs = pairs
        self.storages = storages

    def get_storage_args(self, storage_name, pair_name=None):
        try:
            args = self.storages[storage_name]
        except KeyError:
            pair_pref = 'Pair {}: '.format(pair_name) if pair_name else ''
            raise exceptions.UserError(
                '{}Storage {!r} not found. '
                'These are the configured storages: {}'
                .format(pair_pref, storage_name, list(self.storages))
            )
        else:
            return expand_fetch_params(args)

    def get_pair(self, pair_name):
        try:
            return PairConfig(self, pair_name, *self.pairs[pair_name])
        except KeyError as e:
            raise exceptions.PairNotFound(e, pair_name=pair_name)


class PairConfig(object):
    def __init__(self, config, name, name_a, name_b, pair_options):
        self._config = config
        self.name = name
        self.name_a = name_a
        self.name_b = name_b
        self.options = pair_options

    @cached_property
    def config_a(self):
        return self._config.get_storage_args(self.name_a, pair_name=self.name)

    @cached_property
    def config_b(self):
        return self._config.get_storage_args(self.name_b, pair_name=self.name)


class CollectionConfig(object):
    def __init__(self, pair, name, config_a, config_b):
        self.pair = pair
        self._config = pair._config
        self.name = name
        self.config_a = config_a
        self.config_b = config_b
