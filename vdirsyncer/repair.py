# -*- coding: utf-8 -*-

import uuid

from . import log
from .utils.vobject import Item

logger = log.get(__name__)


def repair_storage(storage):
    seen_uids = set()
    all_hrefs = list(storage.list())
    for i, (href, _) in enumerate(all_hrefs):
        item, etag = storage.get(href)
        logger.info(u'[{}/{}] Processing {}'
                    .format(i, len(all_hrefs), href))

        parsed = item.parsed
        changed = False
        if parsed is None:
            logger.warning('Item {} can\'t be parsed, skipping.'
                           .format(href))
            continue

        if item.uid is None:
            logger.warning('No UID, assigning random one.')
            changed = reroll_uid(parsed) or changed
        elif item.uid in seen_uids:
            logger.warning('Duplicate UID, assigning random one.')
            changed = reroll_uid(parsed) or changed
        elif item.uid.encode('ascii', 'ignore').decode('ascii') != item.uid:
            logger.warning('UID is non-ascii, assigning random one.')
            changed = reroll_uid(parsed) or changed

        new_item = Item(u'\r\n'.join(parsed.dump_lines()))
        assert new_item.uid
        seen_uids.add(new_item.uid)
        if changed:
            try:
                if new_item.uid != item.uid:
                    storage.upload(new_item)
                    storage.delete(href, etag)
                else:
                    storage.update(href, new_item, etag)
            except Exception:
                logger.exception('Server rejected new item.')


def reroll_uid(component):
    new_uid = uuid.uuid4()
    stack = [component]
    changed = False
    while stack:
        component = stack.pop()
        stack.extend(component.subcomponents)

        if component.name in ('VEVENT', 'VTODO', 'VJOURNAL', 'VCARD'):
            component['UID'] = new_uid
            changed = True

    return changed
