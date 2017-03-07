.. _ssl-tutorial:

==============================
SSL and certificate validation
==============================

All SSL configuration is done per-storage.

Pinning by fingerprint
----------------------

To pin the certificate by fingerprint::

    [storage foo]
    type = "caldav"
    ...
    verify_fingerprint = "94:FD:7A:CB:50:75:A4:69:82:0A:F8:23:DF:07:FC:69:3E:CD:90:CA"
    #verify = false  # Optional: Disable CA validation, useful for self-signed certs

SHA1-, SHA256- or MD5-Fingerprints can be used. They're detected by their
length.

You can use the following command for obtaining a SHA-1 fingerprint::

    echo -n | openssl s_client -connect unterwaditzer.net:443 | openssl x509 -noout -fingerprint

Note that ``verify_fingerprint`` doesn't suffice for vdirsyncer to work with
self-signed certificates (or certificates that are not in your trust store). You
most likely need to set ``verify = false`` as well. This disables verification
of the SSL certificate's expiration time and the existence of it in your trust
store, all that's verified now is the fingerprint.

However, please consider using `Let's Encrypt <https://letsencrypt.org/>`_ such
that you can forget about all of that. It is easier to deploy a free
certificate from them than configuring all of your clients to accept the
self-signed certificate.

.. _ssl-cas:

Custom root CAs
---------------

To point vdirsyncer to a custom set of root CAs::

    [storage foo]
    type = "caldav"
    ...
    verify = "/path/to/cert.pem"

Vdirsyncer uses the requests_ library, which, by default, `uses its own set of
trusted CAs
<http://www.python-requests.org/en/latest/user/advanced/#ca-certificates>`_.

However, the actual behavior depends on how you have installed it. Many Linux
distributions patch their ``python-requests`` package to use the system
certificate CAs. Normally these two stores are similar enough for you to not
care.

But there are cases where certificate validation fails even though you can
access the server fine through e.g. your browser. This usually indicates that
your installation of the ``requests`` library is somehow broken. In such cases,
it makes sense to explicitly set ``verify`` or ``verify_fingerprint`` as shown
above.

.. _requests: http://www.python-requests.org/

.. _ssl-client-certs:

Client Certificates
-------------------

Client certificates may be specified with the ``auth_cert`` parameter. If the
key and certificate are stored in the same file, it may be a string::

   [storage foo]
   type = "caldav"
   ...
   auth_cert = "/path/to/certificate.pem"

If the key and certificate are separate, a list may be used::

   [storage foo]
   type = "caldav"
   ...
   auth_cert = ["/path/to/certificate.crt", "/path/to/key.key"]
