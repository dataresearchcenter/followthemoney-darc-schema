PY := .venv/bin/python
PIP := .venv/bin/pip
SCHEMA_DIR := $(PWD)/schema

.PHONY: all install sync check test bump-upstream env clean

all: install sync test

install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

sync:
	$(PY) scripts/sync.py

check:
	$(PY) scripts/sync.py --check

test: check
	FTM_MODEL_PATH=$(SCHEMA_DIR) $(PY) -m pytest -q

bump-upstream:
	$(PY) scripts/sync.py --bump-latest

env:
	@echo "export FTM_MODEL_PATH=$(SCHEMA_DIR)"

clean:
	rm -rf .vendor
