=======
Support
=======

For any questions left unanswered by the documentation, `open an issue on
GitHub <https://github.com/untitaker/vdirsyncer/issues/new>`_ or `contact me
directly <https://unterwaditzer.net>`_.

Troubleshooting
===============

- **[Errno 185090050] _ssl.c:343: error:0B084002:x509 certificate
  routines:X509_load_cert_crl_file:system lib**

  vdirsyncer cannot find the path to your certificate bundle, you need to
  supply it as a parameter to ``verify`` in your config file, e.g.::

      verify = /usr/share/ca-certificates/cacert.org/cacert.org_root.crt
