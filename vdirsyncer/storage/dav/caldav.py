# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.dav.caldav
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Original version from khal: https://github.com/geier/khal

    :copyright: (c) 2014 Markus Unterwaditzer, Christian Geier and contributors
    :license: MIT, see LICENSE for more details.
'''

from .base import DavStorage
from ..base import Item
import vdirsyncer.exceptions as exceptions
from lxml import etree
import datetime

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'
CONFIG_DT_FORMAT = '%Y-%m-%d'


class CaldavStorage(DavStorage):

    fileext = '.ics'
    item_mimetype = 'text/calendar'
    dav_header = 'calendar-access'
    start_date = None
    end_date = None

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

    def __init__(self, start_date=None, end_date=None, **kwargs):
        '''
        :param start_date: Start date of timerange to show, default -inf.
        :param end_date: End date of timerange to show, default +inf.
        '''
        super(CaldavStorage, self).__init__(**kwargs)
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

    @property
    def list_xml(self):
        data = '''<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:"
                xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <D:getetag/>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        {caldavfilter}
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>'''
        start = self.start_date
        end = self.end_date
        if start and end:
            start = start.strftime(CALDAV_DT_FORMAT)
            end = end.strftime(CALDAV_DT_FORMAT)
            caldavfilter = ('<C:comp-filter name="VTODO">'
                            '<C:time-range start="{start}" end="{end}"/>'
                            '</C:comp-filter>').format(start=start,
                                                       end=end)
            return data.format(caldavfilter=caldavfilter)
        return data.format(caldavfilter='')
