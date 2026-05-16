PY := .venv/bin/python
PIP := .venv/bin/pip
SCHEMA_DIR := $(PWD)/schema

.PHONY: all install test env bump-upstream

all: install test

install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test:
	FTM_MODEL_PATH=$(SCHEMA_DIR) $(PY) -m pytest -q

env:
	@echo "export FTM_MODEL_PATH=$(SCHEMA_DIR)"

# Convenience: switch to vendor, import the latest upstream release, switch back.
# Leaves you on your starting branch with vendor advanced; merge it in with `git merge vendor`.
bump-upstream:
	@git diff-index --quiet HEAD -- || { echo "working tree dirty; commit or stash first" >&2; exit 1; }
	@start=$$(git rev-parse --abbrev-ref HEAD); \
	 git checkout vendor && \
	 ./scripts/import-upstream.sh && \
	 git checkout "$$start" && \
	 echo "" && \
	 echo "vendor updated. To bring upstream into this branch: git merge vendor"
