#!/usr/bin/env bash
# Red-green tests for the adr-matrix gate. Pure bash, no deps. Run: gates/test-adr-matrix.sh
#
# NOTE ON FIXTURES: these tests create real ADR *files*, because the files are the gate's source of
# truth. The previous suite only ever wrote an index — which is why it could not express "an
# Accepted ADR exists but was never indexed", the exact case that shipped two ADR-0005s in a
# consumer repo. A gate's tests have to be able to state the failure the gate exists to catch.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
gate="$here/adr-matrix.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fails=0

# chk <desc> <want-exit> <env...> -- <index> <matrix>
chk() {
  local desc="$1" want="$2"; shift 2
  local e=(); while [ "$1" != "--" ]; do e+=("$1"); shift; done; shift
  env "${e[@]}" "$gate" "$1" "$2" >/dev/null 2>&1
  local got=$?
  if [ "$got" = "$want" ]; then echo "ok    — $desc"; else echo "FAIL  — $desc (want $want got $got)"; fails=$((fails + 1)); fi
}

# adr <dir> <id> <slug> <status>
adr() { printf '# ADR %s — %s\n\n- Status: %s\n- Date: 2026-01-01\n' "$2" "$3" "$4" >"$1/$2-$3.md"; }

# ---------------------------------------------------------------------------
# A. files are the source of truth
# ---------------------------------------------------------------------------
d="$tmp/a"; mkdir -p "$d/adr"
adr "$d/adr" 0001 a Accepted
adr "$d/adr" 0002 b Accepted
adr "$d/adr" 0003 c Proposed
adr "$d/adr" 0004 d Accepted
cat >"$d/adr/README.md" <<'EOF'
| [0001](0001-a.md) | first feature  | **Accepted** |
| [0002](0002-b.md) | second feature | **Accepted** |
| [0003](0003-c.md) | roadmap design | **Proposed** |
| [0004](0004-d.md) | a decision     | **Accepted** |
EOF
matrix="$d/FEATURE-MATRIX.md"

printf 'row cites ADR-0001 only\n' >"$matrix"
chk "Accepted-but-uncited (0002,0004) caught"            1 -- "$d/adr/README.md" "$matrix"
chk "exempt 0004 but 0002 still uncited → caught"        1 ADR_MATRIX_EXEMPT=0004 -- "$d/adr/README.md" "$matrix"

printf 'cites ADR-0001 ADR-0002 ADR-0004\n' >"$matrix"
chk "all Accepted cited; Proposed 0003 ignored → pass"   0 -- "$d/adr/README.md" "$matrix"

printf 'cites ADR-0001 only\n' >"$matrix"
chk "0002+0004 exempt, 0001 cited → pass"                0 ADR_MATRIX_EXEMPT="0002 0004" -- "$d/adr/README.md" "$matrix"

chk "missing ADR index is a no-op"                       0 -- "$d/nope/README.md" "$matrix"

# ---------------------------------------------------------------------------
# B. the case the old suite could not express: Accepted on disk, absent from
#    the index. The gate used to read only the index, so this passed silently.
# ---------------------------------------------------------------------------
d="$tmp/b"; mkdir -p "$d/adr"
adr "$d/adr" 0001 a Accepted
adr "$d/adr" 0002 unindexed Accepted
cat >"$d/adr/README.md" <<'EOF'
| [0001](0001-a.md) | first feature | **Accepted** |
EOF
matrix="$d/FEATURE-MATRIX.md"
printf 'cites ADR-0001 and ADR-0002\n' >"$matrix"
chk "Accepted ADR missing from the index caught"         1 -- "$d/adr/README.md" "$matrix"

# …and an index that disagrees with the file's own status is drift too.
cat >"$d/adr/README.md" <<'EOF'
| [0001](0001-a.md)         | first feature | **Accepted** |
| [0002](0002-unindexed.md) | second        | **Proposed** |
EOF
chk "index Status disagreeing with the ADR file caught"  1 -- "$d/adr/README.md" "$matrix"

cat >"$d/adr/README.md" <<'EOF'
| [0001](0001-a.md)         | first feature | **Accepted** |
| [0002](0002-unindexed.md) | second        | **Accepted** |
EOF
chk "index complete and agreeing → pass"                 0 -- "$d/adr/README.md" "$matrix"

# ---------------------------------------------------------------------------
# C. duplicate ids — every `ADR-NNNN` citation is ambiguous while both exist
# ---------------------------------------------------------------------------
d="$tmp/c"; mkdir -p "$d/adr"
adr "$d/adr" 0001 one Accepted
adr "$d/adr" 0001 other Accepted
cat >"$d/adr/README.md" <<'EOF'
| [0001](0001-one.md) | first | **Accepted** |
EOF
matrix="$d/FEATURE-MATRIX.md"
printf 'cites ADR-0001\n' >"$matrix"
chk "two files claiming the same id caught"              1 -- "$d/adr/README.md" "$matrix"

# ---------------------------------------------------------------------------
# D. legacy fallback: an index with no ADR files beside it still works
# ---------------------------------------------------------------------------
d="$tmp/d"; mkdir -p "$d/adr"
cat >"$d/adr/README.md" <<'EOF'
| [0001](0001-a.md) | first feature | **Accepted** |
| [0002](0002-b.md) | second        | **Accepted** |
EOF
matrix="$d/FEATURE-MATRIX.md"
printf 'cites ADR-0001 only\n' >"$matrix"
chk "index-only repo: uncited Accepted still caught"     1 -- "$d/adr/README.md" "$matrix"
printf 'cites ADR-0001 ADR-0002\n' >"$matrix"
chk "index-only repo: all cited → pass"                  0 -- "$d/adr/README.md" "$matrix"

if [ "$fails" = 0 ]; then echo "adr-matrix: all tests pass"; else echo "adr-matrix: $fails FAILED"; exit 1; fi
