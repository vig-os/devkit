#!/usr/bin/env bash
# guardrails: duplication nudge — token-window clone detector (reinvention vs reuse).
# N hand-rolled copies of the same block (modal/confirm handlers, esc-return
# boilerplate, ...) are drift no per-line gate can see: no single line is wrong,
# yet the divergence is expensive (multi-round debugging to find the one copy
# that drifted). This surfaces that class early: normalize each line (strip
# comments, collapse whitespace), slide a window of K significant lines, and flag
# any window that recurs at ≥2 sites. Extract a shared helper, or annotate.
#
# NUDGE by default (report, exit 0) — a hard gate here false-positives on
# intentional repetition and trains `--no-verify`. Promote per-repo with
# GUARDRAILS_DUP_ENFORCE=1.
#
# STALENESS ESCALATION (anti-alarm-fatigue): a flat, repeated nudge habituates —
# so instead of nagging on a timer, the loudness tracks *persistence*. A finding
# recorded in the ledger (`--record`, committed like perf-history.csv) carries a
# first-seen commit; its age is counted in COMMITS to HEAD (git as the
# deterministic clock — no wall-time, stays reproducible). A clone that survives
# GUARDRAILS_DUP_ENFORCE_AGE commits undealt-with has a decayed false-positive
# probability, so it AUTO-PROMOTES from nudge → hard block: the nudge earns the
# right to become a gate. Decorate or extract it and it drops from the ledger on
# the next `--record` (ratchet-shrink). No infinite nag: every finding resolves
# to silence or a one-time block.
#
# Precision-first: an EXACT ≥K normalized-line match is a real (type-1/2) clone,
# so noise stays near zero. Diverged (type-4 "same intent, different code")
# clones are out of scope for v1 — that needs fuzzy token/embedding similarity,
# whose noise floor is too high to nudge on without triage. See CONVENTIONS.md.
#
# Modes:
#   guardrails-duplication [paths...]            check + nudge/escalate (default)
#   guardrails-duplication --record [paths...]   reconcile the ledger to disk
# Knobs:
#   GUARDRAILS_DUP_ENFORCE=1        promote ALL hits from nudge to hard gate
#   GUARDRAILS_DUP_ENFORCE_AGE=N    auto-promote a finding once it has persisted
#                                   ≥N commits (0 = off; ledger-driven)
#   GUARDRAILS_DUP_LEDGER=path      ledger file (default .guardrails/dup-ledger.tsv)
#   GUARDRAILS_DUP_MIN_LINES=N      window size in significant lines (default 6)
#   GUARDRAILS_DUP_EXTS="rs go ..." file extensions to scan (default below)
#   GUARDRAILS_DUP_ALLOW="glob:..." bulk-exclude path globs (space/colon-sep)
#   per-file escape: a `guardrails-ok` line drops the file from the corpus.
set -uo pipefail

record=""
if [ "${1:-}" = "--record" ]; then record=1; shift; fi
roots=("${@:-.}")
enforce="${GUARDRAILS_DUP_ENFORCE:-}"
enforce_age="${GUARDRAILS_DUP_ENFORCE_AGE:-0}"
case "$enforce_age" in ''|*[!0-9]*) enforce_age=0 ;; esac # garbage knob → escalation off, not a bash error
ledger="${GUARDRAILS_DUP_LEDGER:-.guardrails/dup-ledger.tsv}"
allow="${GUARDRAILS_DUP_ALLOW:-}"
min_lines="${GUARDRAILS_DUP_MIN_LINES:-6}"
exts="${GUARDRAILS_DUP_EXTS:-rs go py ts tsx js jsx c h cc cpp hpp java rb sh nix}"
TAB="$(printf '\t')"

files() {
  for p in "$@"; do
    if [ -d "$p" ]; then git -C "$p" ls-files 2>/dev/null | sed "s#^#${p%/}/#" || find "$p" -type f
    elif [ -f "$p" ]; then echo "$p"; fi
  done
}

allowed() { # path matches a GUARDRAILS_DUP_ALLOW glob?
  local f="$1" g
  for g in ${allow//:/ }; do
    # shellcheck disable=SC2254
    case "$f" in $g) return 0 ;; esac
  done
  return 1
}

