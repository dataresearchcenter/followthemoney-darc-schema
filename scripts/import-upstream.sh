#!/usr/bin/env bash
# Import an upstream followthemoney release into the `vendor` branch.
#
# Usage:
#   scripts/import-upstream.sh             # latest release from the GitHub API
#   scripts/import-upstream.sh v4.10.0     # a specific tag
#
# Run this ONLY on the `vendor` branch. The script wipes schema/ and replaces it
# with upstream's followthemoney/schema/*.yaml, writes .upstream-version, and
# commits + tags. To bring the new upstream into main, switch to main afterwards
# and run `git merge vendor`.

set -euo pipefail

UPSTREAM_REPO="opensanctions/followthemoney"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "vendor" ]; then
  echo "error: must be on 'vendor' branch (currently on '$branch')" >&2
  exit 1
fi

if ! git diff-index --quiet HEAD --; then
  echo "error: working tree dirty; commit or stash first" >&2
  exit 1
fi

tag="${1:-}"
if [ -z "$tag" ]; then
  # Use the tags API rather than /releases/latest — upstream sometimes ships
  # hotfix tags (e.g. v4.8.2) that aren't promoted to "releases" on GitHub,
  # and /releases/latest would silently miss them.
  echo "querying latest tag for $UPSTREAM_REPO"
  tag="$(curl -fsSL -H 'Accept: application/vnd.github+json' \
    "https://api.github.com/repos/${UPSTREAM_REPO}/tags" \
    | sed -n 's/.*"name": *"\([^"]*\)".*/\1/p' | head -n1)"
  if [ -z "$tag" ]; then
    echo "error: could not determine latest tag" >&2
    exit 1
  fi
  echo "latest is $tag"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

url="https://github.com/${UPSTREAM_REPO}/archive/refs/tags/${tag}.tar.gz"
echo "fetching $url"
curl -fsSL "$url" -o "$tmp/upstream.tar.gz"

# Extract only followthemoney/schema/*.yaml, stripping the
# `followthemoney-<ver>/followthemoney/schema/` prefix so we get a flat dir of yaml files.
mkdir -p "$tmp/schema"
tar -xzf "$tmp/upstream.tar.gz" -C "$tmp/schema" \
    --strip-components=3 \
    --wildcards '*/followthemoney/schema/*.yaml'

count="$(find "$tmp/schema" -name '*.yaml' | wc -l | tr -d ' ')"
if [ "$count" -eq 0 ]; then
  echo "error: no schema YAMLs extracted from upstream tarball" >&2
  exit 1
fi
echo "extracted $count schema files"

mkdir -p schema
rm -f schema/*.yaml
cp "$tmp/schema/"*.yaml schema/
printf '%s\n' "$tag" > .upstream-version

git add schema/ .upstream-version
if git diff --cached --quiet; then
  echo "already up to date at $tag"
  exit 0
fi

git commit -m "Import upstream $tag"
git tag -f "upstream/$tag"

echo
echo "vendor branch now at upstream $tag"
echo "next: git checkout main && git merge vendor"
