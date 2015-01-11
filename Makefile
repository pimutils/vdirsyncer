install:
	make install-test
	make install-style

install-test:
	sh build.sh install_tests

test:
	sh build.sh tests

install-style:
	pip install flake8 flake8-import-order
	
style:
	flake8
	! grep -ri syncroniz */*

install-docs:
	pip install sphinx sphinx_rtd_theme
	pip install -e .

docs:
	cd docs
	make html
