import json
import os
import string
from configparser import RawConfigParser
from itertools import chain

from click_threading import get_ui_worker

from .. import exceptions
from .. import PROJECT_HOME
from ..utils import cached_property
from ..utils import expand_path
from .fetchparams import expand_fetch_params
from .utils import storage_class_from_config


GENERAL_ALL = frozenset(["status_path"])
GENERAL_REQUIRED = frozenset(["status_path"])
SECTION_NAME_CHARS = frozenset(chain(string.ascii_letters, string.digits, "_"))


def validate_section_name(name, section_type):
    invalid = set(name) - SECTION_NAME_CHARS
    if invalid:
        chars_display = "".join(sorted(SECTION_NAME_CHARS))
        raise exceptions.UserError(
            'The {}-section "{}" contains invalid characters. Only '
            "the following characters are allowed for storage and "
            "pair names:\n{}".format(section_type, name, chars_display)
        )


def _validate_general_section(general_config):
    invalid = set(general_config) - GENERAL_ALL
    missing = GENERAL_REQUIRED - set(general_config)
    problems = []

    if invalid:
        problems.append(
            "general section doesn't take the parameters: {}".format(", ".join(invalid))
        )

    if missing:
        problems.append(
            "general section is missing the parameters: {}".format(", ".join(missing))
        )

    if problems:
        raise exceptions.UserError(
            "Invalid general section. Copy the example "
            "config from the repository and edit it: {}".format(PROJECT_HOME),
            problems=problems,
        )


def _validate_collections_param(collections):
    if collections is None:
        return

    if not isinstance(collections, list):
        raise ValueError("`collections` parameter must be a list or `null`.")

    collection_names = set()

    for i, collection in enumerate(collections):
        try:
            if isinstance(collection, (str, bytes)):
                collection_name = collection
            elif isinstance(collection, list):
                e = ValueError(
                    "Expected list of format "
                    '["config_name", "storage_a_name", "storage_b_name"]'
                )
                if len(collection) != 3:
                    raise e

                if not isinstance(collection[0], (str, bytes)):
                    raise e

                for x in collection[1:]:
                    if x is not None and not isinstance(x, (str, bytes)):
                        raise e

                collection_name = collection[0]
            else:
                raise ValueError("Expected string or list of three strings.")

            if collection_name in collection_names:
                raise ValueError("Duplicate value.")
            collection_names.add(collection_name)
        except ValueError as e:
            raise ValueError(
                "`collections` parameter, position {i}: {e}".format(i=i, e=str(e))
            )


class _ConfigReader:
    def __init__(self, f):
        self._file = f
        self._parser = c = RawConfigParser()
        c.read_file(f)
        self._seen_names = set()

        self._general = {}
        self._pairs = {}
        self._storages = {}

    def _parse_section(self, section_type, name, options):
        validate_section_name(name, section_type)
        if name in self._seen_names:
            raise ValueError(f'Name "{name}" already used.')
        self._seen_names.add(name)

        if section_type == "general":
            if self._general:
                raise ValueError("More than one general section.")
            self._general = options
        elif section_type == "storage":
            self._storages[name] = options
        elif section_type == "pair":
            self._pairs[name] = options
        else:
            raise ValueError("Unknown section type.")

    def parse(self):
        for section in self._parser.sections():
            if " " in section:
                section_type, name = section.split(" ", 1)
            else:
                section_type = name = section

            try:
                self._parse_section(
                    section_type,
                    name,
                    dict(_parse_options(self._parser.items(section), section=section)),
                )
            except ValueError as e:
                raise exceptions.UserError('Section "{}": {}'.format(section, str(e)))

        _validate_general_section(self._general)
        if getattr(self._file, "name", None):
            self._general["status_path"] = os.path.join(
                os.path.dirname(self._file.name),
                expand_path(self._general["status_path"]),
            )

        return self._general, self._pairs, self._storages


def _parse_options(items, section=None):
    for key, value in items:
        try:
            yield key, json.loads(value)
        except ValueError as e:
            raise ValueError('Section "{}", option "{}": {}'.format(section, key, e))


