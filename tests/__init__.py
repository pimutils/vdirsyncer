def normalize_item(x):
    return set(x for x in x.raw.splitlines() if
               not x.startswith('X-RADICALE-NAME') and
               not x.startswith('PRODID'))


def assert_item_equals(a, b):
    assert normalize_item(a) == normalize_item(b)
