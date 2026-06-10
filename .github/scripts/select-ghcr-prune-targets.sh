#!/usr/bin/env bash
# Select GHCR package version IDs to prune after promote-release.
# Emits RC image versions for the base semver and matching cosign signature objects.
# shellcheck shell=bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: select-ghcr-prune-targets.sh <base-version>" >&2
  exit 2
fi

BASE="$1"
if ! echo "$BASE" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "ERROR: invalid base version '$BASE'" >&2
  exit 2
fi

jq -r --arg base "$BASE" '
  ( "^" + ($base | gsub("\\.";"\\.")) + "-rc[0-9]+(-(amd64|arm64))?$" ) as $rc
  | . as $all
  | [ $all[] | select(any((.metadata.container.tags // [])[]; test($rc))) ] as $imgs
  | ($imgs | map(.name | sub("^sha256:"; ""))) as $digests
  | ( $imgs[].id ),
    ( $all[]
      | select(
          ((.metadata.container.tags // []) | length) > 0
          and all((.metadata.container.tags // [])[]; startswith("sha256-"))
          and any((.metadata.container.tags // [])[];
              (sub("^sha256-"; "") | sub("\\..*$"; "")) as $h
              | ($digests | index($h)) != null)
        )
      | .id
    )
'
