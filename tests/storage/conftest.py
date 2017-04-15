# -*- coding: utf-8 -*-

import pytest

import uuid


@pytest.fixture
def slow_create_collection(request):
    # We need to properly clean up because otherwise we might run into
    # storage limits.
    to_delete = []

    def delete_collections():
        for s in to_delete:
            s.session.request('DELETE', '')

    request.addfinalizer(delete_collections)

    def inner(cls, args, collection):
        assert collection.startswith('test')
        collection += '-vdirsyncer-ci-' + str(uuid.uuid4())

        args = cls.create_collection(collection, **args)
        s = cls(**args)
        _clear_collection(s)
        assert not list(s.list())
        to_delete.append(s)
        return args

    return inner


def _clear_collection(s):
    for href, etag in s.list():
        s.delete(href, etag)
