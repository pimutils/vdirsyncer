# -*- coding: utf-8 -*-

import datetime
import os

import setuptools_scm

extensions = ['sphinx.ext.autodoc']

templates_path = ['_templates']

source_suffix = '.rst'
master_doc = 'index'

project = u'vdirsyncer'
copyright = (u'2014-{}, Markus Unterwaditzer & contributors'
             .format(datetime.date.today().strftime('%Y')))

release = setuptools_scm.get_version(root='..', relative_to=__file__)
version = '.'.join(release.split('.')[:2])  # The short X.Y version.

rst_epilog = '.. |vdirsyncer_version| replace:: %s' % release

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


def github_issue_role(name, rawtext, text, lineno, inliner,
                      options={}, content=()):  # noqa: B006
    try:
        issue_num = int(text)
        if issue_num <= 0:
            raise ValueError()
    except ValueError:
        msg = inliner.reporter.error('Invalid GitHub issue: {}'.format(text),
                                     line=lineno)
        prb = inliner.problematic(rawtext, rawtext, msg)
        return [prb], [msg]

    from docutils import nodes

    PROJECT_HOME = 'https://github.com/pimutils/vdirsyncer'
    link = '{}/{}/{}'.format(PROJECT_HOME,
                             'issues' if name == 'gh' else 'pull',
                             issue_num)
    linktext = ('issue #{}' if name == 'gh'
                else 'pull request #{}').format(issue_num)
    node = nodes.reference(rawtext, linktext, refuri=link,
                           **options)
    return [node], []


def setup(app):
    from sphinx.domains.python import PyObject
    app.add_object_type('storage', 'storage', 'pair: %s; storage',
                        doc_field_types=PyObject.doc_field_types)
    app.add_role('gh', github_issue_role)
    app.add_role('ghpr', github_issue_role)
