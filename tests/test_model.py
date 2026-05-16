"""Smoke tests for the merged schema and the overlay mechanism.

The first two tests validate the *committed* schema/ (built by `make sync`).
The third validates the overlay mechanism by building a temporary schema from
tests/fixtures/ overlaid on upstream, isolated from whatever's in overrides/.
"""
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"
OVERRIDES_DIR = REPO_ROOT / "overrides"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module", autouse=True)
def _require_schema_dir():
    if not SCHEMA_DIR.is_dir() or not any(SCHEMA_DIR.glob("*.yaml")):
        pytest.fail("schema/ is empty — run `make sync` first")
    # Belt-and-braces: even if Makefile didn't set it (e.g. direct pytest), point FtM at our dir
    # before the followthemoney imports below resolve.
    os.environ.setdefault("FTM_MODEL_PATH", str(SCHEMA_DIR))


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


def test_committed_overrides_are_byte_identical_to_schema():
    """Every file in overrides/ must appear verbatim in schema/."""
    overrides = list(OVERRIDES_DIR.glob("*.yaml")) if OVERRIDES_DIR.exists() else []
    if not overrides:
        pytest.skip("no override files present")
    for ov in overrides:
        built = SCHEMA_DIR / ov.name
        assert built.exists(), f"override {ov.name} not present in schema/"
        assert built.read_bytes() == ov.read_bytes(), (
            f"override {ov.name} content does not match schema/{ov.name} — did someone hand-edit schema/?"
        )


def test_fixture_override_replaces_upstream_schema(tmp_path):
    """Build a temp schema from upstream + tests/fixtures/, load it, verify the fixture overrode upstream."""
    from sync import build_schema, download_upstream, read_version
    from followthemoney.model import Model

    upstream = download_upstream(read_version())
    built_dir = tmp_path / "schema"
    upstream_count, replaced, added = build_schema(upstream, FIXTURES_DIR, built_dir)
    assert replaced == 1, f"expected 1 replaced schema (Person), got {replaced}"
    assert added == 0
    assert upstream_count > 50

    # The merged file on disk must be byte-identical to the fixture
    assert (built_dir / "Person.yaml").read_bytes() == (FIXTURES_DIR / "Person.yaml").read_bytes()

    # And the loaded model must reflect the fixture's added property
    model = Model(str(built_dir))
    person = model.get("Person")
    assert person is not None
    assert "fixtureTestProp" in person.properties, (
        "fixtureTestProp from tests/fixtures/Person.yaml not present on Person — overlay didn't take precedence"
    )

    entity = model.make_entity("Person")
    entity.add("name", "Test Person")
    entity.add("fixtureTestProp", "0.87")
    assert entity.get("fixtureTestProp") == ["0.87"]
