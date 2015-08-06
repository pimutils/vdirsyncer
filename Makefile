# Packagers who want to run the testsuite against an installed vdirsyncer:
#
# - Create a virtualenv
# - Inside the virtualenv: `make install-test test`
# - Somehow link your installation of vdirsyncer into the virtualenv, e.g. by
#   using --system-site-packages when creating the virtualenv
#
# The `install-test` target requires internet access. Be aware that vdirsyncer
# requires very recent versions of Radicale for the tests to run successfully.
#
# If you want to skip the DAV tests against Radicale, use:
#     make DAV_SERVER=skip # ...

DAV_SERVER = radicale
REQUIREMENTS = release
TESTSERVER_BASE = ./tests/storage/dav/servers/
TRAVIS = false
PIP_INSTALL = pip install

install-davserver:
	set -e; \
	if [ ! -d "$(TESTSERVER_BASE)$(DAV_SERVER)/" ]; then \
		git clone --depth=1 \
			https://github.com/vdirsyncer/$(DAV_SERVER)-testserver.git \
			/tmp/$(DAV_SERVER)-testserver; \
		ln -s /tmp/$(DAV_SERVER)-testserver $(TESTSERVER_BASE)$(DAV_SERVER); \
	fi
	cd $(TESTSERVER_BASE)$(DAV_SERVER) && sh install.sh

install-test: install-davserver
	$(PIP_INSTALL) pytest pytest-xprocess pytest-localserver
	[ $(TRAVIS) != "true" ] || $(PIP_INSTALL) coverage coveralls

test:
	set -e; \
	if [ "$(TRAVIS)" = "true" ]; then \
		coverage run --source=vdirsyncer/ --module pytest; \
		coveralls; \
	else \
		py.test; \
	fi

install-style:
	pip install flake8 flake8-import-order sphinx
	
style:
	flake8
	! grep -ri syncroniz */*
	sphinx-build -W -b html ./docs/ ./docs/_build/html/

install-docs:
	pip install sphinx sphinx_rtd_theme

docs:
	cd docs
	make html

linkcheck:
	sphinx-build -W -b linkcheck ./docs/ ./docs/_build/linkcheck/

install:
	$(error Take a look at https://vdirsyncer.readthedocs.org/en/stable/tutorial.html#installation)

release:
	python setup.py sdist bdist_wheel upload

.DEFAULT_GOAL := install
