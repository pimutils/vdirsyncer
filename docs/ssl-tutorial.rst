.. _ssl-tutorial:

==============================
SSL and certificate validation
==============================

All SSL configuration is done per-storage.

.. _ssl-cas:

Custom root CAs
---------------

To point vdirsyncer to a custom set of root CAs::

    [storage foo]
    type = "caldav"
    ...
    verify_cert = "/path/to/cert.pem"

Only PEM-format is currently supported.

.. _ssl-client-certs:

Client Certificates
-------------------

Client certificates may be specified with the ``auth_cert`` parameter. The file
has to be a DER-formatted PKCS #12 archive, which typically have the file
extension ``.p12`` or ``.pfx``.

The archive should contain a leaf certificate and its private key, as well any
intermediate certificates that allow clients to build a chain to a trusted
root.  The chain certificates should be in order from the leaf certificate
towards the root.

::

   [storage foo]
   type = "caldav"
   ...
   auth_cert = "/path/to/identity.pfx"
   auth_cert_password = "optional password to decrypt the key"

If you have a "key" and a "cert" file, you can generate a ``.pfx`` file using
openssl::

    openssl pkcs12 -export -out identity.pfx -inkey key.pem -in cert.pem -certfile chain_certs.pem
