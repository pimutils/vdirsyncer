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

# Assume to run in CI. Don't use this outside of a virtual machine. It will
# heavily "pollute" your system, such as attempting to install a new Python
# systemwide.
export CI := false

# Whether to generate coverage data while running tests.
export COVERAGE := $(CI)

# Additional arguments that should be passed to py.test.
PYTEST_ARGS =

# Variables below this line are not very interesting for getting started.

TEST_EXTRA_PACKAGES =

PYTEST = py.test $(PYTEST_ARGS)
CODECOV_PATH = /tmp/codecov.sh

all:
	$(error Take a look at https://vdirsyncer.pimutils.org/en/stable/tutorial.html#installation)

ci-test:
	curl -s https://codecov.io/bash > $(CODECOV_PATH)
	$(PYTEST) --cov vdirsyncer --cov-append tests/unit/ tests/system/
	bash $(CODECOV_PATH) -c

ci-test-storage:
	curl -s https://codecov.io/bash > $(CODECOV_PATH)
	set -ex; \
	for server in $(DAV_SERVER); do \
		DAV_SERVER=$$server $(PYTEST) --cov vdirsyncer --cov-append tests/storage; \
	done
	bash $(CODECOV_PATH) -c

test:
	$(PYTEST)

style:
	pre-commit run --all
	! git grep -i syncroniz */*
	! git grep -i 'text/icalendar' */*
	sphinx-build -W -b html ./docs/ ./docs/_build/html/

install-docs:
	pip install -Ur docs-requirements.txt

docs:
	cd docs && make html
	sphinx-build -W -b linkcheck ./docs/ ./docs/_build/linkcheck/

release-deb:
	sh scripts/release-deb.sh debian jessie
	sh scripts/release-deb.sh debian stretch
	sh scripts/release-deb.sh ubuntu trusty
	sh scripts/release-deb.sh ubuntu xenial
	sh scripts/release-deb.sh ubuntu zesty

install-dev:
	pip install -U pip setuptools wheel
	pip install -e .
	pip install -Ur test-requirements.txt $(TEST_EXTRA_PACKAGES)
	pip install pre-commit
	set -xe && if [ "$(REQUIREMENTS)" = "minimal" ]; then \
		pip install -U --force-reinstall $$(python setup.py --quiet minimal_requirements); \
	fi

.PHONY: docs
