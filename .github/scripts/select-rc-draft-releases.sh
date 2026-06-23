#!/usr/bin/env bash
# Select RC draft pre-releases to prune after promote-release.
# Reads a GitHub "list releases" array on stdin and emits "<id>\t<tag_name>"
# for every draft pre-release whose tag is X.Y.Z-rcN for the given base semver.
# Seeding cleanup from the releases list (not from git tags) reclaims drafts
# whose RC tag was already deleted in an earlier, partially-failed run.
# shellcheck shell=bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: select-rc-draft-releases.sh <base-version>" >&2
  exit 2
fi

BASE="$1"
if ! echo "$BASE" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "ERROR: invalid base version '$BASE'" >&2
  exit 2
fi

jq -r --arg base "$BASE" '
  ( "^" + ($base | gsub("\\.";"\\.")) + "-rc[0-9]+$" ) as $rc
  | .[]
  | select(.draft == true and .prerelease == true and (.tag_name | test($rc)))
  | "\(.id)\t\(.tag_name)"
'
