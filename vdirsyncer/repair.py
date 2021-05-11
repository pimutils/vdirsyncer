import logging
from os.path import basename

from .utils import generate_href
from .utils import href_safe

logger = logging.getLogger(__name__)


class IrreparableItem(Exception):
    pass


def repair_storage(storage, repair_unsafe_uid):
    seen_uids = set()
    all_hrefs = list(storage.list())
    for i, (href, _) in enumerate(all_hrefs):
        item, etag = storage.get(href)
        logger.info("[{}/{}] Processing {}".format(i, len(all_hrefs), href))

        try:
            new_item = repair_item(href, item, seen_uids, repair_unsafe_uid)
        except IrreparableItem:
            logger.error(
                "Item {!r} is malformed beyond repair. "
                "The PRODID property may indicate which software "
                "created this item.".format(href)
            )
            logger.error(f"Item content: {item.raw!r}")
            continue

        seen_uids.add(new_item.uid)
        if new_item.raw != item.raw:
            if new_item.uid != item.uid:
                storage.upload(new_item)
                storage.delete(href, etag)
            else:
                storage.update(href, new_item, etag)


def repair_item(href, item, seen_uids, repair_unsafe_uid):
    if item.parsed is None:
        raise IrreparableItem()

    new_item = item

    if not item.uid:
        logger.warning("No UID, assigning random UID.")
        new_item = item.with_uid(generate_href())
    elif item.uid in seen_uids:
        logger.warning("Duplicate UID, assigning random UID.")
        new_item = item.with_uid(generate_href())
    elif not href_safe(item.uid) or not href_safe(basename(href)):
        if not repair_unsafe_uid:
            logger.warning(
                "UID may cause problems, add " "--repair-unsafe-uid to repair."
            )
        else:
            logger.warning("UID or href is unsafe, assigning random UID.")
            new_item = item.with_uid(generate_href())

    if not new_item.uid:
        raise IrreparableItem()

    return new_item
