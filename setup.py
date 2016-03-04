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
import re

from setuptools import find_packages, setup, Command


requirements = [
    # https://github.com/mitsuhiko/click/issues/200
    'click>=5.0',
    'click-log>=0.1.3',
    'click-threading>=0.1.2',
    # https://github.com/kennethreitz/requests/issues/2930
    'requests >=2.0.1, !=2.9.0',
    'lxml >=3.1' + (
        # See https://github.com/untitaker/vdirsyncer/issues/298
        # We pin some LXML version that is known to work with PyPy
        # I assume nobody actually uses PyPy with vdirsyncer, so this is
        # moot
        ', <=3.4.4'
        if platform.python_implementation() == 'PyPy'
        else ''
    ),
    # https://github.com/sigmavirus24/requests-toolbelt/pull/28
    'requests_toolbelt >=0.3.0',
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
        [
            print(requirement.replace(">", "=").replace(" ", ""))
            for requirement in requirements
        ]

setup(
    name='vdirsyncer',
    use_scm_version={
        'write_to': 'vdirsyncer/version.py',
    },
    setup_requires=['setuptools_scm'],
    author='Markus Unterwaditzer',
    author_email='markus@unterwaditzer.net',
    url='https://github.com/untitaker/vdirsyncer',
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
        'remotestorage': ['requests-oauthlib']
    },
    cmdclass={
        'requirements': PrintRequirements
    }
)
