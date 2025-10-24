#!/usr/bin/env bash
set -euo pipefail

# Fetch a community E46 DBC into ./dbc/
REPO_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
DBC_DIR="$REPO_DIR/dbc"
mkdir -p "$DBC_DIR"

# Example: clone a public repo containing e46.dbc (adjust as needed)
# NOTE: Validate license/accuracy for your use case.
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Replace the URL/Path with your preferred source
GIT_URL="https://github.com/andymartell/e46.git"
FILE_PATH="e46.dbc"

git clone --depth 1 "$GIT_URL" "$TMP_DIR/e46"
cp "$TMP_DIR/e46/$FILE_PATH" "$DBC_DIR/e46.dbc"

echo "[OK] DBC copied to $DBC_DIR/e46.dbc"
