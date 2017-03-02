# -*- coding: utf-8 -*-
import logging
import ldap3
import vobject

from .base import Item, Storage
from .. import exceptions

ldap_logger = logging.getLogger(__name__)


class LDAPStorage(Storage):
    '''
    :param url: LDAP URL
    :param search_base: search base
    :param bind: bind dn
    :param password: bind password
    :param filter: filter
    '''
    storage_name = 'ldap'
    fileext = '.vcf'
    item_mimetype = 'text/vcard'

    def __init__(self, url='ldap://localhost', search_base=None, bind=None,
                 password=None,
                 filter='(&(objectCategory=person)(objectClass=user)'
                        '(sn=*)(givenName=*))',
                 _conn=None, **kwargs):
        super(LDAPStorage, self).__init__(**kwargs)
        self.search_base = search_base
        self.filter = filter
        self.conn = _conn
        if self.conn is None:
            server = ldap3.Server(url, get_info=ldap3.DSA)
            if bind:
                self.conn = ldap3.Connection(server, user=bind,
                                             password=password)
            else:
                self.conn = ldap3.Connection(server)
            self.conn.bind()
            self.conn.start_tls()

        ldap_logger.debug('Connected to: {}'.format(self.conn))

        if self.search_base is None:
            # Fallback to default root entry
            self.search_base = server.info.naming_contexts[0]

    def list(self):
        '''
        :returns: list of (href, etag)
        '''
        ldap_logger.debug('Search on {self.search_base} with filter'
                          '{self.filter}'.format(self=self))
        self.conn.search(self.search_base, self.filter,
                         attributes=["whenChanged"])
        for entry in self.conn.entries:
            ldap_logger.debug('Found {}'.format(entry.entry_get_dn()))
            href = entry.entry_get_dn()
            if getattr(entry, 'whenChanged'):
                etag = str(entry.whenChanged)
            else:
                item = self.get(href)
                etag = item.hash

            yield href, etag

    def get(self, href):
        self.conn.search(href, self.filter,
                         attributes=["whenChanged", "cn", "sn", "givenName",
                                     "displayName", "telephoneNumber",
                                     "mobile", "facsimileTelephoneNumber",
                                     "mail", "title"])

        if not self.conn.entries[0]:
            raise exceptions.NotFoundError(href)

        entry = self.conn.entries[0]
        etag = str(entry.whenChanged)

        vcard = vobject.vCard()
        vo = vcard.add('fn')
        vo.value = str(entry.cn)
        vo = vcard.add('n')
        vo.value = vobject.vcard.Name(family=str(entry.sn),
                                      given=str(entry.givenName))
        if getattr(entry, 'telephoneNumber', None):
            vo = vcard.add('tel')
            vo.value = str(entry.telephoneNumber)
            vo.type_param = 'WORK'
        if getattr(entry, 'mobile', None):
            vo = vcard.add('tel')
            vo.value = str(entry.mobile)
            vo.type_param = 'CELL'
        if getattr(entry, 'facsimileTelephoneNumber', None):
            vo = vcard.add('tel')
            vo.value = str(entry.facsimileTelephoneNumber)
            vo.type_param = 'FAX'
        if getattr(entry, 'mail', None):
            vo = vcard.add('email')
            vo.value = str(entry.mail)
            vo.type_param = 'INTERNET'
        if getattr(entry, 'title', None):
            vo = vcard.add('title')
            vo.value = str(entry.title)

        item = Item(vcard.serialize())

        return item, etag

    def upload(self, item):
        vcard = vobject.readOne(item.raw)
        self.conn.strategy.add_entry('cn={},ou=test,o=lab'.format(vcard.fn),
                                     vcard)

    def update(self, href, item, etag):
        vcard = vobject.readOne(item.raw)
        self.conn.strategy.add_entry(href, vcard)
