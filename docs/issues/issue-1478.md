---
type: issue
state: open
created: 2026-08-12T14:32:56Z
updated: 2026-08-12T14:32:56Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1478
comments: 0
labels: bug
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-08-13T04:18:10.744Z
---

# [Issue 1478]: [[BUG] CI reports Tests green when pyproject.toml is missing — a deleted Python suite passes silently](https://github.com/vig-os/devkit/issues/1478)

### Description

A repo whose `pyproject.toml` disappears still reports a green `Tests` check. The scaffolded recipes are guarded on the manifest's existence:

```just
test *args:
    @if [ -f pyproject.toml ]; then uv run pytest {{ args }} || { rc=$?; [ "$rc" -eq 5 ] || exit "$rc"; }; fi
```

(`assets/workspace/justfile.project:48-49`, same shape for `test-cov:53-54`, `lint:30`, `format:35`, `sync:63`.)

Two deliberate leniencies compose into one blind spot:

- no `pyproject.toml` → the whole recipe body is skipped, exit 0;
- `pyproject.toml` present but nothing collected → pytest's exit 5 is swallowed (#1281).

Both are individually correct — the recipes must be safe in a non-Python repo, and "zero tests collected" is a legitimate state for a fresh scaffold. Together they mean **CI cannot distinguish "this repo has no Python suite by design" from "this repo's Python suite vanished"**, and reports success for both.

### Steps to Reproduce

Live instance, 1.8.0-rc3 (devkit-smoke-test#359):

1. The rc3 smoke deploy removed `pyproject.toml`, `uv.lock`, `src/` and `tests/` from the deploy branch (#1466).
2. CI ran on that branch. `Tests` reported **SUCCESS**.
3. The only check that objected was `Scaffold Drift`, and it objected for an unrelated downstream reason (CodeQL/`.gitignore` re-rendered language-neutral because language detection no longer saw a Python repo).

A repo had its entire test suite deleted and the test job said green.

### Expected Behavior

CI distinguishes "no suite expected" from "suite expected but absent". A repo that was Python at its last scaffold and has no `pyproject.toml` now should fail, or at minimum warn loudly, rather than pass silently.

### Actual Behavior

`just test` exits 0 and the `Tests` check is green. Nothing in the run output indicates that no tests ran.

### Impact

Low frequency, high cost when it fires. It is the reason #1466's damage travelled as far as it did: the deletion passed CI unremarked, and the failure that finally surfaced pointed at the drift gate rather than at the missing project — costing a diagnosis hop on a blocked release train.

The exposure is consumer-wide, not devkit-only: every scaffolded Python repo carries these recipes and the same `Tests` job.

### Possible Solution

Not prescriptive — the tension is real, and whatever is chosen must keep a genuinely non-Python repo green.

1. **Make the expectation explicit.** `.vig-os` already records what the scaffold resolved; a `DEVKIT_LANGUAGES`-style key (or reusing the language detection that already runs at scaffold time, `assets/init-workspace.sh:928-943`) lets the recipe assert "this repo is Python, so a missing `pyproject.toml` is an error" instead of inferring absence means non-Python.
2. **Report, don't just skip.** Have the recipe echo a clear `no pyproject.toml — skipping` line, and have the CI job surface it in the step summary. Cheap, no semantics change, removes the silence.
3. **Split the two leniencies.** Keep exit 5 swallowed only when a `tests/` directory is absent; once a repo has a test directory, "zero collected" is a signal, not a no-op.
4. Consider the same treatment for `lint` / `format`, which have the identical guard and the identical blind spot.

Option 1 is the only one that closes the hole rather than narrowing it; options 2 and 3 are cheap mitigations worth having regardless.

### Environment

devkit 1.8.0, `assets/workspace/justfile.project`, and the `Tests` job in the scaffolded `ci.yml`.

### Changelog Category

Changed

Refs: #1281, #1466

