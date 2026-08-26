---
type: issue
state: closed
created: 2026-08-26T11:45:11Z
updated: 2026-08-26T13:06:02Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1565
comments: 1
labels: bug, priority:high, area:ci, effort:medium, semver:patch, security
assignees: none
milestone: 1.11.1
projects: none
parent: none
children: none
synced: 2026-08-26T13:51:55.958Z
---

# [Issue 1565]: [[BUG] The pinned nixpkgs rev has no automated advance — the primary CVE-remediation lever is manual](https://github.com/vig-os/devkit/issues/1565)

### Description

`docs/CONTAINER_SECURITY.md` names advancing the pinned `nixpkgs` rev as the
**primary CVE-remediation lever**, and states that Renovate keeps it current
automatically (lines 32–38):

> Renovate keeps the pin current through two mechanisms in `renovate.json`:
> - The **`nix` manager** detects flake inputs and proposes pinned-input updates.
> - **`lockFileMaintenance`** (enabled, scheduled weekly) refreshes the locked
>   revisions of all inputs (notably `nixpkgs`) so upstream security fixes land
>   through the normal PR/CI gate rather than a manual `nix flake update`.

Neither mechanism is actually moving the pin. **Renovate has never opened a
`flake.lock` PR.** The pinned `nixpkgs` node has advanced exactly three times in
the repo's life, each time by hand (#1273, #1327/#1328).

This is not a cosmetic docs drift. The entire Wednesday expiry-grid convention
(#1337) is *derived* from step 1 of a cadence that does not happen — see the
"Expiry dates land on a Wednesday" section, which opens:

> 1. Renovate opens the `nixpkgs`/`flake.lock` bump — the primary remediation
>    lever — in its Monday window

### Evidence

**1. Renovate detects zero flake inputs.** The Dependency Dashboard (#529),
"Detected Dependencies → `flake.nix`", lists exactly one entry:

```
- `pip-licenses 5.5.5`
```

That is the `custom.regex` manager tracking a wheel URL. The `nix` manager is
enabled (`renovate.json:6`) and has a `packageRules` entry
(`renovate.json:23–25`, "Nix flake.lock — bump flake inputs through the normal
PR/CI gate"), but it has surfaced no flake input — not `nixpkgs`, not
`nixpkgs-unstable`, not any of the other nine.

**2. Weekly `lockFileMaintenance` is pip-only.** It is enabled and scheduled
(`assets/workspace/.github/renovate-default.json:8–12`, "before 9am on monday").
The last three PRs it produced each changed exactly one file:

| PR | merged | files changed |
|---|---|---|
| [#1527](https://github.com/vig-os/devkit/pull/1527) | 2026-08-17 | `uv.lock` |
| [#1556](https://github.com/vig-os/devkit/pull/1556) | 2026-08-20 | `uv.lock` |
| [#1560](https://github.com/vig-os/devkit/pull/1560) | 2026-08-24 | `uv.lock` |

The one branch currently in "Awaiting Schedule" on the dashboard is the same:
`build(pip): lock file maintenance`.

**3. The pin is 22 days stale.** `flake.lock`'s `nixpkgs` node is still
`531670d871c0`, set by `f4eeac2f` ("build(nix): advance nixpkgs pin to current
nixos-26.05", 2026-08-04, hand-driven under #1328).

**4. The automation that *does* run is for the other input.** Every `flake.lock`
commit since 2026-08-04 is `chore(nix): bump nixpkgs-unstable (fast-movers
refresh)` from `update-nixpkgs-unstable.yml`, which runs literally
`nix flake update nixpkgs-unstable` — one named input. The most recent
([#1561](https://github.com/vig-os/devkit/pull/1561), 2026-08-24) is a
three-line diff wholly inside the `"nixpkgs-unstable"` node:

```diff
     "nixpkgs-unstable": {
       "locked": {
-        "rev": "8be7bd0c83f12e2e3bbba07c9044d6fed9e66f7f",
+        "rev": "a831408e6378bc02ebf8cc09b52c96ca86f6bab4",
```

That input reaches the closure through `mkFastMoverOverlay`, which substitutes
only `fastMovers = [ "uv" "gh" "claude-code" ]` (`flake.nix:97`). **No package in
any exception register is a fast-mover** — podman, glibc, libssh2, unbound, fzf,
zlib, sqlite and libmicrohttpd all resolve from the pinned stable node. So the
weekly automation that works covers three packages, and the input carrying
essentially the whole CVE surface has none.

### Expected Behavior

The pinned `nixpkgs` rev advances on a weekly cadence through the normal PR/CI
gate, without a human remembering to run `nix flake update nixpkgs`, so that the
Wednesday grid's step 1 is real and each register review has a fresh findings
delta to reconcile against.

### Actual Behavior

The pin moves only when someone notices it has gone stale and advances it by
hand. Between those, every expiring block is re-reviewed against an **unchanged
closure**, so the only available outcome is a date bump.

That is visible in the register itself. Three consecutive renewals record it
almost verbatim:

- #1481 (glibc): *"the 'advance the rev' lever has nowhere to land"*
- #1547 (fzf): *"the rev-advance lever still has nowhere to land"*
- #1553: re-dated seven blocks, *"a re-date is a scheduling adjustment ONLY — no
  risk assessment below was re-opened, re-verified or changed by it"*

And it is why #1563 / #1564 arrived: the podman block's own note asks to
*"re-check weekly"* for NixOS/nixpkgs#536367, which can only be observed by
advancing the pin.

### Possible Solution

Two candidates; the investigation is part of the work.

1. **Fix the `nix` manager.** Establish why Renovate detects no flake inputs
   (hosted-app `nix` binary availability for lock maintenance is one hypothesis —
   unverified). If it can be made to work, this is the documented design and
   needs no new moving parts.
2. **Mirror `update-nixpkgs-unstable.yml` for the pinned input.** A proven
   pattern in this repo, running `nix flake update nixpkgs` on a schedule that
   lands the PR in the Monday window the grid assumes. Costs a second scheduled
   workflow; wholly under our control.

Either way, `docs/CONTAINER_SECURITY.md` §1 and the "Expiry dates land on a
Wednesday" derivation must be corrected to describe the mechanism that actually
runs. If option 2 wins, the doc's Renovate framing is replaced outright.

### Notes

- **Same milestone as the register work, separate PR.** 1.11.1 clears
  #1563/#1564 against the 2026-09-02 deadline; this closes the hole that keeps
  regenerating them. Keeping them in distinct PRs preserves the minimal diff and
  keeps the deadline-bound fix independently mergeable — same split as
  #1547 / #1548.
- The pin advance itself is a separate act with its own review (a full closure
  rebuild + findings delta). This issue is only about *proposing* it on a
  cadence — the PR/CI gate and the register reconciliation stay exactly as they
  are.
- Related: #638 (the original "Renovate `nix` manager + lockFileMaintenance"
  remediation design), #817 (the unstable fast-movers workflow), #1337 (the
  expiry grid whose step 1 this restores).

---

# [Comment #1]() by [c-vigo]()

_Posted on August 26, 2026 at 01:06 PM_

Resolved by #1566 (merged to dev): update-nixpkgs.yml advances the pinned rev Mondays 04:30 UTC + workflow_dispatch; docs corrected. Note: the workflow becomes dispatchable/schedulable once it reaches main (default branch) with the 1.11.1 promote — first cron 2026-09-07.

