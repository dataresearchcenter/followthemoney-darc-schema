# followthemoney-darc-schema

DARC's overlay of the [`followthemoney`](https://followthemoney.tech/) (FtM) schema YAMLs, kept in sync with [upstream](https://github.com/opensanctions/followthemoney) automatically.

This is **not a Python package** — it's a directory of YAML files (`schema/`) that you point `followthemoney` at via the `FTM_MODEL_PATH` environment variable. `followthemoney` itself is installed as normal from PyPI.

## How it works

```
overrides/*.yaml   →  full-file replacements (and additions)
              +
upstream@<pin>     →  fetched from github.com/opensanctions/followthemoney
              =
schema/*.yaml      →  what FtM loads when FTM_MODEL_PATH points here
```

`scripts/sync.py` downloads the pinned upstream tarball, drops every YAML into `schema/`, then overlays anything in `overrides/` on top. The build output is committed so PRs show the exact diff.

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

## Add an override (maintainers)

1. Copy the upstream YAML you want to customise into `overrides/`:
   ```bash
   cp .vendor/$(cat .upstream-version)/schema/Organization.yaml overrides/Organization.yaml
   ```
2. Edit `overrides/Organization.yaml` as needed.
3. Rebuild and verify:
   ```bash
   make sync   # rebuilds schema/
   make test   # parses the merged model and runs tests
   ```
4. Commit `overrides/Organization.yaml`, the regenerated files under `schema/`, and `.upstream-hashes.json`.

**Adding a brand-new schema** works the same — drop `overrides/DarcCustomThing.yaml`; the sync just adds it to `schema/`.

## Bump upstream

Manually:
```bash
make bump-upstream    # queries GitHub for the latest release, updates .upstream-version, re-syncs
```

Automatically: the `sync-upstream` workflow runs every Monday and opens a PR if a newer upstream release exists. The PR body includes the `sync.py` output — if it warns that an override may be stale (upstream changed a file you also override), re-apply upstream's changes by hand to the corresponding `overrides/*.yaml` and push to the PR branch.

## Make targets

| Target | What it does |
|---|---|
| `make` / `make all` | `install` + `sync` + `test` — the cold-start / refresh flow |
| `make install` | Create `.venv` and install `requirements.txt` |
| `make sync` | Build `schema/` from upstream@`.upstream-version` + `overrides/` |
| `make check` | CI: fail if `schema/` differs from what `sync` would produce (catches manual edits) |
| `make test` | `make check` + run pytest with `FTM_MODEL_PATH` set |
| `make bump-upstream` | Set `.upstream-version` to latest GitHub release, then sync |
| `make env` | Print `export FTM_MODEL_PATH=…` for local dev (`eval $(make env)`) |
| `make clean` | Remove `.vendor/` download cache |

## Repo layout

```
overrides/                   # source — files we override or add
schema/                      # build output — committed; what consumers point FTM_MODEL_PATH at
scripts/sync.py              # download + merge + conflict report
tests/test_model.py          # smoke tests for the merged model
.upstream-version            # pinned upstream ref
.upstream-hashes.json        # sha256 of each upstream file at the pinned ref (used for conflict detection)
.vendor/                     # gitignored cache of upstream tarballs
.github/workflows/
  ci.yml                     # check + test
  sync.yml                   # weekly upstream PR
```
