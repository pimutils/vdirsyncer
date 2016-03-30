# -*- coding: utf-8 -*-
'''
Vdirsyncer is a synchronization tool for vdir. See the README for more details.
'''

# Packagers: Vdirsyncer's version is automatically detected using
# setuptools-scm, but that one is not a runtime dependency.
#
# Do NOT use the GitHub's tarballs, those don't contain any version information
# detectable for setuptools-scm. Rather use the PyPI ones.


import platform

from setuptools import Command, find_packages, setup


requirements = [
    # https://github.com/mitsuhiko/click/issues/200
    'click>=5.0',
    'click-log>=0.1.3',
    'click-threading>=0.1.2',
    # !=2.9.0: https://github.com/kennethreitz/requests/issues/2930
    # >=2.4.1: https://github.com/shazow/urllib3/pull/444
    #
    # Without the above pull request, `verify=False` also disables fingerprint
    # validation. This is *not* what we want, and it's not possible to
    # replicate vdirsyncer's current behavior (verifying fingerprints without
    # verifying against CAs) with older versions of urllib3.
    'requests >=2.4.1, !=2.9.0',
    'lxml >=3.1' + (
        # See https://github.com/pimutils/vdirsyncer/issues/298
        # We pin some LXML version that is known to work with PyPy
        # I assume nobody actually uses PyPy with vdirsyncer, so this is
        # moot
        ', <=3.4.4'
        if platform.python_implementation() == 'PyPy'
        else ''
    ),
    # https://github.com/sigmavirus24/requests-toolbelt/pull/28
    # And https://github.com/sigmavirus24/requests-toolbelt/issues/54
    'requests_toolbelt >=0.4.0',
    # https://github.com/untitaker/python-atomicwrites/commit/4d12f23227b6a944ab1d99c507a69fdbc7c9ed6d  # noqa
    'atomicwrites>=0.1.7'
]


class PrintRequirements(Command):

    description = 'Prints minimal requirements'

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        for requirement in requirements:
            print(requirement.replace(">", "=").replace(" ", ""))

setup(
    name='vdirsyncer',
    use_scm_version={
        'write_to': 'vdirsyncer/version.py',
    },
    setup_requires=['setuptools_scm'],
    author='Markus Unterwaditzer',
    author_email='markus@unterwaditzer.net',
    url='https://github.com/pimutils/vdirsyncer',
    description='Synchronize calendars and contacts',
    license='MIT',
    long_description=open('README.rst').read(),
    packages=find_packages(exclude=['tests.*', 'tests']),
    include_package_data=True,
    entry_points={
        'console_scripts': ['vdirsyncer = vdirsyncer.cli:main']
    },
    install_requires=requirements,
    extras_require={
        'remotestorage': ['requests-oauthlib'],
        'oauth2': ['requests-oauthlib'],
    },
    cmdclass={
        'minimal_requirements': PrintRequirements
    }
)
