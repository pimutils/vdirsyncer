.. _ssl-tutorial:

==============================
SSL and certificate validation
==============================

Vdirsyncer uses the requests_ library for all its HTTP and SSL interaction.

All SSL configuration is done per-storage. Storages that have anything to do
with SSL have two parameters: ``verify`` and ``verify_fingerprint``.

- The ``verify`` parameter determines whether to verify SSL certificates.

  1. The default, ``true``, means that certificates will be validated against a
     set of trusted CAs. See :ref:`ssl-cas`.

  2. The value ``false`` will disable both trusted-CA-validation and the
     validation of the certificate's expiration date. Unless combined with
     ``verify_fingerprint``, **you should not use this value at all, because
     it's a security risk**.

  3. You can also set ``verify`` to a path of the server's certificate in PEM
     format, instead of relying on the default root CAs::

         [storage foo]
         type = caldav
         ...
         verify = "/path/to/cert.pem"

- The ``verify_fingerprint`` parameter can be used to compare the SSL
  fingerprint to a fixed value. The value can be either a SHA1-fingerprint or
  an MD5 one::

      [storage foo]
      type = caldav
      ...
      verify_fingerprint = "94:FD:7A:CB:50:75:A4:69:82:0A:F8:23:DF:07:FC:69:3E:CD:90:CA"

  Using it will effectively set ``verify=False``.

.. _ssl-cas:

Trusted CAs
-----------

As said, vdirsyncer uses the requests_ library for such parts, which, by
default, `uses its own set of trusted CAs
<http://www.python-requests.org/en/latest/user/advanced/#ca-certificates>`_.

However, the actual behavior depends on how you have installed it. Some Linux
distributions, such as Debian, patch their ``python-requests`` package to use
the system certificate CAs. Normally these two stores are similar enough for
you not to care. If the behavior on your system is somehow confusing, your best
bet is explicitly setting the SSL options above.

.. _ssl-client-certs:

Client Certificates
-------------------

Client certificates may be specified with the ``auth_cert`` parameter. If the
key and certificate are stored in the same file, it may be a string::

   [storage foo]
   type = caldav
   ...
   auth_cert = "/path/to/certificate.pem"

If the key and certificate are separate, a list may be used::

   [storage foo]
   type = caldav
   ...
   auth_cert = ["/path/to/certificate.crt", "/path/to/key.key"]

.. _requests: http://www.python-requests.org/
