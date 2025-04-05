"""
Vdirsyncer synchronizes calendars and contacts.

Please refer to https://vdirsyncer.pimutils.org/en/stable/packaging.html for
how to package vdirsyncer.
"""

from __future__ import annotations

from setuptools import Command
from setuptools import find_packages
from setuptools import setup

requirements = [
    "click>=5.0,<9.0",
    "click-log>=0.3.0, <0.5.0",
    "requests >=2.20.0",
    "aiohttp>=3.8.2,<4.0.0",
    "aiostream>=0.4.3,<0.5.0",
]


class PrintRequirements(Command):
    description = "Prints minimal requirements"
    user_options: list = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        for requirement in requirements:
            print(requirement.replace(">", "=").replace(" ", ""))


with open("README.rst") as f:
    long_description = f.read()


setup(
    # General metadata
    name="vdirsyncer",
    author="Markus Unterwaditzer",
    author_email="markus@unterwaditzer.net",
    url="https://github.com/pimutils/vdirsyncer",
    description="Synchronize calendars and contacts",
    license="BSD",
    long_description=long_description,
    # Runtime dependencies
    install_requires=requirements,
    # Optional dependencies
    extras_require={
        "google": ["aiohttp-oauthlib"],
        "ldap": ["ldap3", "vobject"],
    },
    # Other
    packages=find_packages(exclude=["tests.*", "tests"]),
    include_package_data=True,
    cmdclass={"minimal_requirements": PrintRequirements},
    entry_points={"console_scripts": ["vdirsyncer = vdirsyncer.cli:app"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet",
        "Topic :: Utilities",
    ],
)
