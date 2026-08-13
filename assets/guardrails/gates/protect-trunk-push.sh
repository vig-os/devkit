#!/usr/bin/env bash
# guardrails: protect-trunk-push — refuse pushes that advance a protected REMOTE ref. The
# pre-push half of protect-trunk: keyed on the remote ref from the push spec, NOT on HEAD, so
# it catches what the pre-commit gate structurally can't:
#   * `git push origin HEAD:main` from a feature branch (the exact incident refspec, issue #17)
#   * commits that never fired pre-commit: clean cherry-pick/revert, plumbing (commit-tree)
#
# git feeds pre-push one line per ref on stdin: <local-ref> <local-sha> <remote-ref> <remote-sha>
# Deletions (local-sha all-zeros) are skipped — removing a stray remote branch is not advancing
# trunk, and trunk deletion is the forge's protection to enforce.
#
# prek caveat (found in review, j178/prek languages/system.rs): prek runs system hooks with
# stdin(Stdio::null()) — the refspec lines never reach us. prek DOES parse them itself and
# exports PRE_COMMIT_REMOTE_BRANCH = the remote REF of the first valid non-deletion push line
# (hook_impl.rs rsplitn parse; pre-commit sets the same var). So: consume stdin when present
# (native .git/hooks installs, full multi-ref coverage), else fall back to the env interface
# (prek/pre-commit; first pushed ref only — a multi-ref push is checked on its first line,
# which is also all prek itself checks).
#
# Same knobs as protect-trunk.sh: GUARDRAILS_PROTECTED_BRANCHES (colon-sep globs, REPLACES the
# `main:master` default, empty disables), GUARDRAILS_ALLOW_TRUNK=1 escape (loud), CI auto-allow.
set -uo pipefail

if [ "${GUARDRAILS_ALLOW_TRUNK:-0}" = 1 ]; then
  echo "guardrails/protect-trunk-push: GUARDRAILS_ALLOW_TRUNK=1 — intentional trunk push allowed." >&2
  exit 0
fi
case "${CI:-}" in true|1) exit 0 ;; esac
case "${GITHUB_ACTIONS:-}" in true|1) exit 0 ;; esac

# Trunk-merge-gate (issue #18): "advance trunk when it's EARNED" — for solo/trusted-operator
# repos, GUARDRAILS_TRUNK_MERGE_GATE=1 turns the hard refusal into a pass condition: the push
# to a protected ref is allowed iff the repo's full check suite is green RIGHT NOW. Pre-push
# is the honest seam for this (not pre-commit): the commit's own hooks already ran, and
# `nix flake check` is a SUPERSET of the commit tier (adr-matrix, budgets, ratchets, tests) —
# so green here means something new. Default off; PR-flow fleets keep the plain refusal.
trunk_merge_gate() {
  [ "${GUARDRAILS_TRUNK_MERGE_GATE:-0}" = 1 ] || return 1
  local cmd="${GUARDRAILS_TRUNK_MERGE_CMD:-nix flake check}"
  echo "guardrails/protect-trunk-push: trunk-merge-gate — earning the push with: $cmd" >&2
  # Subshell re-enables globbing (callers hold set -f for branch-glob safety); the gate is
  # only as honest as the CMD the consumer picks — a trivially-green CMD is just
  # ALLOW_TRUNK with extra steps, same trust model, same audit trail (the echo above).
  if ( set +f; $cmd ) >&2; then
    echo "guardrails/protect-trunk-push: guards green — trunk push earned." >&2
    return 0
  fi
  echo "guardrails/protect-trunk-push: guards NOT green — trunk push refused (fix the checks, or push a branch + PR)." >&2
  return 2
}
tmg_memo="" # the check suite runs at most once per push, however many refs match
trunk_merge_gate_once() {
  if [ -z "$tmg_memo" ]; then trunk_merge_gate; tmg_memo=$?; fi
  return "$tmg_memo"
}

IFS=: read -ra protected <<< "${GUARDRAILS_PROTECTED_BRANCHES-main:master}"

zeros=0000000000000000000000000000000000000000
fails=0
check_remote_ref() { # $1 = remote ref (refs/heads/... or a bare branch name from the env path)
  local ref="$1" branch pat
  branch="${ref#refs/heads/}"
  case "$ref" in refs/*) [ "$branch" = "$ref" ] && return 0 ;; esac # tags/notes/etc. — only heads are trunk
  set -f
  for pat in "${protected[@]:-}"; do # :- keeps bash 3.2 alive on the empty-knob opt-out path
    [ -n "$pat" ] || continue
    # shellcheck disable=SC2254  # $pat is intentionally a glob
    case "$branch" in
      $pat)
        if trunk_merge_gate_once; then
          : # trunk-merge-gate earned this push — green guards ARE the pass condition
        else
          echo "guardrails/protect-trunk-push: refusing to push to protected '$branch' — trunk advances by merge/PR only." >&2
          echo "  Push a feature branch and open a PR:  git push origin HEAD:refs/heads/<feature-name>" >&2
          echo "  Intentional (hotfix/release)?         GUARDRAILS_ALLOW_TRUNK=1 git push ..." >&2
          echo "  Solo/trunk-flow with green guards?    GUARDRAILS_TRUNK_MERGE_GATE=1 (earn it — see 'guardrails info')" >&2
          fails=$((fails + 1))
        fi
        ;;
    esac
  done
  set +f
}

saw_stdin=0
while read -r _local_ref local_sha remote_ref _remote_sha; do
  [ -n "${remote_ref:-}" ] || continue
  saw_stdin=1
  [ "$local_sha" = "$zeros" ] && continue # deletion, not an advance
  check_remote_ref "$remote_ref"
done

# prek/pre-commit path: stdin was nulled, but the runner parsed the push and exported the
# remote ref of the first valid line. Without it (nothing to push), there is nothing to check.
if [ "$saw_stdin" = 0 ] && [ -n "${PRE_COMMIT_REMOTE_BRANCH:-}" ]; then
  check_remote_ref "$PRE_COMMIT_REMOTE_BRANCH"
fi

[ "$fails" -eq 0 ] || exit 1
