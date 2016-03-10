# -*- coding: utf-8 -*-

import logging
from os.path import basename

from .utils import generate_href, href_safe
from .utils.vobject import Item

logger = logging.getLogger(__name__)


def repair_storage(storage):
    seen_uids = set()
    all_hrefs = list(storage.list())
    for i, (href, _) in enumerate(all_hrefs):
        item, etag = storage.get(href)
        logger.info(u'[{}/{}] Processing {}'
                    .format(i, len(all_hrefs), href))

        changed = False
        if item.parsed is None:
            logger.warning('Item {} can\'t be parsed, skipping.'
                           .format(href))
            continue

        if not item.uid:
            logger.warning('No UID, assigning random one.')
            changed = change_uid(item, generate_href()) or changed
        elif item.uid in seen_uids:
            logger.warning('Duplicate UID, assigning random one.')
            changed = change_uid(item, generate_href()) or changed
        elif not href_safe(item.uid) or not href_safe(basename(href)):
            logger.warning('UID or href is unsafe, assigning random UID.')
            changed = change_uid(item, generate_href(item.uid)) or changed

        new_item = Item(u'\r\n'.join(item.parsed.dump_lines()))
        if not new_item.uid:
            logger.error('Item {!r} is malformed beyond repair. '
                         'This is a serverside bug.'
                         .format(href))
            logger.error('Item content: {!r}'.format(item.raw))
            continue

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


def change_uid(item, new_uid):
    stack = [item.parsed]
    changed = False
    while stack:
        component = stack.pop()
        stack.extend(component.subcomponents)

        if component.name in ('VEVENT', 'VTODO', 'VJOURNAL', 'VCARD'):
            component['UID'] = new_uid
            changed = True

    return changed
