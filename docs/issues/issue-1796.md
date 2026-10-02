---
type: issue
state: open
created: 2026-10-01T12:57:47Z
updated: 2026-10-01T12:57:47Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1796
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-02T08:18:22.915Z
---

# [Issue 1796]: [resolve-toolchain: make the resolve job's own runs-on overridable (vars)](https://github.com/vig-os/devkit/issues/1796)

The `resolve-toolchain` job's own `runs-on` is not overridable, so every
scaffolded workflow run costs one hosted job-minute on a private repo.

## The gap

`#1173` made the *downstream* runner manifest-driven via `DEVKIT_CI_RUNNER`, but
the resolve job itself is a bare literal in all seven managed workflows that
declare it:

| workflow | line |
|---|---|
| `ci.yml` | 97-99 |
| `sync-issues.yml` | 44-46 |
| `sync-main-to-dev.yml` | 52-54 |
| `abandon-release.yml` | 44-46 |
| `prepare-hotfix.yml` | 77-79 |
| `promote-release.yml` | 32-34 |
| `release.yml` | 51-53 |

`ci.yml:28-30` and `.vig-os` explain the pin as chicken-and-egg: the job
*produces* `runner-json`, so it cannot consume it. That reasoning is sound for
`.vig-os`-derived values — the file is not readable until after checkout, which
requires a runner to already be chosen.

But it does not extend to **`vars`**. GitHub lists `vars` as an available
context for `jobs.<job_id>.runs-on`, and it resolves server-side before any
runner is provisioned. So a repository or org variable can select this job's
runner without any circularity.

## Cost

On private repos GitHub bills each job rounded **up** to a whole minute. The
resolve job runs ~7s and is therefore billed at 1 minute, every run, every
workflow. Measured over one week across five private consumer repos this was
~430 billed minutes of pure bootstrap overhead, and it scales linearly with the
number of private repos onboarded. Public consumers are unaffected (hosted
minutes are free there).

## Proposed change

```yaml
runs-on: ${{ vars.DEVKIT_CI_RESOLVE_RUNNER || 'ubuntu-26.04' }}
```

applied uniformly to all seven workflows. Default unchanged, so this is a no-op
for every existing consumer until one opts in.

A repo variable rather than a `.vig-os` key is deliberate — `.vig-os` cannot be
read before a runner exists, which is the whole constraint.

## Spike this before shipping

- **No precedent in this repo.** `grep -rn 'runs-on' | grep 'vars\.'` returns
  zero hits across devkit and every consumer checked. The context-availability
  claim is from GitHub's docs, not from anything exercised here. Verify it on a
  throwaway branch before rolling it into seven files — same methodology as #992.
- **No validation path.** A malformed value (a bare comma-separated string where
  a label is expected, or a label no runner carries) does not fail fast; the job
  queues until GitHub's job-queue ceiling. The `.vig-os` path is parsed,
  defaulted and validated inside the composite action; this one would not be.
  Consider validating in `resolve-toolchain` and surfacing a clear error, or
  documenting the failure mode.

## Not a fallback mechanism

To be explicit, since it is tempting to claim it: this does **not** give
consumers an out-of-band escape hatch for a self-hosted outage. `runner-json` —
which controls where the expensive downstream jobs run — is still derived only
from `DEVKIT_CI_RUNNER` in `.vig-os`, so recovery remains a commit to that file
either way. This issue is strictly about the resolve job's own billed minute.

