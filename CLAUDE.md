# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is (and isn't)

DARC's fork of upstream [`followthemoney`](https://github.com/opensanctions/followthemoney) (FtM) schema YAMLs. **Not a Python package** — the deliverable is the `schema/` directory, which consumers point FtM at via the `FTM_MODEL_PATH` environment variable. Don't add `pyproject.toml` / `__init__.py` / a wheel build — that decision was deliberate (see plan in `/home/elliot/.claude/plans/this-project-should-be-twinkling-book.md` for the rationale).

`./followthemoney/` (if present at repo root) is a **reference checkout** of upstream FtM for browsing, not part of this repo — it's gitignored.

## Architecture: two git branches

Two long-lived branches:

- **`vendor`** — pristine upstream. Each commit corresponds to one upstream FtM release. The import script (`scripts/import-upstream.sh`) is the only thing that commits here, and it only modifies `schema/*.yaml` and `.upstream-version`.
- **`main`** — branched from `vendor`'s first commit. Contains the same `schema/` plus DARC customizations on top, plus merge commits from `vendor` that bring in new upstream releases.

```
vendor:  V0 ───── V1 ───── V2          (upstream tarballs imported one by one)
main:    V0 ─ A ─M1─ B ─C─M2 ─ D       (DARC edits + merges from vendor)
```

`git diff vendor main -- schema/` always shows "all DARC customizations".

Property-level merge of upstream changes happens via git's standard 3-way merge — no custom merging code. When upstream and DARC edit different parts of the same file, git auto-merges. When they edit the same lines, the maintainer resolves the conflict in `schema/X.yaml` like any other merge conflict.

Discovery that makes the whole approach work: `followthemoney/settings.py` reads `FTM_MODEL_PATH` from the environment and `model.py` walks that single directory — no library patching needed.

## FTM_MODEL_PATH gotcha

`followthemoney.settings.MODEL_PATH` is resolved **at import time**. Setting `FTM_MODEL_PATH` in Python after `import followthemoney` does nothing. Always export it in the shell before launching, or use `os.environ.setdefault(...)` before any FtM import (see `tests/test_model.py` for the pattern).

## Commands

```bash
make / make all           # install + test (default target)
make install              # create .venv, install requirements.txt
make test                 # pytest with FTM_MODEL_PATH=$(PWD)/schema
make bump-upstream        # switch to vendor, run import script, switch back
make env                  # print `export FTM_MODEL_PATH=…` for local use
```

Bump upstream by hand to a specific tag:
```bash
git checkout vendor
./scripts/import-upstream.sh v4.10.0   # (omit arg for latest GitHub release)
git checkout main
git merge vendor                        # resolve conflicts in schema/*.yaml if any
```

Run a single test:
```bash
FTM_MODEL_PATH=$PWD/schema .venv/bin/pytest tests/test_model.py::test_model_uses_our_schema_dir -v
```

## Common changes

- **Modify a schema**: edit `schema/X.yaml` directly on `main`, `make test`, commit. No build step. This *is* the override mechanism.
- **Add a brand-new (DARC-only) schema**: drop `schema/DarcCustomThing.yaml` on `main`. It lives only on main and is untouched by future `git merge vendor`.
- **Bump upstream**: `make bump-upstream && git merge vendor`. Or use the weekly CI cron, which opens a PR automatically.
- **Change the import script** (e.g. handle a new upstream layout): edit `scripts/import-upstream.sh`. Keep the "run only on vendor branch" guard and the no-op-when-unchanged exit behaviour — the CI sync workflow depends on them.

## CI

- `.github/workflows/ci.yml`: runs pytest on every push/PR. No drift check — direct edits to `schema/` are the intended workflow now.
- `.github/workflows/sync.yml`: weekly Monday cron + manual dispatch. Switches to `vendor`, runs `scripts/import-upstream.sh`, pushes the new vendor commit + `upstream/<tag>` tag, then creates `auto/upstream-<tag>` off `main`, attempts `git merge vendor`, pushes, and opens a PR via `gh pr create`. Clean merges → normal PR. Conflicting merges → **draft** PR labelled `needs-manual-merge` with conflict markers committed so the reviewer can resolve in-PR or locally.