class Config:
    def __init__(self, general, pairs, storages):
        self.general = general
        self.storages = storages
        for name, options in storages.items():
            options["instance_name"] = name

        self.pairs = {}
        for name, options in pairs.items():
            try:
                self.pairs[name] = PairConfig(self, name, options)
            except ValueError as e:
                raise exceptions.UserError(f"Pair {name}: {e}")

    @classmethod
    def from_fileobject(cls, f):
        reader = _ConfigReader(f)
        return cls(*reader.parse())

    @classmethod
    def from_filename_or_environment(cls, fname=None):
        if fname is None:
            fname = os.environ.get("VDIRSYNCER_CONFIG", None)
        if fname is None:
            fname = expand_path("~/.vdirsyncer/config")
            if not os.path.exists(fname):
                xdg_config_dir = os.environ.get(
                    "XDG_CONFIG_HOME", expand_path("~/.config/")
                )
                fname = os.path.join(xdg_config_dir, "vdirsyncer/config")

        try:
            with open(fname) as f:
                return cls.from_fileobject(f)
        except Exception as e:
            raise exceptions.UserError(
                "Error during reading config {}: {}".format(fname, e)
            )

    def get_storage_args(self, storage_name):
        try:
            args = self.storages[storage_name]
        except KeyError:
            raise exceptions.UserError(
                "Storage {!r} not found. "
                "These are the configured storages: {}".format(
                    storage_name, list(self.storages)
                )
            )
        else:
            return expand_fetch_params(args)

    def get_pair(self, pair_name):
        try:
            return self.pairs[pair_name]
        except KeyError as e:
            raise exceptions.PairNotFound(e, pair_name=pair_name)


class PairConfig:
    def __init__(self, full_config, name, options):
        self._config = full_config
        self.name = name
        self.name_a = options.pop("a")
        self.name_b = options.pop("b")

        self._partial_sync = options.pop("partial_sync", None)
        self.metadata = options.pop("metadata", None) or ()

        self.conflict_resolution = self._process_conflict_resolution_param(
            options.pop("conflict_resolution", None)
        )

        try:
            self.collections = options.pop("collections")
        except KeyError:
            raise ValueError(
                "collections parameter missing.\n\n"
                "As of 0.9.0 this parameter has no default anymore. "
                "Set `collections = null` explicitly in your pair config."
            )
        else:
            _validate_collections_param(self.collections)

        if options:
            raise ValueError("Unknown options: {}".format(", ".join(options)))

    def _process_conflict_resolution_param(self, conflict_resolution):
        if conflict_resolution in (None, "a wins", "b wins"):
            return conflict_resolution
        elif (
            isinstance(conflict_resolution, list)
            and len(conflict_resolution) > 1
            and conflict_resolution[0] == "command"
        ):

            def resolve(a, b):
                a_name = self.config_a["instance_name"]
                b_name = self.config_b["instance_name"]
                command = conflict_resolution[1:]

                def inner():
                    return _resolve_conflict_via_command(a, b, command, a_name, b_name)

                ui_worker = get_ui_worker()
                return ui_worker.put(inner)

            return resolve
        else:
            raise ValueError("Invalid value for `conflict_resolution`.")

    # The following parameters are lazily evaluated because evaluating
    # self.config_a would expand all `x.fetch` parameters. This is costly and
    # unnecessary if the pair is not actually synced.

    @cached_property
    def config_a(self):
        return self._config.get_storage_args(self.name_a)

    @cached_property
    def config_b(self):
        return self._config.get_storage_args(self.name_b)

    @cached_property
    def partial_sync(self):
        partial_sync = self._partial_sync
        # We need to use UserError here because ValueError is not
        # caught at the time this is expanded.

        if partial_sync is not None:
            cls_a, _ = storage_class_from_config(self.config_a)
            cls_b, _ = storage_class_from_config(self.config_b)

            if (
                not cls_a.read_only
                and not self.config_a.get("read_only", False)
                and not cls_b.read_only
                and not self.config_b.get("read_only", False)
            ):
                raise exceptions.UserError(
                    "`partial_sync` is only effective if one storage is "
                    "read-only. Use `read_only = true` in exactly one storage "
                    "section."
                )

        if partial_sync is None:
            partial_sync = "revert"

        if partial_sync not in ("ignore", "revert", "error"):
            raise exceptions.UserError("Invalid value for `partial_sync`.")

        return partial_sync


class CollectionConfig:
    def __init__(self, pair, name, config_a, config_b):
        self.pair = pair
        self._config = pair._config
        self.name = name
        self.config_a = config_a
        self.config_b = config_b


#: Public API. Khal's config wizard depends on this function.
load_config = Config.from_filename_or_environment


def _resolve_conflict_via_command(a, b, command, a_name, b_name, _check_call=None):
    import tempfile
    import shutil

    if _check_call is None:
        from subprocess import check_call as _check_call

    from ..vobject import Item

    dir = tempfile.mkdtemp(prefix="vdirsyncer-conflict.")
    try:
        a_tmp = os.path.join(dir, a_name)
        b_tmp = os.path.join(dir, b_name)

        with open(a_tmp, "w") as f:
            f.write(a.raw)
        with open(b_tmp, "w") as f:
            f.write(b.raw)

        command[0] = expand_path(command[0])
        _check_call(command + [a_tmp, b_tmp])

        with open(a_tmp) as f:
            new_a = f.read()
        with open(b_tmp) as f:
            new_b = f.read()

        if new_a != new_b:
            raise exceptions.UserError("The two files are not completely " "equal.")
        return Item(new_a)
    finally:
        shutil.rmtree(dir)
