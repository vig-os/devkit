---
type: issue
state: open
created: 2026-11-17T16:17:36Z
updated: 2026-11-17T16:17:36Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2079
comments: 0
labels: feature, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-17T20:22:44.787Z
---

# [Issue 2079]: [Consumer configuration walkthrough: an agent-guided 'devkit configure' that inventories, explains and validates every knob a consumer deploys](https://github.com/vig-os/devkit/issues/2079)

## Motivation
Owner request (2026-11-17, from the stepv architect session): a devkit deployment has many knobs that live in different places. Nobody holds them all in context, so failures look like devkit bugs when they're really configuration or environment problems. Concrete case:
- stepv had `vars.CACHIX_CACHE=gerchowl` and `secrets.CACHIX_AUTH_TOKEN` set since 2026-10-13, which nobody remembered. Devkit 1.19.0 turned that into a new `cachix-action` step.
- That step failed on runners whose local substituter is down (gerchowl/g-fleet#1500). The first triage blamed devkit, and that was wrong (#2077).
- The release hang (#2010) has the same environmental root.

## Proposal
A **configuration walkthrough** that an agent runs with dedicated context, offered as a devkit-shipped skill/command (e.g. `just devkit-configure`, plus an agent skill that drives it):

1. **Inventory:** read every input devkit consumes:
   - `.vig-os` keys;
   - `justfile.project`;
   - flake inputs and pins;
   - repo and org Actions **variables and secrets** by name (`CACHIX_CACHE`, `CACHIX_AUTH_TOKEN`, `CI_RUNNER_*`, `GHCR_PULL_TOKEN`, …);
   - the runner labels in use;
   - the branch ruleset (required approvals, required checks);
   - the release model (gitflow or trunk, tag prefix, floating tags);
   - the commit and `Refs:` policy.
2. **Explain:** for each knob, what it turns on in the managed workflows, its current value and where it's set (repo, org or default), and which managed steps depend on it.
3. **Validate live:** for example, is the cachix cache reachable, do the runners with those labels exist and are they healthy, can a toolchain setup finish within the job timeout (a probe job), is the token scope sufficient for release, and does the ruleset let promote work for a solo owner.
4. **Decide with the owner:** present the choices as a short questionnaire with a recommended default, apply them (`gh variable set/delete`, `.vig-os` edits), and record the decisions in a committed `docs/devkit-config.md`, so the next upgrade's diff can say "this upgrade newly uses CACHIX_CACHE, which you set to gerchowl".
5. **Upgrade-aware:** `install.sh --force` / the devkit-upgrade PR body lists the **newly consumed** knobs and their current values in the consumer, so a step like 1.19.0's cachix step is never a surprise.

## Acceptance
- One command or skill produces the inventory, the validation report and the decision record for a consumer.
- Every managed workflow input is documented in one schema, and the walkthrough reads from that schema, so it can't go stale.
- Upgrade PRs name the newly consumed knobs.

Refs: #2010, #2077, gerchowl/g-fleet#1500
