# -*- coding: utf-8 -*-
'''
Vdirsyncer is a synchronization tool for vdir. See the README for more details.
'''

import ast
import re

from setuptools import find_packages, setup


_version_re = re.compile(r'__version__\s+=\s+(.*)')


with open('vdirsyncer/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))


setup(
    name='vdirsyncer',
    version=version,
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
    install_requires=[
        # https://github.com/mitsuhiko/click/issues/200
        'click>=3.1',
        'requests',
        'lxml>=3.0',
        # https://github.com/sigmavirus24/requests-toolbelt/pull/28
        'requests_toolbelt>=0.3.0',
        'atomicwrites'
    ],
    extras_require={'keyring': ['keyring']}
)
