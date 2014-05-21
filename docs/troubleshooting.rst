===============
Troubleshooting
===============

- **[Errno 185090050] _ssl.c:343: error:0B084002:x509 certificate
  routines:X509_load_cert_crl_file:system lib**

  vdirsyncer cannot find the path to your certificate bundle, you need to
  supply it as a parameter to ``verify`` in your config file, e.g.::

      verify = /usr/share/ca-certificates/cacert.org/cacert.org_root.crt

- **During sync an error occurs: TypeError: request() got an unexpected keyword
  argument 'verify'**

  You need to update your version of requests.
