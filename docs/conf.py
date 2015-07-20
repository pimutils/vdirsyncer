# -*- coding: utf-8 -*-

import datetime
import os
import sys

import pkg_resources

from sphinx.ext import autodoc

extensions = ['sphinx.ext.autodoc']

templates_path = ['_templates']

source_suffix = '.rst'
master_doc = 'index'

project = u'vdirsyncer'
copyright = (u'2014-{}, Markus Unterwaditzer & contributors'
             .format(datetime.date.today().strftime('%Y')))

try:
    # The full version, including alpha/beta/rc tags.
    release = pkg_resources.require('vdirsyncer')[0].version
except pkg_resources.DistributionNotFound:
    print('To build the documentation, the distribution information of '
          'vdirsyncer has to be available. Run "setup.py develop" to do '
          'this.')
    sys.exit(1)

version = '.'.join(release.split('.')[:2])  # The short X.Y version.

exclude_patterns = ['_build']

pygments_style = 'sphinx'

on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

try:
    import sphinx_rtd_theme
    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
except ImportError:
    html_theme = 'default'
    if not on_rtd:
        print('-' * 74)
        print('Warning: sphinx-rtd-theme not installed, building with default '
              'theme.')
        print('-' * 74)

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
     'Synchronize calendars and contacts.', 'Miscellaneous'),
]


def github_issue_role(name, rawtext, text, lineno, inliner, options={},
                      content=()):
    try:
        issue_num = int(text)
        if issue_num <= 0:
            raise ValueError()
    except ValueError:
        msg = inliner.reporter.error('Invalid GitHub issue: {}'.format(text),
                                     line=lineno)
        prb = inliner.problematic(rawtext, rawtext, msg)
        return [prb], [msg]

    import vdirsyncer
    from docutils import nodes
    link = '{}/{}/{}'.format(vdirsyncer.PROJECT_HOME,
                             'issues' if name == 'gh' else 'pull',
                             issue_num)
    linktext = ('issue #{}' if name == 'gh'
                else 'pull request #{}').format(issue_num)
    node = nodes.reference(rawtext, linktext, refuri=link,
                           **options)
    return [node], []


class StorageDocumenter(autodoc.ClassDocumenter):
    '''Custom formatter for auto-documenting storage classes. It assumes that
    the first line of the class' docstring is its own paragraph.

    After that first paragraph, an example configuration will be inserted and
    Sphinx' __init__ signature removed.'''

    objtype = 'storage'
    directivetype = 'attribute'

    def format_signature(self):
        return ''

    def get_doc(self, encoding=None, ignore=1):
        from vdirsyncer.cli.utils import format_storage_config
        rv = autodoc.ClassDocumenter.get_doc(self, encoding, ignore)
        config = [u'    ' + x for x in format_storage_config(self.object)]
        rv[0] = rv[0][:1] + [u'::', u''] + config + [u''] + rv[0][1:]
        return rv


def setup(app):
    app.add_role('gh', github_issue_role)
    app.add_role('ghpr', github_issue_role)
    app.add_autodocumenter(StorageDocumenter)
