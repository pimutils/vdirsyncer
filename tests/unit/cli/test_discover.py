import pytest

from vdirsyncer.cli.discover import expand_collections


missing = object()


@pytest.mark.parametrize(
    "shortcuts,expected",
    [
        (
            ["from a"],
            [
                (
                    "c1",
                    (
                        {"type": "fooboo", "custom_arg": "a1", "collection": "c1"},
                        {"type": "fooboo", "custom_arg": "b1", "collection": "c1"},
                    ),
                ),
                (
                    "c2",
                    (
                        {"type": "fooboo", "custom_arg": "a2", "collection": "c2"},
                        {"type": "fooboo", "custom_arg": "b2", "collection": "c2"},
                    ),
                ),
                (
                    "a3",
                    (
                        {"type": "fooboo", "custom_arg": "a3", "collection": "a3"},
                        missing,
                    ),
                ),
            ],
        ),
        (
            ["from b"],
            [
                (
                    "c1",
                    (
                        {"type": "fooboo", "custom_arg": "a1", "collection": "c1"},
                        {"type": "fooboo", "custom_arg": "b1", "collection": "c1"},
                    ),
                ),
                (
                    "c2",
                    (
                        {"type": "fooboo", "custom_arg": "a2", "collection": "c2"},
                        {"type": "fooboo", "custom_arg": "b2", "collection": "c2"},
                    ),
                ),
                (
                    "b3",
                    (
                        missing,
                        {"type": "fooboo", "custom_arg": "b3", "collection": "b3"},
                    ),
                ),
            ],
        ),
        (
            ["from a", "from b"],
            [
                (
                    "c1",
                    (
                        {"type": "fooboo", "custom_arg": "a1", "collection": "c1"},
                        {"type": "fooboo", "custom_arg": "b1", "collection": "c1"},
                    ),
                ),
                (
                    "c2",
                    (
                        {"type": "fooboo", "custom_arg": "a2", "collection": "c2"},
                        {"type": "fooboo", "custom_arg": "b2", "collection": "c2"},
                    ),
                ),
                (
                    "a3",
                    (
                        {"type": "fooboo", "custom_arg": "a3", "collection": "a3"},
                        missing,
                    ),
                ),
                (
                    "b3",
                    (
                        missing,
                        {"type": "fooboo", "custom_arg": "b3", "collection": "b3"},
                    ),
                ),
            ],
        ),
        (
            [["c12", "c1", "c2"]],
            [
                (
                    "c12",
                    (
                        {"type": "fooboo", "custom_arg": "a1", "collection": "c1"},
                        {"type": "fooboo", "custom_arg": "b2", "collection": "c2"},
                    ),
                ),
            ],
        ),
        (
            None,
            [
                (
                    None,
                    (
                        {"type": "fooboo", "storage_side": "a", "collection": None},
                        {"type": "fooboo", "storage_side": "b", "collection": None},
                    ),
                )
            ],
        ),
        (
            [None],
            [
                (
                    None,
                    (
                        {"type": "fooboo", "storage_side": "a", "collection": None},
                        {"type": "fooboo", "storage_side": "b", "collection": None},
                    ),
                )
            ],
        ),
    ],
)
def test_expand_collections(shortcuts, expected):
    config_a = {"type": "fooboo", "storage_side": "a"}

    config_b = {"type": "fooboo", "storage_side": "b"}

    def get_discovered_a():
        return {
            "c1": {"type": "fooboo", "custom_arg": "a1", "collection": "c1"},
            "c2": {"type": "fooboo", "custom_arg": "a2", "collection": "c2"},
            "a3": {"type": "fooboo", "custom_arg": "a3", "collection": "a3"},
        }

    def get_discovered_b():
        return {
            "c1": {"type": "fooboo", "custom_arg": "b1", "collection": "c1"},
            "c2": {"type": "fooboo", "custom_arg": "b2", "collection": "c2"},
            "b3": {"type": "fooboo", "custom_arg": "b3", "collection": "b3"},
        }

    assert (
        sorted(
            expand_collections(
                shortcuts,
                config_a,
                config_b,
                get_discovered_a,
                get_discovered_b,
                lambda config, collection: missing,
            )
        )
        == sorted(expected)
    )
