#!/usr/bin/env bash
# guardrails: protect-trunk — refuse direct commits on a protected branch (trunk advances by
# merge/PR only, never by a local commit). Catches the whole "right change, wrong place" class
# that content gates can't see: a session cd's into a clone sitting on main and commits feature
# work straight to trunk (real incident — four commits on main, one pushed, see issue #17).
#
# Detection: current branch via `git symbolic-ref`; when HEAD is detached we probe the rebase
# state files so a rebase OF a protected branch still blocks (plain detached work is allowed —
# bisect, checkout <sha>, cherry-pick surgery are fine).
#
# Knobs (the usual GUARDRAILS_* idiom):
#   GUARDRAILS_PROTECTED_BRANCHES  colon-separated glob list; REPLACES the default `main:master`
#                                  (set empty to disable — trunk-flow repos opt out cleanly;
#                                  `case` globs, so `release/*` also matches `release/1.0/x`)
#   GUARDRAILS_ALLOW_TRUNK=1       one-shot escape for an intentional trunk write (hotfix) — loud
#   CI / GITHUB_ACTIONS            auto-allow: release bots and CI never need the escape
set -uo pipefail

# CI context is a legitimate trunk writer (release-please, merge queues) — never block there.
if [ "${GUARDRAILS_ALLOW_TRUNK:-0}" = 1 ]; then
  echo "guardrails/protect-trunk: GUARDRAILS_ALLOW_TRUNK=1 — intentional trunk write allowed." >&2
  exit 0
fi
case "${CI:-}" in true|1) exit 0 ;; esac
case "${GITHUB_ACTIONS:-}" in true|1) exit 0 ;; esac

# Not a git repo (docs checkout, sandbox) → nothing to protect.
git_dir="$(git rev-parse --git-dir 2>/dev/null)" || exit 0

branch="$(git symbolic-ref --short -q HEAD || true)"
if [ -z "$branch" ]; then
  # Detached HEAD. A rebase detaches exactly while it rewrites the branch — probe the rebase
  # state so `git rebase` ON main doesn't slip through; genuinely detached work stays allowed.
  for state in rebase-merge rebase-apply; do
    if [ -f "$git_dir/$state/head-name" ]; then
      branch="$(cat "$git_dir/$state/head-name")"
      branch="${branch#refs/heads/}"
      break
    fi
  done
  [ -n "$branch" ] || exit 0
fi

IFS=: read -ra protected <<< "${GUARDRAILS_PROTECTED_BRANCHES-main:master}"

# trunk_commit_allowed: the verdict seam. Today: a protected branch never takes a direct commit.
# extension point: #18's trunk-merge-gate swaps this body for "pass iff `guardrails gate` is
# green" — same hook, same message shape, richer pass condition.
trunk_commit_allowed() { # $1 = branch
  local pat
  set -f # branch/pattern glob chars must not pathname-expand
  for pat in "${protected[@]:-}"; do # :- keeps bash 3.2 alive on the empty-knob opt-out path
    [ -n "$pat" ] || continue # `:main:` boundary empties must not match everything
    # shellcheck disable=SC2254  # $pat is intentionally a glob
    case "$1" in $pat) set +f; return 1 ;; esac
  done
  set +f
  return 0
}

if ! trunk_commit_allowed "$branch"; then
  cat >&2 <<EOF
guardrails/protect-trunk: HEAD is '$branch' — this repo advances trunk by merge/PR only.
  Move your work to a feature branch (keeps staged changes):
      git switch -c <feature-name>
  Intentional trunk write (hotfix/release)? Say so explicitly:
      GUARDRAILS_ALLOW_TRUNK=1 git commit ...
  Trunk-flow repo? Opt out for good:
      export GUARDRAILS_PROTECTED_BRANCHES=""   # e.g. in .envrc / flake devShell
EOF
  exit 1
fi
