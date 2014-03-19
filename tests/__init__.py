def normalize_item(item):
    rv = set()
    for line in item.raw.splitlines():
        line = line.strip()
        line = line.strip().split(u':', 1)
        line[0] = line[0].split(';')[0]
        if line[0] in ('X-RADICALE-NAME', 'PRODID', 'REV'):
            continue
        rv.add(u':'.join(line))
    return rv


def assert_item_equals(a, b):
    assert normalize_item(a) == normalize_item(b)
