import pkg_resources
import datetime

version = pkg_resources.get_distribution('vdirsyncer').version
version = version.replace('.dev', '~')
print('vdirsyncer-latest ({}) unstable; urgency=medium'.format(version))
print('''
  * Dummy changelog

 -- Markus Unterwaditzer <markus-debianpkg@unterwaditzer.net>  {}
'''.format(datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0200')))
