# -*- coding: utf-8 -*-
import ldap3
import logging

from .base import Storage, Item

ldap_logger = logging.getLogger(__name__)

class LDAPStorage(Storage):

    __doc__ = '''
    :param uri: LDAP URI
    :param search_base: search base
    :param bind: bind dn
    :param password: bind password
    :param filter: filter
    '''
    storage_name = 'ldap'
    read_only = True
    fileext = '.vcf'
    item_mimetype = 'text/vcard'

    def __init__(self, uri=None, search_base=None, bind=None, password=None, filter='(objectClass=*)', **kwargs):
        super(LDAPStorage, self).__init__(**kwargs)
        self.search_base = search_base
        self.filter = filter
        self.server = ldap3.Server(uri)
        if bind:
            self.conn = ldap3.Connection(self.server, user=bind, password=password)
        else:
            self.conn = ldap3.Connection(self.server)
        self.conn.bind()
        self.conn.start_tls()
        ldap_logger.debug('Connected to: {}'.format(self.conn))

    def list(self):
        '''
        :returns: list of (href, etag)
        '''
        ldap_logger.debug('Search on {self.search_base} with filter {self.filter}'.format(self=self))
        self.conn.search(self.search_base, self.filter, attributes=["whenChanged"])
        for entry in self.conn.entries:
            ldap_logger.debug('Found {}'.format(entry.entry_get_dn()))
            href = entry.entry_get_dn()
            etag = str(entry.whenChanged)
            yield href, etag

    def get(self, href):
        self.conn.search(href, self.filter,
                         attributes=["whenChanged", "cn", "sn", "givenName", "displayName", "telephoneNumber", "mobile", "mail"])

        if not self.conn.entries[0]:
            raise exceptions.NotFoundError(href)

        entry = self.conn.entries[0]
        etag = str(entry.whenChanged)

        vcard = "BEGIN:VCARD\r\n"
        vcard += "VERSION:3.0\r\n"
        vcard += "FN;CHARSET=UTF-8:{cn}\r\n".format(cn=entry.cn)
        if getattr(entry, 'sn', None):
            vcard += "N;CHARSET=UTF-8:{sn};{givenName}\r\n".format(givenName=entry.givenName, sn=entry.sn)
        if getattr(entry, 'telephoneNumber', None):
            vcard += "TEL;WORK;VOICE:{tel}\r\n".format(tel=entry.telephoneNumber)
        if getattr(entry, 'mobile', None):
            vcard += "TEL;CELL;VOICE:{mobile}\r\n".format(mobile=entry.mobile)
        if getattr(entry, 'mail', None):
            vcard += "EMAIL;INTERNET:{email}\r\n".format(email=entry.mail.value.strip())
        vcard += "END:VCARD"

        item = Item(vcard)

        return item, etag
