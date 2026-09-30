---
type: issue
state: open
created: 2026-09-29T13:07:39Z
updated: 2026-09-29T15:28:53Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1766
comments: 1
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-30T08:17:45.778Z
---

# [Issue 1766]: [[FEATURE] AX budget for new-repo setup: eval-gated ceiling on tool calls, tokens and time](https://github.com/vig-os/devkit/issues/1766)

### Description

Set a measured **agent-experience (AX) budget** for "set up a new repo with devkit" and gate it in CI. An agent-driven first setup should take a handful of tool calls and a couple of minutes. Today it takes tens of calls and a real context bill, spent mostly on discovery and workarounds rather than on the setup itself.

### Problem Statement

Measured on a real first setup (vig-os/revkit, devkit 1.17.0, `--mode direnv --workflow gitflow`, modules `node` + `guardrails`, 2026-09-29, Claude Code, taken from the session transcript):

| Metric | Value |
|---|---|
| Wall clock | ~27 min (includes three user follow-up asks, ~⅓ of the calls) |
| Tool calls | 59 (55 Bash), 4 errored |
| Model turns | 137 |
| Output tokens | ~99k |
| Tool output pulled into context | ~157 KB (≈40k tokens), re-read every turn → ~15M cache-read tokens |

Where the setup share went (approximate call counts):

| Phase | Calls | Avoidable by |
|---|---|---|
| Learning the option surface: README, `docs/NIX.md`, `docs/SOLO_ADOPTION.md`, `docs/MIGRATION.md` (manifest table, feature groups), `nix/modules/*`, `init-workspace.sh` | ~12 | a machine-readable option manifest + `/devkit:init` (#1765) |
| Installer detour: GHCR image **403** for direnv mode → inspect cached image (1.4.1, stale) → extract the tag's `assets/` → run `init-workspace.sh` on the host via `TEMPLATE_DIR`/`VERSION_FILE`/`WORKSPACE_DIR`, and redo `install.sh`'s git bootstrap by hand | ~9 | a container-free install path for direnv/bare (#1765 item 1) |
| Host/tooling traps: flakes disabled on the host; `prek install` clobbering `.githooks/pre-commit` and cleaning up after it | ~5 | preflight + a one-line "hooks are already wired, never `prek install`" (#1765 items 2–3) |
| Hand edits the scaffold could render: pin `vigos.url` to `DEVKIT_VERSION`, mirror `DEVKIT_MODULES` into `modules`, add `bun` | ~3 | scaffold renders from `.vig-os` (#1765 items 4–5) |
| Guardrails: discover that no hook runs the gates, find the gate CLI contract, wire six flake hooks, probe with a bad file | ~5 | module-contributed hook entries (#1765 item 6) |
| Post-push: repo labels from `label-taxonomy.toml` (no recipe in direnv mode: `.devcontainer/justfile.gh` is pruned); `pull_request` CI never triggered on the first PR (dispatch works, close/reopen doesn't; root cause unknown) | ~7 | a `just labels-sync`-style recipe available in every mode; a post-setup `/devkit:status` check that CI fires |

**The ideal path** is `/devkit:init`: one question round, one apply, one verify. That's about 5 tool calls, under 3 minutes and under ~20k tokens of tool output.

### Proposed Solution

1. **An AX eval with ceilings.** A headless agent run (`claude -p` with the plugin loaded, or `claude plugin eval`) in CI: *"set up an empty repo with devkit, answers: <fixture>"*. It asserts that the resulting tree matches a golden scaffold, `prek run --all-files` is green, and the run stays under budget. Starting budget: **≤ 10 tool calls, 0 tool errors, ≤ 30k tokens of tool output, ≤ 5 min**. Record the numbers per release so regressions are visible (an AX perf-record, same idea as guardrails `perf-record`).
2. **Make discovery cheap.** Ship one machine-readable option manifest (keys, flags, modules + options, feature groups, defaults, one-line consequences) generated from the SSoTs. The skill, the docs and the coverage gate of #1765 all read it. An agent should never need to read `init-workspace.sh` to learn an option.
3. **Kill the detours** listed in the table (tracked in #1765 items 1–6, plus the labels recipe and the first-PR CI check).
4. **Output hygiene for agents.** Installer/scaffold output in a `--quiet`/`--json` mode (the rsync file list alone is a few hundred lines of context). `just doctor --json` covering flakes, gh scopes, image reachability and hooksPath in one call.

### Alternatives Considered

- **Rely on the plugin skill alone.** A skill without a measured budget regresses silently as devkit grows. The eval is what keeps it honest.
- **Token budgets in docs only.** Not enforced, so not real.

### Additional Context

- Parent/companion: #1765 (guided setup, coverage gate, discoverability).
- Session evidence: vig-os/revkit initial scaffold commit on `main`; ledger vig-os/revkit#1.

### Impact

Every new consumer, whether set up by an agent or a person, gets a setup cost that is measured and bounded. The AX eval also becomes the regression test for the plugin.

### Changelog Category

Added

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 03:27 PM_

Another data point for the AX budget: on the fresh vig-os/revkit, **no event-triggered workflow ever ran** (push or pull_request) until the repo's Actions was reset (off → on via `PUT /repos/{o}/{r}/actions/permissions`). That took about 10 tool calls of debugging, plus a temporary `admin:org` grant to rule out the org policy.

Right after that, **Dependency Review failed** on the first PR because the org creates repos with the dependency graph off. MIGRATION.md documents `gh api -X PUT repos/<o>/<r>/vulnerability-alerts`, but it is *"run by no scaffold script"*.

Suggestion: the setup flow's post-push verification (`/devkit:status` / `/devkit:init`) should:
- assert the first push or PR created a run within about 60 s, naming the Actions reset as the remedy (vig-os/org-config#311);
- run the dependency-graph PUT for public repos, instead of leaving it to be found from a red first PR.

