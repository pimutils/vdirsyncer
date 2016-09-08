import json
import os
import string
from itertools import chain

from . import cli_logger
from .fetchparams import expand_fetch_params
from .. import PROJECT_HOME, exceptions
from ..utils import cached_property, expand_path

try:
    from ConfigParser import RawConfigParser
except ImportError:
    from configparser import RawConfigParser

GENERAL_ALL = frozenset(['status_path'])
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
        try:
            if isinstance(collection, (str, bytes)):
                collection_name = collection
            elif isinstance(collection, list):
                e = ValueError(
                    'Expected list of format '
                    '["config_name", "storage_a_name", "storage_b_name"]'
                    .format(len(collection)))
                if len(collection) != 3:
                    raise e

                if not isinstance(collection[0], (str, bytes)):
                    raise e

                for x in collection[1:]:
                    if x is not None and not isinstance(x, (str, bytes)):
                        raise e

                collection_name = collection[0]
            else:
                raise ValueError('Expected string or list of three strings.')

            if collection_name in collection_names:
                raise ValueError('Duplicate value.')
            collection_names.add(collection_name)
        except ValueError as e:
            raise ValueError('`collections` parameter, position {i}: {e}'
                             .format(i=i, e=str(e)))


class ConfigReader:
    def __init__(self, f):
        self._file = f
        self._parser = c = RawConfigParser()
        c.readfp(f)
        self._seen_names = set()

        self._general = {}
        self._pairs = {}
        self._storages = {}

        self._handlers = {
            'general': self._handle_general,
            'pair': self._handle_pair,
            'storage': self._handle_storage
        }

    def _get_options(self, s):
        return dict(parse_options(self._parser.items(s), section=s))

    def _handle_storage(self, storage_name, options):
        options['instance_name'] = storage_name
        self._storages[storage_name] = options

    def _handle_pair(self, pair_name, options):
        _validate_pair_section(options)
        a, b = options.pop('a'), options.pop('b')
        self._pairs[pair_name] = a, b, options

    def _handle_general(self, _, options):
        if self._general:
            raise ValueError('More than one general section.')
        self._general = options

    def _parse_section(self, section_type, name, options):
        validate_section_name(name, section_type)
        if name in self._seen_names:
            raise ValueError('Name "{}" already used.'.format(name))
        self._seen_names.add(name)

        try:
            f = self._handlers[section_type]
        except KeyError:
            raise ValueError('Unknown section type.')

        f(name, options)

    def parse(self):
        for section in self._parser.sections():
            if ' ' in section:
                section_type, name = section.split(' ', 1)
            else:
                section_type = name = section

            try:
                self._parse_section(section_type, name,
                                    self._get_options(section))
            except ValueError as e:
                raise exceptions.UserError(
                    'Section "{}": {}'.format(section, str(e)))

        _validate_general_section(self._general)
        if getattr(self._file, 'name', None):
            self._general['status_path'] = os.path.join(
                os.path.dirname(self._file.name),
                expand_path(self._general['status_path'])
            )

        return self._general, self._pairs, self._storages


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

    @classmethod
    def from_fileobject(cls, f):
        reader = ConfigReader(f)
        return cls(*reader.parse())

    @classmethod
    def from_filename_or_environment(cls, fname=None):
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
                return cls.from_fileobject(f)
        except Exception as e:
            raise exceptions.UserError(
                'Error during reading config {}: {}'
                .format(fname, e)
            )

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
