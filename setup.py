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
    version='0.1.0',
    author='Markus Unterwaditzer',
    author_email='markus@unterwaditzer.net',
    url='https://github.com/untitaker/vdirsyncer',
    description='A syncronization tool for vdir',
    long_description=open('README.md').read(),
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': ['vdirsyncer = vdirsyncer.cli:main']
    },
    install_requires=['argvard']
)
