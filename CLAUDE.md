# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is (and isn't)

DARC's overlay of upstream [`followthemoney`](https://github.com/opensanctions/followthemoney) (FtM) schema YAMLs. **Not a Python package** — the deliverable is the `schema/` directory, which consumers point FtM at via the `FTM_MODEL_PATH` environment variable. Don't add `pyproject.toml` / `__init__.py` / a wheel build — that decision was deliberate (see plan in `/home/elliot/.claude/plans/this-project-should-be-twinkling-book.md` for the rationale).

`./followthemoney/` (if present at repo root) is a **reference checkout** of upstream FtM for browsing, not part of this repo — it's gitignored. The sync script downloads its own copy into `.vendor/`.

## Architecture: vendor + overlay

```
overrides/*.yaml   ← SOURCE (committed) — full-file replacements or new schemas
       +
upstream@<.upstream-version>  ← fetched from GitHub on `make sync`
       =
schema/*.yaml      ← BUILD OUTPUT (committed) — what FTM_MODEL_PATH points at
```

Three load-bearing files:
- `.upstream-version` — pins the upstream git tag (e.g. `v4.8.2`).
- `.upstream-hashes.json` — sha256 of every upstream file at the pinned version. Used by `sync.py` to detect when upstream has changed a file we override (the "conflict report").
- `schema/` — committed build artefact. Never hand-edit; `make check` catches drift.

Override mechanism is **full-file replacement** — if upstream changes a file we override, the maintainer must re-apply by hand. The sync script surfaces this with a `WARNING: N override(s) may be stale` message and (when the previous vendor dir is still cached) a unified diff between the old and new upstream versions of the file.

Discovery that makes the whole approach work: `followthemoney/settings.py:16-17` reads `FTM_MODEL_PATH` from the environment and `model.py:45-48` walks that single directory — no library patching needed.

## FTM_MODEL_PATH gotcha

`followthemoney.settings.MODEL_PATH` is resolved **at import time**. Setting `FTM_MODEL_PATH` in Python after `import followthemoney` does nothing. Always export it in the shell before launching, or use `os.environ.setdefault(...)` before any FtM import (see `tests/test_model.py` for the pattern).

## Commands

```bash
make / make all           # install + sync + test (default target; cold-start or refresh)
make install              # create .venv, install requirements.txt
make sync                 # rebuild schema/ from upstream@pin + overrides/
make check                # CI: fail if schema/ differs from expected build
make test                 # make check + pytest
make bump-upstream        # update .upstream-version to latest GH release, then sync
make env                  # print `export FTM_MODEL_PATH=…` for local use
make clean                # remove .vendor/ download cache
```

Run a single test:
```bash
FTM_MODEL_PATH=$PWD/schema .venv/bin/pytest tests/test_model.py::test_overrides_are_applied -v
```

Run the sync script with non-default behaviour:
```bash
.venv/bin/python scripts/sync.py --check         # drift detection
.venv/bin/python scripts/sync.py --bump-latest   # query GH API, bump if newer
```

## Common changes

- **Add or modify an override**: drop the file in `overrides/`, run `make sync`, then `make test`. Commit `overrides/X.yaml`, the regenerated `schema/X.yaml`, and `.upstream-hashes.json` if it changed.
- **Bump upstream**: `make bump-upstream` (or edit `.upstream-version` by hand, then `make sync`). The weekly `.github/workflows/sync.yml` job does this automatically and opens a PR.
- **Change sync behaviour** (e.g. add a new validation, change conflict-report format): edit `scripts/sync.py`. Keep the three commands (`sync`, `--check`, `--bump-latest`) backwards-compatible — CI depends on them.

## CI

- `.github/workflows/ci.yml`: runs `python scripts/sync.py --check` then pytest on every push/PR. The `--check` step is what catches manual edits to `schema/`.
- `.github/workflows/sync.yml`: weekly Monday cron + manual dispatch. Calls `--bump-latest`, opens a PR via `peter-evans/create-pull-request@v6` with the sync log (including any stale-override warnings) in the body.
