# See the documentation on how to run the tests:
# https://vdirsyncer.pimutils.org/en/stable/contributing.html

# Which DAV server to run the tests against (radicale, xandikos, skip, nextcloud, ...)
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
	TEST_EXTRA_PACKAGES += django-etesync-journal django djangorestframework wsgi_intercept drf-nested-routers
endif

PYTEST = py.test $(PYTEST_ARGS)

export TESTSERVER_BASE := ./tests/storage/servers/
CODECOV_PATH = /tmp/codecov.sh

all:
	$(error Take a look at https://vdirsyncer.pimutils.org/en/stable/tutorial.html#installation)

ifeq ($(CI), true)
codecov.sh:
	curl -s https://codecov.io/bash > $@
else
codecov.sh:
	echo > $@
endif

rust-test:
	cd rust/ && cargo test --release

test: unit-test system-test storage-test

unit-test: codecov.sh
	$(PYTEST) tests/unit/
	bash codecov.sh -c -F unit

system-test: codecov.sh
	$(PYTEST) tests/system/
	bash codecov.sh -c -F system

storage-test: codecov.sh
	$(PYTEST) tests/storage/
	bash codecov.sh -c -F storage

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
	pip install -U flake8 flake8-import-order 'flake8-bugbear>=17.3.0'
	which cargo-install-update || cargo install cargo-update
	cargo +nightly install-update -i clippy
	cargo +nightly install-update -i rustfmt-nightly
	cargo +nightly install-update -i cargo-update

style:
	flake8
	! git grep -i syncroniz */*
	! git grep -i 'text/icalendar' */*
	sphinx-build -W -b html ./docs/ ./docs/_build/html/
	cd rust/ && cargo +nightly clippy
	cd rust/ && cargo fmt --all -- --write-mode=diff

install-docs:
	pip install -Ur docs-requirements.txt

docs:
	cd docs && make html

linkcheck:
	sphinx-build -W -b linkcheck ./docs/ ./docs/_build/linkcheck/

release:
	python setup.py sdist upload

release-deb:
	sh scripts/release-deb.sh debian jessie
	sh scripts/release-deb.sh debian stretch
	sh scripts/release-deb.sh ubuntu trusty
	sh scripts/release-deb.sh ubuntu xenial

install-dev:
	pip install -ve .
	[ "$(ETESYNC_TESTS)" = "false" ] || pip install -Ue .[etesync]
	set -xe && if [ "$(REQUIREMENTS)" = "devel" ]; then \
	    pip install -U --force-reinstall \
			git+https://github.com/mitsuhiko/click \
			git+https://github.com/click-contrib/click-log \
			git+https://github.com/kennethreitz/requests \
			"git+https://github.com/untitaker/shippai#subdirectory=python"; \
	elif [ "$(REQUIREMENTS)" = "minimal" ]; then \
		pip install -U --force-reinstall $$(python setup.py --quiet minimal_requirements); \
	fi

ssh-submodule-urls:
	git submodule foreach "\
		echo -n 'Old: '; \
		git remote get-url origin; \
		git remote set-url origin \$$(git remote get-url origin | sed -e 's/https:\/\/github\.com\//git@github.com:/g'); \
		echo -n 'New URL: '; \
		git remote get-url origin"

install-rust:
	curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain nightly
	rustup update nightly

rust/vdirsyncer_rustext.h:
	cbindgen -c rust/cbindgen.toml rust/ > $@

.PHONY: docs rust/vdirsyncer_rustext.h
