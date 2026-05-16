#!/usr/bin/env python3
"""Sync followthemoney upstream schema YAMLs into ./schema/, with overrides applied on top.

Usage:
    scripts/sync.py                 # build schema/ from current .upstream-version + overrides/
    scripts/sync.py --check         # exit non-zero if schema/ differs from expected build
    scripts/sync.py --bump-latest   # set .upstream-version to latest GitHub release, then sync
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

import requests

UPSTREAM_REPO = "opensanctions/followthemoney"
TARBALL_URL = "https://github.com/{repo}/archive/refs/tags/{ver}.tar.gz"
LATEST_RELEASE_URL = "https://api.github.com/repos/{repo}/releases/latest"

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / ".vendor"
OVERRIDES_DIR = REPO_ROOT / "overrides"
SCHEMA_DIR = REPO_ROOT / "schema"
UPSTREAM_VERSION_FILE = REPO_ROOT / ".upstream-version"
HASHES_FILE = REPO_ROOT / ".upstream-hashes.json"


def read_version() -> str:
    return UPSTREAM_VERSION_FILE.read_text().strip()


def write_version(ver: str) -> None:
    UPSTREAM_VERSION_FILE.write_text(ver + "\n")


def read_previous_hashes() -> dict[str, str]:
    if not HASHES_FILE.exists():
        return {}
    return json.loads(HASHES_FILE.read_text())


def write_hashes(data: dict[str, str]) -> None:
    HASHES_FILE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_upstream(version: str) -> Path:
    """Fetch + extract the upstream tarball if not already cached under .vendor/<ver>/.
    Returns the path to the extracted upstream schema dir."""
    VENDOR_DIR.mkdir(exist_ok=True)
    extract_root = VENDOR_DIR / version
    schema_subdir = extract_root / "schema"
    if schema_subdir.is_dir() and any(schema_subdir.glob("*.yaml")):
        return schema_subdir

    url = TARBALL_URL.format(repo=UPSTREAM_REPO, ver=version)
    print(f"  fetching {url}")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    extract_root.mkdir(parents=True, exist_ok=True)
    schema_subdir.mkdir(exist_ok=True)
    prefix_marker = "/followthemoney/schema/"
    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            idx = member.name.find(prefix_marker)
            if idx == -1:
                continue
            rel = member.name[idx + len(prefix_marker):]
            if "/" in rel or not rel.endswith(".yaml"):
                continue
            data = tar.extractfile(member)
            if data is None:
                continue
            (schema_subdir / rel).write_bytes(data.read())
    return schema_subdir


def compute_hashes(d: Path) -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(d.glob("*.yaml"))}


def build_schema(upstream_dir: Path, overrides_dir: Path, out_dir: Path) -> tuple[int, int, int]:
    """Wipe out_dir, copy upstream YAMLs, overlay overrides. Returns (upstream_count, replaced, added)."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    upstream_files = {p.name for p in upstream_dir.glob("*.yaml")}
    override_files = {p.name for p in overrides_dir.glob("*.yaml")} if overrides_dir.exists() else set()

    for f in sorted(upstream_files):
        shutil.copy2(upstream_dir / f, out_dir / f)
    for f in sorted(override_files):
        shutil.copy2(overrides_dir / f, out_dir / f)

    replaced = len(upstream_files & override_files)
    added = len(override_files - upstream_files)
    return len(upstream_files), replaced, added


def _existing_vendor_for(prev_hashes: dict[str, str]) -> Path | None:
    """Best-effort: locate the previously-synced upstream snapshot in .vendor/ for diff purposes."""
    if not VENDOR_DIR.exists() or not prev_hashes:
        return None
    sample = next(iter(prev_hashes.items()), None)
    if sample is None:
        return None
    sample_name, sample_hash = sample
    for ver_dir in VENDOR_DIR.iterdir():
        cand = ver_dir / "schema" / sample_name
        if cand.exists() and sha256_file(cand) == sample_hash:
            return cand.parent
    return None


