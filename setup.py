'''
Vdirsyncer synchronizes calendars and contacts.

Please refer to https://vdirsyncer.pimutils.org/en/stable/packaging.html for
how to package vdirsyncer.
'''
from setuptools import Command
from setuptools import find_packages
from setuptools import setup


requirements = [
    # https://github.com/mitsuhiko/click/issues/200
    'click>=5.0',
    'click-log>=0.3.0, <0.4.0',

    # https://github.com/pimutils/vdirsyncer/issues/478
    'click-threading>=0.2',

    'requests >=2.20.0',

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


with open('README.rst') as f:
    long_description = f.read()


setup(
    # General metadata
    name='vdirsyncer',
    author='Markus Unterwaditzer',
    author_email='markus@unterwaditzer.net',
    url='https://github.com/pimutils/vdirsyncer',
    description='Synchronize calendars and contacts',
    license='BSD',
    long_description=long_description,

    # Runtime dependencies
    install_requires=requirements,

    # Optional dependencies
    extras_require={
        'google': ['requests-oauthlib'],
        'etesync': ['etesync==0.5.2', 'django<2.0']
    },

    # Build dependencies
    setup_requires=['setuptools_scm != 1.12.0'],

    # Other
    packages=find_packages(exclude=['tests.*', 'tests']),
    include_package_data=True,
    cmdclass={
        'minimal_requirements': PrintRequirements
    },
    use_scm_version={
        'write_to': 'vdirsyncer/version.py'
    },
    entry_points={
        'console_scripts': ['vdirsyncer = vdirsyncer.cli:main']
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Internet',
        'Topic :: Utilities',
    ],
)
