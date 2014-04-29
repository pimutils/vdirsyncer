# -*- coding: utf-8 -*-
'''
    vdirsyncer
    ~~~~~~~~~~

    vdirsyncer is a syncronization tool for vdir. See the README for more
    details.

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from setuptools import setup, find_packages

setup(
    name='vdirsyncer',
    version='0.1.4',
    author='Markus Unterwaditzer',
    author_email='markus@unterwaditzer.net',
    url='https://github.com/untitaker/vdirsyncer',
    description='A syncronization tool for vdir',
    license='MIT',
    long_description=open('README.rst').read(),
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    entry_points={
        'console_scripts': ['vdirsyncer = vdirsyncer.cli:main']
    },
    install_requires=[
        'argvard>=0.3.0',
        'requests',
        'lxml'
    ],
    extras_require={'keyring': ['keyring']}
)
