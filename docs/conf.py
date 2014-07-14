# -*- coding: utf-8 -*-

import os
import sys

import pkg_resources

extensions = ['sphinx.ext.autodoc']

templates_path = ['_templates']

source_suffix = '.rst'
master_doc = 'index'

project = u'vdirsyncer'
copyright = u'2014, Markus Unterwaditzer & contributors'

try:
    # The full version, including alpha/beta/rc tags.
    release = pkg_resources.require('vdirsyncer')[0].version
except pkg_resources.DistributionNotFound:
    print('To build the documentation, the distribution information of'
          'vdirsyncer has to be available. Run "setup.py develop" to do'
          'this.')
    sys.exit(1)

version = '.'.join(release.split('.')[:2])  # The short X.Y version.

exclude_patterns = ['_build']

pygments_style = 'sphinx'

on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

if not on_rtd:
    import sphinx_rtd_theme
    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

html_static_path = ['_static']
htmlhelp_basename = 'vdirsyncerdoc'

latex_elements = {}
latex_documents = [
    ('index', 'vdirsyncer.tex', u'vdirsyncer Documentation',
     u'Markus Unterwaditzer', 'manual'),
]

man_pages = [
    ('index', 'vdirsyncer', u'vdirsyncer Documentation',
     [u'Markus Unterwaditzer'], 1)
]

texinfo_documents = [
    ('index', 'vdirsyncer', u'vdirsyncer Documentation',
     u'Markus Unterwaditzer', 'vdirsyncer',
     'One line description of project.', 'Miscellaneous'),
]
