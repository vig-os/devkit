---
type: issue
state: closed
created: 2026-09-25T10:03:42Z
updated: 2026-09-25T17:20:15Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1708
comments: 2
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:41.902Z
---

# [Issue 1708]: [Nightly security scan (dev): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1708)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `dev` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `dev`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-25T10:03:40Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/36121477017
- **Findings artifact:** `nix-image-cve-scan-dev` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 01:22 PM_

## Diagnosis

The three unexcepted findings are all in **perl 5.42.0**, which is back in the `dev` image closure:

- CVE-2026-4176 (9.8), CVE-2026-13221 (9.1), CVE-2026-57432 (8.4)

`main` scanned green on the same run with the **same nixpkgs pin** (`6d663c05`), so this is not a feed event and not a pin problem — it is a closure change on `dev`. The 2026-09-24 `dev` leg (run 35982816399) still showed only the unbound batch, so the change landed on 2026-09-25 before 09:59 UTC.

**Cause: #1690 (#1687).** `nix/bats.nix` now wraps `bats` with GNU `parallel` on its PATH so `bats --jobs` works. GNU parallel is a perl script, and the bats wrapper is part of the image env (`nix/devtools.nix`), so perl rides back in:

```
$ nix why-depends .#devkitImageEnv /nix/store/…-perl-5.42.0
/nix/store/jqybbpzf…-devcontainer-image-env
└───/nix/store/y7xhzcvw…-bats-with-libraries-1.12.0
    └───/nix/store/n9ykcqsk…-parallel-20260422
        └───/nix/store/myzwgd3y…-perl-5.42.0
```

The runtime-closure diff `main` → `dev` is exactly `+ bats-with-libraries`, `+ parallel`, `+ perl` (plus unrelated hash moves of `vig-utils` / the python env). This silently reverses the perl eviction from #1108, whose CVE exception batch was retired on the strength of perl being gone.

**Upstream fix status:** perl 5.42.3 (fixes all three) is on nixpkgs `master`/`nixos-unstable` since 2026-08-18, but `nixos-26.05` (our pin) still carries 5.42.0 with only a `CVE-2026-8376.patch`; no backport PR found. So a pin advance will not clear this.

## Fix

Swap GNU parallel for `rush` (shenwei356/rush), which `bats-exec-suite` supports natively via `BATS_PARALLEL_BINARY_NAME`. At the pin, `rush-parallel` 0.9.0 is a Go binary with a 47 MiB closure (parallel: 121 MiB) and no perl. Verified `bats -j` runs the suite correctly on it. The fix PR adds a negative image test pinning perl absent from the closure so #1108's eviction cannot regress unnoticed again. No `.vulnixignore` entry is needed: perl leaves the closure.

Per the issue template this closes once a later scheduled run passes the gate on `dev`.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 05:20 PM_

Closing: the fix (#1711, merged to `dev` at 464aa887) is scanned green. Manually dispatched run https://github.com/vig-os/devkit/actions/runs/36165864790 passed the vulnix gate on **both** legs (`dev` and `main`) — perl 5.42.0 is out of the `dev` image closure; no `.vulnixignore` entry was needed.

