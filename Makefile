SHELL := /bin/bash

help:
	@echo "Available Commands:"
	@echo ""
	@echo "format: apply all available formatters"
	@echo ""
	@echo "test: run all tests"
	@echo ""


py_warn = PYTHONDEVMODE=1


# 'shopt -s globstar' allows us to run **/*.py globs. By default bash can't do recursive globs 
format:
	shopt -s globstar; \
	poetry run pyupgrade **/*.py --py38-plus --exit-zero-even-if-changed --keep-mock; \
	poetry run autoflake . --in-place --recursive --remove-all-unused-imports --ignore-init-module-imports --verbose; \
	poetry run isort .; \
	poetry run black .;

test:
	poetry run pytest -v --cov=pydantic_duality --cov-report=term-missing:skip-covered --cov-branch --cov-report=xml tests;
