# See the documentation on how to run the tests:
# https://vdirsyncer.pimutils.org/en/stable/contributing.html

# Which DAV server to run the tests against (radicale, xandikos, skip, owncloud, nextcloud, ...)
export DAV_SERVER := skip

# release (install release versions of dependencies)
# development (install development versions of some of vdirsyncer's dependencies)
# or minimal (install oldest version of each dependency that is supported by vdirsyncer)
export REQUIREMENTS := release

# Set this to true if you run vdirsyncer's test as part of e.g. packaging.
export DETERMINISTIC_TESTS := false

# Run the etesync testsuite.
export ETESYNC_TESTS := false

# Assume to run in Travis. Don't use this outside of a virtual machine. It will
# heavily "pollute" your system, such as attempting to install a new Python
# systemwide.
export CI := false

# Whether to generate coverage data while running tests.
export COVERAGE := $(CI)

# Additional arguments that should be passed to py.test.
PYTEST_ARGS =

# Variables below this line are not very interesting for getting started.

TEST_EXTRA_PACKAGES =

ifeq ($(COVERAGE), true)
	TEST_EXTRA_PACKAGES += pytest-cov
	PYTEST_ARGS += --cov-config .coveragerc --cov vdirsyncer
endif

ifeq ($(ETESYNC_TESTS), true)
	TEST_EXTRA_PACKAGES += git+https://github.com/etesync/journal-manager
	TEST_EXTRA_PACKAGES += django djangorestframework wsgi_intercept drf-nested-routers
endif

PYTEST = py.test $(PYTEST_ARGS)

export TESTSERVER_BASE := ./tests/storage/servers/
CODECOV_PATH = /tmp/codecov.sh

ifeq ($(CI), true)
test:
	curl -s https://codecov.io/bash > $(CODECOV_PATH)
	$(PYTEST) tests/unit/
	bash $(CODECOV_PATH) -c -F unit
	$(PYTEST) tests/system/
	bash $(CODECOV_PATH) -c -F system
	$(PYTEST) tests/storage/
	bash $(CODECOV_PATH) -c -F storage
else
test:
	$(PYTEST)
endif

all:
	$(error Take a look at https://vdirsyncer.pimutils.org/en/stable/tutorial.html#installation)

install-servers:
	set -ex; \
	for server in $(DAV_SERVER); do \
		if [ ! "$$(ls $(TESTSERVER_BASE)$$server/)" ]; then \
			git submodule update --init -- "$(TESTSERVER_BASE)$$server"; \
		fi; \
		(cd $(TESTSERVER_BASE)$$server && sh install.sh); \
	done

install-test: install-servers
	pip install -Ur test-requirements.txt
	set -xe && if [ "$$REQUIREMENTS" = "devel" ]; then \
		pip install -U --force-reinstall \
			git+https://github.com/DRMacIver/hypothesis \
			git+https://github.com/kennethreitz/requests \
			git+https://github.com/pytest-dev/pytest; \
	fi
	[ -z "$(TEST_EXTRA_PACKAGES)" ] || pip install $(TEST_EXTRA_PACKAGES)

install-style: install-docs
	pip install -U flake8 flake8-import-order 'flake8-bugbear>=17.3.0' autopep8
	
style:
	flake8
	! git grep -i syncroniz */*
	! git grep -i 'text/icalendar' */*
	sphinx-build -W -b html ./docs/ ./docs/_build/html/
	python3 scripts/make_travisconf.py | diff -b .travis.yml -

travis-conf:
	python3 scripts/make_travisconf.py > .travis.yml

install-docs:
	pip install -Ur docs-requirements.txt

docs:
	cd docs && make html

linkcheck:
	sphinx-build -W -b linkcheck ./docs/ ./docs/_build/linkcheck/

release:
	python setup.py sdist bdist_wheel upload

release-deb:
	sh scripts/release-deb.sh debian jessie
	sh scripts/release-deb.sh debian stretch
	sh scripts/release-deb.sh ubuntu trusty
	sh scripts/release-deb.sh ubuntu xenial
	sh scripts/release-deb.sh ubuntu zesty

install-dev:
	pip install -e .
	[ "$(ETESYNC_TESTS)" = "false" ] || pip install -Ue .[etesync]
	set -xe && if [ "$(REQUIREMENTS)" = "devel" ]; then \
	    pip install -U --force-reinstall \
			git+https://github.com/mitsuhiko/click \
			git+https://github.com/kennethreitz/requests; \
	elif [ "$(REQUIREMENTS)" = "minimal" ]; then \
		pip install -U --force-reinstall $$(python setup.py --quiet minimal_requirements); \
	fi

install-git-hooks: install-style
	echo "make style-autocorrect" > .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

style-autocorrect:
	git diff --cached --name-only | egrep '\.py$$' | xargs --no-run-if-empty autopep8 -ri

ssh-submodule-urls:
	git submodule foreach "\
		echo -n 'Old: '; \
		git remote get-url origin; \
		git remote set-url origin \$$(git remote get-url origin | sed -e 's/https:\/\/github\.com\//git@github.com:/g'); \
		echo -n 'New URL: '; \
		git remote get-url origin"

.PHONY: docs
