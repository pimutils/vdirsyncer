# -*- coding: utf-8 -*-
'''
    vdirsyncer
    ~~~~~~~~~~

    vdirsyncer is a synchronization tool for vdir. See the README for more
    details.

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

from setuptools import setup, find_packages

setup(
    name='vdirsyncer',
    version='0.1.5',
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
        'argvard>=0.3.0',
        'requests',
        'lxml',
        'icalendar>=3.6',
        'requests_toolbelt>=0.3.0'
    ],
    extras_require={'keyring': ['keyring']}
)
