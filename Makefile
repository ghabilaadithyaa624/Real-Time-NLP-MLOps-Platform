.PHONY: install test coverage api-coverage compile lint security ci

PYTHON ?= .venv/bin/python
RUFF ?= .venv/bin/ruff
BANDIT ?= .venv/bin/bandit

install:
	$(PYTHON) -m pip install --disable-pip-version-check --no-input -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -q tests

coverage:
	$(PYTHON) -m pytest --cov=app --cov=training --cov-report=term-missing --cov-report=xml:coverage.xml -q tests

api-coverage:
	$(PYTHON) -m pytest --cov=app --cov-report=term-missing -q tests

compile:
	$(PYTHON) -m compileall -q app training tests

lint:
	$(RUFF) check app training tests

security:
	$(BANDIT) --quiet --recursive app training --severity-level medium

ci: lint security compile test
