#!/usr/bin/env bash
# release.sh — bump version, tag, and push to trigger CI release
#
# Usage:
#   ./release.sh          # bump patch  (v0.1.1 → v0.1.2)
#   ./release.sh minor    # bump minor  (v0.1.1 → v0.2.0)
#   ./release.sh major    # bump major  (v0.1.1 → v1.0.0)

set -euo pipefail

BUMP="${1:-patch}"

# ── Get latest tag ─────────────────────────────────────────────────────────────
LATEST=$(git tag --sort=-v:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -1)

if [[ -z "$LATEST" ]]; then
    LATEST="v0.0.0"
    echo "No existing version tag found, starting from $LATEST"
else
    echo "Current version: $LATEST"
fi

# ── Parse major.minor.patch ────────────────────────────────────────────────────
VERSION="${LATEST#v}"   # strip leading 'v'
MAJOR=$(echo "$VERSION" | cut -d. -f1)
MINOR=$(echo "$VERSION" | cut -d. -f2)
PATCH=$(echo "$VERSION" | cut -d. -f3)

# ── Bump ───────────────────────────────────────────────────────────────────────
case "$BUMP" in
    major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
    minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
    patch) PATCH=$((PATCH + 1)) ;;
    *)
        echo "Error: unknown bump type '$BUMP'. Use: patch | minor | major" >&2
        exit 1
        ;;
esac

NEXT="v${MAJOR}.${MINOR}.${PATCH}"
echo "Next version:    $NEXT"

# ── Confirm ────────────────────────────────────────────────────────────────────
read -rp "Tag and push $NEXT? [y/N] " CONFIRM
if [[ "${CONFIRM,,}" != "y" ]]; then
    echo "Aborted."
    exit 0
fi

# ── Tag and push ───────────────────────────────────────────────────────────────
git tag "$NEXT"
git push origin "$NEXT"

echo "Done! GitHub Actions will now build and release $NEXT."