def conflict_report(
    overrides_dir: Path,
    prev_hashes: dict[str, str],
    new_hashes: dict[str, str],
    prev_vendor_dir: Path | None,
    new_vendor_dir: Path,
) -> list[str]:
    """Warn for overrides whose upstream counterpart changed since the last sync. Print unified diffs when possible."""
    if not overrides_dir.exists():
        return []
    conflicts: list[str] = []
    for ov in sorted(overrides_dir.glob("*.yaml")):
        name = ov.name
        if name not in new_hashes or name not in prev_hashes:
            continue  # newly-added schema, or first sync with this override
        if prev_hashes[name] != new_hashes[name]:
            conflicts.append(name)

    if not conflicts:
        return conflicts

    print(f"\n  WARNING: {len(conflicts)} override(s) may be stale (upstream counterpart changed):")
    for name in conflicts:
        print(f"    - overrides/{name}")
        if prev_vendor_dir is None:
            continue
        prev_file = prev_vendor_dir / name
        new_file = new_vendor_dir / name
        if not (prev_file.exists() and new_file.exists()):
            continue
        diff = list(difflib.unified_diff(
            prev_file.read_text().splitlines(keepends=True),
            new_file.read_text().splitlines(keepends=True),
            fromfile=f"upstream(prev)/{name}",
            tofile=f"upstream(new)/{name}",
            n=2,
        ))
        for line in diff:
            print("      " + line.rstrip("\n"))
    return conflicts


def cmd_sync(_args: argparse.Namespace) -> int:
    version = read_version()
    print(f"syncing followthemoney @ {version}")

    upstream = download_upstream(version)
    new_hashes = compute_hashes(upstream)
    prev_hashes = read_previous_hashes()
    prev_vendor = _existing_vendor_for(prev_hashes)

    upstream_count, replaced, added = build_schema(upstream, OVERRIDES_DIR, SCHEMA_DIR)
    conflicts = conflict_report(OVERRIDES_DIR, prev_hashes, new_hashes, prev_vendor, upstream)
    write_hashes(new_hashes)

    print(
        f"\ndone — {upstream_count} from upstream, {replaced} replaced by overrides, "
        f"{added} added by overrides, {len(conflicts)} potential conflicts"
    )
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    version = read_version()
    upstream = download_upstream(version)
    expected_hashes = compute_hashes(upstream)

    stored_hashes = read_previous_hashes()
    if stored_hashes != expected_hashes:
        print(f"FAIL: .upstream-hashes.json is out of sync with upstream@{version}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        expected_dir = Path(tmp) / "schema"
        build_schema(upstream, OVERRIDES_DIR, expected_dir)
        actual = {p.name: sha256_file(p) for p in SCHEMA_DIR.glob("*.yaml")} if SCHEMA_DIR.exists() else {}
        expected = {p.name: sha256_file(p) for p in expected_dir.glob("*.yaml")}
        if actual != expected:
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            mismatched = sorted(n for n in actual if n in expected and actual[n] != expected[n])
            print(f"FAIL: schema/ is out of sync with overrides/ + upstream@{version}", file=sys.stderr)
            if missing:
                print(f"  missing in schema/: {', '.join(missing)}", file=sys.stderr)
            if extra:
                print(f"  unexpected in schema/: {', '.join(extra)}", file=sys.stderr)
            if mismatched:
                print(f"  content mismatch: {', '.join(mismatched)}", file=sys.stderr)
            return 1

    print(f"OK: schema/ matches upstream@{version} + overrides/")
    return 0


def cmd_bump_latest(args: argparse.Namespace) -> int:
    print(f"fetching latest release for {UPSTREAM_REPO}")
    url = LATEST_RELEASE_URL.format(repo=UPSTREAM_REPO)
    resp = requests.get(url, timeout=30, headers={"Accept": "application/vnd.github+json"})
    resp.raise_for_status()
    latest = resp.json()["tag_name"]

    current = read_version()
    if latest == current:
        print(f"already at latest ({current})")
        return 0

    print(f"bumping {current} -> {latest}")
    write_version(latest)
    return cmd_sync(args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync followthemoney schema YAMLs with local overrides.")
    parser.add_argument("--check", action="store_true",
                        help="verify schema/ matches expected build; exit non-zero if not")
    parser.add_argument("--bump-latest", action="store_true",
                        help="set .upstream-version to latest GitHub release, then sync")
    args = parser.parse_args()

    if args.check:
        return cmd_check(args)
    if args.bump_latest:
        return cmd_bump_latest(args)
    return cmd_sync(args)


if __name__ == "__main__":
    sys.exit(main())