ext_ok() {
  local f="$1" e
  for e in $exts; do case "$f" in *."$e") return 0 ;; esac; done
  return 1
}

# Surviving corpus: right extension, not annotated, not bulk-allowed. Exclude a
# top-level tests/ component too (mirrors the other gates' relative-path skip).
list=()
while IFS= read -r f; do
  [ -f "$f" ] || continue
  case "$f" in tests/* | */tests/*) continue ;; esac
  ext_ok "$f" || continue
  grep -q 'guardrails-ok' "$f" && continue
  allowed "$f" && continue
  list+=("$f")
done < <(files "${roots[@]}")

# Detection emits one machine record per clone group:
#   GROUP<TAB>canonical_hash<TAB>n_sites<TAB>span_lines<TAB>site1|site2|...
groups_raw=""
if [ "${#list[@]}" -gt 1 ]; then
  groups_raw="$(GUARDRAILS_DUP_MIN_LINES="$min_lines" python3 - "${list[@]}" <<'PY'
import hashlib, multiprocessing, os, sys

K = max(1, int(os.environ.get("GUARDRAILS_DUP_MIN_LINES", "6")))
paths = sorted(set(sys.argv[1:]))


def norm(line):
    for marker in ("//", "#"):
        i = line.find(marker)
        if i != -1:
            line = line[:i]
    return " ".join(line.split())


def significant(nl):
    core = "".join(ch for ch in nl if ch.isalnum() or ch == "_")
    return len(core) >= 3


# Per-file scan: read + normalize + K-window hash. Embarrassingly parallel — this is the
# compute that made duplication the wall-clock ceiling of the whole gate set (#34: the
# verdict was "parallelize the lone compute island, don't build the engine"). The union-find
# merge below stays serial (cheap).
def scan(f):
    try:
        with open(f, "r", errors="replace") as fh:
            rows = [(ln, nl) for ln, raw in enumerate(fh, 1)
                    if significant(nl := norm(raw))]
    except OSError:
        return f, None, None
    if not rows:
        return f, None, None
    win = []
    for i in range(len(rows) - K + 1):
        text = "\n".join(rows[j][1] for j in range(i, i + K))
        win.append((i, hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()))
    # Only line NUMBERS cross the pipe — the normalized text is dead weight once the
    # windows are hashed here in the worker (pickle volume ≈ the whole corpus otherwise).
    return f, [r[0] for r in rows], win


# fork, not spawn: this script arrives on stdin, so spawn's __main__ re-import is impossible
# (macOS default). Workers touch only hashlib/str — fork-safe. Small corpora skip the pool
# (fork+IPC overhead beats the win under ~32 files). pool.map preserves order → deterministic.
cpus = os.cpu_count() or 1
workers = min(cpus, 8)
if len(paths) >= 32 and cpus > 1 and "fork" in multiprocessing.get_all_start_methods():
    with multiprocessing.get_context("fork").Pool(workers) as pool:
        results = pool.map(scan, paths, chunksize=max(1, len(paths) // (workers * 4)))
else:
    results = [scan(f) for f in paths]

sig = {}
occ = {}
for f, rows, win in results:
    if rows is None:
        continue
    sig[f] = rows
    for i, h in win:
        occ.setdefault(h, []).append((f, i))

dup = {h: os_ for h, os_ in occ.items() if len(os_) >= 2}

cover = {}
for h, occs in dup.items():
    for (f, i) in occs:
        for j in range(i, i + K):
            cover.setdefault((f, j), set()).add(h)

by_file = {}
for (f, j) in cover:
    by_file.setdefault(f, set()).add(j)
regions = []
for f in sorted(by_file):
    idxs = sorted(by_file[f])
    start = prev = idxs[0]
    for x in idxs[1:]:
        if x == prev + 1:
            prev = x
        else:
            regions.append((f, start, prev))
            start = prev = x
    regions.append((f, start, prev))


def region_hashes(r):
    f, s, e = r
    hs = set()
    for j in range(s, e + 1):
        hs |= cover.get((f, j), set())
    return hs


parent = list(range(len(regions)))


def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


h2r = {}
for ri, r in enumerate(regions):
    for h in region_hashes(r):
        h2r.setdefault(h, []).append(ri)
for ris in h2r.values():
    for k in range(1, len(ris)):
        a, b = find(ris[0]), find(ris[k])
        if a != b:
            parent[a] = b

groups = {}
for ri, r in enumerate(regions):
    groups.setdefault(find(ri), []).append(r)

out = []
for members in groups.values():
    sites = sorted(set(members))
    if len(sites) < 2:
        continue
    span = max(e - s + 1 for _, s, e in sites)
    labels = [f"{f}:{sig[f][s]}-{sig[f][e]}" for (f, s, e) in sites]
    hs = set()
    for r in sites:
        hs |= region_hashes(r)
    ghash = min(hs) if hs else ""
    out.append((span, ghash, len(labels), labels))

for span, ghash, nsites, labels in sorted(out, key=lambda t: (-t[0], t[1])):
    print(f"GROUP\t{ghash}\t{nsites}\t{span}\t{'|'.join(labels)}")
PY
)"
fi

# Lifecycle (first-seen stamping, age-in-commits, growth, promotion, ledger reconcile)
# lives in the shared nudge-ledger harness (issue #32); this gate keeps detection and
# vocabulary only. Findings: key=clone-hash, count=nsites, label=span|nsites|sites.
# Fail-open by design: if the harness dies mid-check (its exit is discarded by the process
# substitution below) the nudge still fires from `hits`, just without per-clone tiers —
# degraded and visible, never a false block.
nl_bin="$(command -v guardrails-nudge-ledger || true)"
[ -n "$nl_bin" ] || nl_bin="$(cd "$(dirname "$0")" && pwd)/../tools/nudge-ledger.sh"

findings=""; hits=0
while IFS="$TAB" read -r tag h nsites span labels; do
  [ "$tag" = GROUP ] || continue
  hits=$((hits + 1))
  findings+="${h}${TAB}${nsites}${TAB}${span}${TAB}${nsites}${TAB}${labels}"$'\n'
done <<< "$groups_raw"

# --record: the harness reconciles the ledger (persisting keys keep first-seen, new keys
# stamp at HEAD, resolved keys drop → only shrinks unless real drift appears; sorted).
if [ -n "$record" ]; then
  printf '%s' "$findings" | "$nl_bin" record --ledger "$ledger"
  exit 0
fi

report=""; promoted=0
while IFS="$TAB" read -r h tier span nsites labels; do
  [ -n "$h" ] || continue
  sites_disp="${labels//|/, }"
  case "$tier" in
    new) t="(new)" ;;
    promoted:*)
      rest="${tier#promoted:}"; age="${rest%%:*}"
      grew=""; case "$rest" in *:grew:*) g="${rest##*:grew:}"; grew=" grew ${g%>*}→${g#*>} sites" ;; esac
      t="(persisted ${age} commits${grew} → PROMOTED to block)"
      promoted=$((promoted + 1)) ;;
    persisted:*:grew:*)
      rest="${tier#persisted:}"; age="${rest%%:*}"; g="${rest##*:grew:}"
      t="(persisted ${age} commits grew ${g%>*}→${g#*>} sites) ⚠" ;;
    persisted:*) t="(persisted ${tier#persisted:} commits)" ;;
    *) t="($tier)" ;;
  esac
  report+="  dup: ~${span} significant lines cloned across ${nsites} sites ${t}: ${sites_disp}"$'\n'
done < <(printf '%s' "$findings" | "$nl_bin" check --ledger "$ledger" --enforce-age "$enforce_age")

[ "$hits" -gt 0 ] || exit 0
printf '%s' "$report"
msg="guardrails/duplication: $hits cloned block group(s) (≥${min_lines} normalized lines). Extract a shared helper, or bless intentional repetition with a \`guardrails-ok\` line / GUARDRAILS_DUP_ALLOW glob."
if [ "$promoted" -gt 0 ]; then
  echo "$msg" >&2
  echo "  ↑ $promoted finding(s) auto-promoted to a hard block after persisting ≥${enforce_age} commits undealt-with." >&2
  exit 1
fi
if [ -n "$enforce" ]; then
  echo "$msg" >&2
  exit 1
fi
echo "nudge: $msg" >&2
exit 0
