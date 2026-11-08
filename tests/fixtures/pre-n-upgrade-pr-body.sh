#!/usr/bin/env bash
# Snapshot of the adoption PR-body step shipped in tag 1.18.0 (#1929).
set -euo pipefail
# No adoption issue and no auto-close marker (#1405): a no-diff run
# now simply skips publish + PR with nothing to garbage-collect (the
# stranded-issue cleanup this replaced was #1347).
TITLE="chore: adopt devkit ${TARGET}"
BODY="$(printf 'Automated devkit upgrade to %s via install.sh --force.\n\nReview the scaffold + flake.lock diff and merge. Release notes: https://github.com/vig-os/devkit/releases/tag/%s\n' "$TARGET" "$TARGET")"
# The flake-input outcome (#1497): a skipped advance is a decision
# the consumer makes, not a silent no-op — put it where they review.
if [ -n "$FLAKE_BUMP" ]; then
  BODY="$(printf '%s\n%s\n' "$BODY" "$FLAKE_BUMP")"
fi
# Preserved-config drift (#1652): the upgrade could not deliver these
# hook fixes — only the consumer can fold them in, so say so where
# they review the adoption.
# shellcheck disable=SC2016  # backticks are literal Markdown code spans, not command substitution
if [ -n "$HOOK_DRIFT" ]; then
  BODY="$(printf '%s\n**Preserved config keeps a retired hook block** — the upgrade cannot rewrite a consumer-owned file; fold these in by hand (see MIGRATION.md):\n\n```\n%s\n```\n' "$BODY" "$HOOK_DRIFT")"
fi
# Reconciled blocks (#1654): this upgrade DID rewrite the preserved
# hook config. Say so where the diff is reviewed, next to the hunk.
# shellcheck disable=SC2016  # backticks are literal Markdown code spans, not command substitution
if [ -n "$HOOK_RECONCILE" ]; then
  BODY="$(printf '%s\n**Preserved hook config reconciled** — the upgrade rewrote `.pre-commit-config.yaml`; review the hunk (see MIGRATION.md):\n\n```\n%s\n```\n' "$BODY" "$HOOK_RECONCILE")"
fi
if gh pr view "$BRANCH" --json number >/dev/null 2>&1; then
  gh pr edit "$BRANCH" --title "$TITLE" --body "$BODY"
  echo "Updated the existing adoption PR."
else
  gh pr create --base "$BASE" --head "$BRANCH" --title "$TITLE" --body "$BODY"
  echo "Opened the adoption PR."
fi
