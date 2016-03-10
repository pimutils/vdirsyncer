# -*- coding: utf-8 -*-
import logging

import requests

from .. import exceptions


logger = logging.getLogger(__name__)


def _install_fingerprint_adapter(session, fingerprint):
    prefix = 'https://'
    try:
        from requests_toolbelt.adapters.fingerprint import \
            FingerprintAdapter
    except ImportError:
        raise RuntimeError('`verify_fingerprint` can only be used with '
                           'requests-toolbelt versions >= 0.4.0')

    if not isinstance(session.adapters[prefix], FingerprintAdapter):
        fingerprint_adapter = FingerprintAdapter(fingerprint)
        session.mount(prefix, fingerprint_adapter)


def request(method, url, session=None, latin1_fallback=True,
            verify_fingerprint=None, **kwargs):
    '''
    Wrapper method for requests, to ease logging and mocking. Parameters should
    be the same as for ``requests.request``, except:

    :param session: A requests session object to use.
    :param verify_fingerprint: Optional. SHA1 or MD5 fingerprint of the
        expected server certificate.
    :param latin1_fallback: RFC-2616 specifies the default Content-Type of
        text/* to be latin1, which is not always correct, but exactly what
        requests is doing. Setting this parameter to False will use charset
        autodetection (usually ending up with utf8) instead of plainly falling
        back to this silly default. See
        https://github.com/kennethreitz/requests/issues/2042
    '''

    if session is None:
        session = requests.Session()

    if verify_fingerprint is not None:
        _install_fingerprint_adapter(session, verify_fingerprint)

    func = session.request

    logger.debug(u'{} {}'.format(method, url))
    logger.debug(kwargs.get('headers', {}))
    logger.debug(kwargs.get('data', None))
    logger.debug('Sending request...')
    r = func(method, url, **kwargs)

    # See https://github.com/kennethreitz/requests/issues/2042
    content_type = r.headers.get('Content-Type', '')
    if not latin1_fallback and \
       'charset' not in content_type and \
       content_type.startswith('text/'):
        logger.debug('Removing latin1 fallback')
        r.encoding = None

    logger.debug(r.status_code)
    logger.debug(r.headers)
    logger.debug(r.content)

    if r.status_code == 412:
        raise exceptions.PreconditionFailed(r.reason)
    if r.status_code == 404:
        raise exceptions.NotFoundError(r.reason)

    r.raise_for_status()
    return r
