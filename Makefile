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
	pip install pytest pytest-xprocess pytest-localserver hypothesis pytest-subtesthack
	[ $(TRAVIS) != "true" ] || pip install coverage codecov

test:
	set -e; \
	if [ "$(TRAVIS)" = "true" ]; then \
		coverage run --source=vdirsyncer/ --module pytest; \
		codecov; \
	else \
		py.test; \
	fi

install-style:
	pip install flake8 flake8-import-order sphinx
	
style:
	flake8
	! grep -ri syncroniz */*
	sphinx-build -W -b html ./docs/ ./docs/_build/html/
	$(MAKE) travis-conf
	git diff --exit-code

travis-conf:
	python3 scripts/make_travisconf.py > .travis.yml

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

install-dev:
	set -xe && if [ "$$REMOTESTORAGE_SERVER" != "skip" ]; then \
		pip install -e .[remotestorage]; \
	else \
		pip install -e .; \
	fi
	set -xe && if [ "$$REQUIREMENTS" = "devel" ]; then \
	    pip install -U --force-reinstall git+https://github.com/kennethreitz/requests; \
	elif [ "$$REQUIREMENTS" = "minimal" ]; then \
		pip install -U --force-reinstall lxml==3.1 requests==2.4.1 requests_toolbelt==0.4.0 click==5.0; \
	fi

.PHONY: docs
