# -*- coding: utf-8 -*-
'''
    vdirsyncer
    ~~~~~~~~~~

    vdirsyncer is a synchronization tool for vdir. See the README for more
    details.

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
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
    description='A synchronization tool for vdir',
    license='MIT',
    long_description=open('README.rst').read(),
    packages=find_packages(exclude=['tests.*', 'tests']),
    include_package_data=True,
    entry_points={
        'console_scripts': ['vdirsyncer = vdirsyncer.cli:main']
    },
    install_requires=[
        'click>=2.0',
        'requests',
        'lxml',
        'icalendar>=3.6',
        'requests_toolbelt>=0.3.0'
    ],
    extras_require={'keyring': ['keyring']}
)
