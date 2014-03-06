# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.dav.caldav
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Original version from khal: https://github.com/geier/khal

    :copyright: (c) 2014 Markus Unterwaditzer, Christian Geier and contributors
    :license: MIT, see LICENSE for more details.
'''

from .base import DavStorage
import datetime

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'
CONFIG_DT_FORMAT = '%Y-%m-%d'


class CaldavStorage(DavStorage):

    fileext = '.ics'
    item_mimetype = 'text/calendar'
    dav_header = 'calendar-access'
    start_date = None
    end_date = None
    item_types = None

    get_multi_template = '''<?xml version="1.0" encoding="utf-8" ?>
        <C:calendar-multiget xmlns:D="DAV:"
            xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <D:getetag/>
                <C:calendar-data/>
            </D:prop>
            {hrefs}
        </C:calendar-multiget>'''

    get_multi_data_query = '{urn:ietf:params:xml:ns:caldav}calendar-data'

    def __init__(self, start_date=None, end_date=None,
                 item_types=('VTODO', 'VEVENT'), **kwargs):
        '''
        :param start_date: Start date of timerange to show, default -inf.
        :param end_date: End date of timerange to show, default +inf.
        '''
        super(CaldavStorage, self).__init__(**kwargs)
        if isinstance(item_types, str):
            item_types = [x.strip() for x in item_types.split(',')]
        self.item_types = item_types
        if (start_date is None) != (end_date is None):
            raise ValueError('If start_date is given, '
                             'end_date has to be given too.')
        elif start_date is not None and end_date is not None:
            namespace = dict(datetime.__dict__)
            namespace['start_date'] = self.start_date = \
                (eval(start_date, namespace) if isinstance(start_date, str)
                 else start_date)
            self.end_date = \
                (eval(end_date, namespace) if isinstance(end_date, str)
                 else end_date)

        self._list_template = self._get_list_template()

    def _get_list_template(self):
        data = '''<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:"
                xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <D:getetag/>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        <C:comp-filter name="{component}">
                            {caldavfilter}
                        </C:comp-filter>
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>'''
        start = self.start_date
        end = self.end_date
        caldavfilter = ''
        if start is not None and end is not None:
            start = start.strftime(CALDAV_DT_FORMAT)
            end = end.strftime(CALDAV_DT_FORMAT)
            caldavfilter = ('<C:time-range start="{start}" end="{end}"/>'
                            .format(start=start, end=end))
        return data.format(caldavfilter=caldavfilter, component='{item_type}')

    def list(self):
        hrefs = set()
        for t in self.item_types:
            xml = self._list_template.format(item_type=t)
            for href, etag in self._list(xml):
                assert href not in hrefs
                hrefs.add(href)
                yield href, etag
