"""Smoke tests for the committed schema/ directory.

schema/ is the source of truth on `main`: upstream YAMLs imported via the
`vendor` branch, plus any DARC edits committed on top. These tests validate
that the directory loads cleanly and parses as YAML — they will fail loudly
if a `git merge vendor` left conflict markers behind.
"""
import os
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"


@pytest.fixture(scope="module", autouse=True)
def _require_schema_dir():
    if not SCHEMA_DIR.is_dir() or not any(SCHEMA_DIR.glob("*.yaml")):
        pytest.fail("schema/ is empty")
    # Belt-and-braces: even if Makefile didn't set it (e.g. direct pytest), point FtM at our dir
    # before the followthemoney imports below resolve.
    os.environ.setdefault("FTM_MODEL_PATH", str(SCHEMA_DIR))


def test_every_schema_file_parses_as_yaml():
    """Catches merge conflict markers (pyyaml chokes on `<<<<<<<`) and any other malformed YAML."""
    files = sorted(SCHEMA_DIR.glob("*.yaml"))
    assert files, "schema/ contains no YAML files"
    for path in files:
        with path.open() as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), f"{path.name}: top level is not a mapping"
        assert len(data) == 1, f"{path.name}: expected exactly one top-level key, got {list(data)}"
        key = next(iter(data))
        assert key == path.stem, f"{path.name}: top-level key {key!r} does not match filename stem"


def test_model_loads_and_has_core_schemata():
    from followthemoney import model
    names = {s.name for s in model}
    for expected in ("Person", "Organization", "Company", "LegalEntity", "Thing"):
        assert expected in names, f"missing upstream schema: {expected}"
    assert len(names) >= 50, f"suspiciously few schemata loaded: {len(names)}"


def test_model_uses_our_schema_dir():
    """The loaded model must be reading from our schema/, not the bundled upstream one."""
    from followthemoney import model
    assert Path(model.path).resolve() == SCHEMA_DIR.resolve(), (
        f"model.path is {model.path!r}, expected {SCHEMA_DIR}"
    )
