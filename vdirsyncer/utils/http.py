# -*- coding: utf-8 -*-

import requests

from .. import exceptions, log


logger = log.get(__name__)


def _verify_fingerprint_works():
    try:
        from pkg_resources import parse_version as ver

        return ver(requests.__version__) >= ver('2.4.1')
    except Exception:
        return False

# https://github.com/shazow/urllib3/pull/444
#
# Without the above pull request, `verify=False` also disables fingerprint
# validation. This is *not* what we want, and it's not possible to replicate
# vdirsyncer's current behavior (verifying fingerprints without verifying
# against CAs) with older versions of urllib3.
#
# We check this here instead of setup.py, because:
# - Python's packaging stuff doesn't check installed versions.
# - The people who don't use `verify_fingerprint` wouldn't care.
VERIFY_FINGERPRINT_WORKS = _verify_fingerprint_works()
del _verify_fingerprint_works


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
        if not VERIFY_FINGERPRINT_WORKS:
            raise RuntimeError('`verify_fingerprint` can only be used with '
                               'requests versions >= 2.4.1')
        _install_fingerprint_adapter(session, verify_fingerprint)
        kwargs['verify'] = False

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
