# followthemoney-darc-schema

DARC's fork of the [`followthemoney`](https://followthemoney.tech/) (FtM) schema YAMLs, kept in sync with [upstream](https://github.com/opensanctions/followthemoney) automatically.

This is **not a Python package** — it's a directory of YAML files (`schema/`) that you point `followthemoney` at via the `FTM_MODEL_PATH` environment variable. `followthemoney` itself is installed as normal from PyPI.

## How it works

Two branches:

- **`vendor`** — pristine upstream. Each commit corresponds to one upstream FtM release. Only ever touches `schema/*.yaml` and `.upstream-version`.
- **`main`** — branched from `vendor`. Contains the same `schema/` plus DARC's edits on top, with merge commits from `vendor` bringing in newer upstream releases.

```
vendor:  V0 ─────── V1 ─────── V2
         v4.8.2     v4.9.0     v4.10.0
                     │           │
                     ▼ merge     ▼ merge
main:    V0 ─ A ─ B ─M1─ C ─ D ─M2 ─ E
                       ▲          ▲
                  upstream v4.9.0   upstream v4.10.0
```

Property-level merging happens for free via git's standard 3-way merge. Upstream adds a property to `Person.yaml`, DARC adds a different property — git auto-merges both. Both touch the same lines — standard merge conflict in `schema/Person.yaml`.

## Use it (consumers)

Pick whichever fits.

**Clone + env var.** Simplest:
```bash
git clone --depth=1 https://github.com/dataresearchcenter/followthemoney-darc-schema.git /opt/ftm-darc
export FTM_MODEL_PATH=/opt/ftm-darc/schema
python -c "from followthemoney import model; print('schemas:', len(list(model)))"
```

**Submodule.** Pin to a specific commit in a downstream repo:
```bash
git submodule add https://github.com/dataresearchcenter/followthemoney-darc-schema.git vendor/ftm-darc
# then in the app launcher: export FTM_MODEL_PATH=$PWD/vendor/ftm-darc/schema
```

**Docker layer.** No git in the runtime image:
```dockerfile
ADD https://github.com/dataresearchcenter/followthemoney-darc-schema/archive/refs/heads/main.tar.gz /tmp/s.tgz
RUN tar -xzf /tmp/s.tgz -C /opt && mv /opt/followthemoney-darc-schema-main/schema /opt/ftm-schema && rm /tmp/s.tgz
ENV FTM_MODEL_PATH=/opt/ftm-schema
```

> `FTM_MODEL_PATH` is read **once at import time** by `followthemoney.settings`. Export it in the shell that launches your process — setting it in Python after `import followthemoney` has no effect.

## Add or modify a schema (maintainers)

Edit `schema/X.yaml` directly on `main` and commit:
```bash
git checkout main
# edit schema/Person.yaml
git add schema/Person.yaml
git commit -m "Add darcInternalId property to Person"
```

That's the entire workflow. No separate `overrides/` directory, no build step. The edit is your override; merging upstream later will preserve it (and conflict if upstream touched the same lines, which you resolve as usual).

**Adding a brand-new schema** is the same — drop `schema/DarcCustomThing.yaml` and commit. It lives only on `main` and is untouched by future merges from `vendor`.

## Bump upstream

Manually:
```bash
make bump-upstream     # switches to vendor, imports latest release, switches back
git merge vendor       # bring the upstream changes into your current branch
```

Or step-by-step if you want a specific tag:
```bash
git checkout vendor
./scripts/import-upstream.sh v4.10.0
git checkout main
git merge vendor
```

Resolve any merge conflicts in `schema/*.yaml` the normal way, then `git commit`.

Automatically: the `sync-upstream` workflow runs every Monday. If a newer upstream release exists, it advances `vendor`, attempts to merge into a fresh branch off `main`, and opens a PR. Clean merges open a normal PR; conflicting merges open a **draft** PR labelled `needs-manual-merge` with the conflict markers committed so you can resolve in-PR or locally.

## Make targets

| Target | What it does |
|---|---|
| `make` / `make all` | `install` + `test` |
| `make install` | Create `.venv` and install `requirements.txt` |
| `make test` | Run pytest with `FTM_MODEL_PATH=$(PWD)/schema` |
| `make bump-upstream` | Switch to `vendor`, run import script, switch back — then `git merge vendor` |
| `make env` | Print `export FTM_MODEL_PATH=…` for local dev (`eval $(make env)`) |

## Repo layout

```
schema/                      # the deliverable — what consumers point FTM_MODEL_PATH at
scripts/import-upstream.sh   # run only on the `vendor` branch to pull a new upstream release
tests/test_model.py          # smoke tests for the committed schema
.upstream-version            # current upstream pin (kept in sync by import-upstream.sh)
.github/workflows/
  ci.yml                     # install + pytest
  sync.yml                   # weekly upstream bump → vendor branch → auto-PR into main
```

Tags `upstream/vX.Y.Z` are placed on the corresponding `vendor` commits so you can `git log upstream/v4.8.2..vendor -- schema/` to see what changed between upstream releases.
