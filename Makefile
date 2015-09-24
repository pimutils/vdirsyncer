# Packagers who want to run the testsuite against an installed vdirsyncer:
#
# - Create a virtualenv
# - Somehow link your installation of vdirsyncer into the virtualenv, e.g. by
#   using --system-site-packages when creating the virtualenv
# - Inside the virtualenv: `make install-test test`
#
# The `install-test` target requires internet access. Be aware that vdirsyncer
# requires very recent versions of Radicale for the tests to run successfully.
#
# If you want to skip the DAV tests against Radicale, use:
#     make DAV_SERVER=skip # ...

export DAV_SERVER := skip
export REMOTESTORAGE_SERVER := skip
export RADICALE_BACKEND := filesystem
export REQUIREMENTS := release
export TESTSERVER_BASE := ./tests/storage/servers/
export TRAVIS := false

install-servers:
	set -ex; \
	for server in $(DAV_SERVER) $(REMOTESTORAGE_SERVER); do \
		if [ ! -d "$(TESTSERVER_BASE)$$server/" ]; then \
			git clone --depth=1 \
				https://github.com/vdirsyncer/$$server-testserver.git \
				/tmp/$$server-testserver; \
			ln -s /tmp/$$server-testserver $(TESTSERVER_BASE)$$server; \
		fi; \
		(cd $(TESTSERVER_BASE)$$server && sh install.sh); \
	done

install-test: install-servers
	pip install pytest pytest-xprocess pytest-localserver
	[ $(TRAVIS) != "true" ] || pip install coverage coveralls

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
	cd docs && make html

sh:  # open subshell with default test config
	$$SHELL;

linkcheck:
	sphinx-build -W -b linkcheck ./docs/ ./docs/_build/linkcheck/

all:
	$(error Take a look at https://vdirsyncer.readthedocs.org/en/stable/tutorial.html#installation)

release:
	python setup.py sdist bdist_wheel upload

.PHONY: docs
