---
type: issue
state: closed
created: 2026-08-12T05:15:40Z
updated: 2026-08-12T07:56:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1434
comments: 1
labels: bug, priority:medium, area:workspace, effort:medium, semver:minor
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:42.215Z
---

# [Issue 1434]: [[BUG] flake-generated consumer hooks omit the commit-msg-stage and agent-identity hooks — local enforcement is a no-op in direnv consumers](https://github.com/vig-os/devkit/issues/1434)

### Description

A direnv consumer that opted into flake-generated hooks (#1167 default) has **no local commit-message or agent-identity enforcement at all**. The three #163/#1019/#1031 hooks — `validate-commit-msg`, `prepare-commit-msg-strip-trailers`, `check-agent-identity` — carry no `consumer` fragment in `nix/hooks.nix` (they are `scaffold = true` only), so the generated `.pre-commit-config.yaml` omits them and the scaffolded `.githooks/commit-msg` shim's `prek run --hook-stage commit-msg` exits 0 with nothing to run.

### Steps to Reproduce

In a direnv consumer on flake-generated hooks (e.g. exo-pet/vault), inside the dev shell:

```
printf 'totally-invalid message with no type\n' > /tmp/msg
prek run --hook-stage commit-msg --commit-msg-filename /tmp/msg; echo $?
```

### Expected Behavior

The message is rejected (exit 1), as it is in a docker-mode consumer whose scaffolded YAML carries the commit-msg hooks — that was #1019's whole point ("every scaffolded repo shipped a COMMIT_MESSAGE_STANDARD.md it could not enforce").

### Actual Behavior

Exit 0, no output (reproduced 2026-08-11 in exo-pet/vault, devkit 1.7.0). The commit-msg stage is empty; `check-agent-identity` (pre-commit stage) is likewise absent from the generated config, so `git commit --author="Claude <…>"` passes locally. CI (`validate-commit-range`, `check-pr-agent-fingerprints`) is the only line of defense for these consumers.

### Additional Context

Found while spiking exo-pet/vault#54 / #1431. Root cause is structural: these hooks run `uv run <tool>` from the project venv, which the git-hooks.nix consumer surface couldn't express when #883 landed — but they could now ship as `language: system` fragments (vig-utils is on the dev-shell PATH via the flake), or the consumer render could append them verbatim from the portable definition. Whatever the fix, it must honor #1431's `DEVKIT_COMMIT_TYPES` and #1282's `DEVKIT_REFS_POLICY` on the flake surface (e.g. threaded like `workflow`/`branchTypes`, #1432).

### Impact

All direnv-mode consumers on generated hooks (vault, exo-fleet, org-config, …). Not a regression — pre-existing since the #883/#1167 opt-in — so no train blocker; CI still gates PRs.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 07:56 AM_

Fixed by #1439, merged to `dev` as 20e5660c.

The three hooks (`validate-commit-msg`, `prepare-commit-msg-strip-trailers`, `check-agent-identity`) now ship `consumer` fragments in `nix/hooks.nix` with Nix store-path entries, so the flake-generated `.pre-commit-config.yaml` carries them and the scaffolded `.githooks/commit-msg` shim has something to run.

Route: store-path entries rather than the portable `uv run <tool>` form. `uv run` resolves against the *consumer's* project venv, which has no `vig-utils` (many consumers have no `pyproject.toml` at all); every other tool-naming consumer fragment already resolves `${pkgs.<tool>}/bin/…`, so the hook version follows the devkit pin the consumer bumps with `nix flake update vigos`. git-hooks.nix does support `commit-msg`/`prepare-commit-msg` in its `stages` set — "stage-gated" was never the blocker, and the header comment's "not generatable" claim was simply stale. It has been corrected.

`pkgs.vig-utils` existed only via `overlays.default`, which would have made the generation surface fail eval on a plain `pkgs`; the package is now extracted to `nix/vig-utils.nix` (the `nix/pymarkdown.nix` precedent) and consumed by both the overlay and the hook fragments.

**Verification** — the reproduction from the issue description, against a real generated config:

| check | before | after |
|---|---|---|
| `prek run --hook-stage commit-msg` on `totally-invalid message…` | exit 0, no hooks | **exit 1** — `First line must match 'type(scope): short description'` |
| valid `fix(hooks): …` + `Refs:` | — | exit 0 |
| `check-agent-identity` with `GIT_AUTHOR_NAME=Claude` | absent | **exit 1** — `matches blocklisted AI agent identity: 'claude'` |
| `commitTypes=[feat,fix,chore,record] refsPolicy=optional` → `record(registry): …` no Refs | — | exit 0 |
| same config → `perf(x): …` | — | **exit 1** — `Allowed types: chore, feat, fix, record` |

**Knob composition** (the hard requirement here): `mkProjectShell` gains `commitTypes` / `refsPolicy`, and `assets/workspace/flake.nix` reads `DEVKIT_COMMIT_TYPES` / `DEVKIT_REFS_POLICY` from `.vig-os` behind a `builtins.functionArgs` probe (#1249 pattern). The flake path resolves identically to `render_commit_types` / `render_refs_policy` (`assets/init-workspace.sh`) and `resolve-toolchain`: same default 11-type list, same parse, same charset allowlist, `optional` mirroring the **resolved** list (#1431's composition, not a hardcoded stock copy), `required` using the `none` sentinel. Confirmed by direct render: `commitTypes=[feat,fix,chore,record] refsPolicy=optional` yields `--refs-optional-types feat,fix,chore,record`, matching `render_refs_policy`'s `RESOLVED_COMMIT_TYPES` branch.

**Invariants**: drift gate holds (neither `.pre-commit-config.yaml` appears in the diff at all — the argv refactor renders byte-identically); zero-hooks parity holds (identical `drvPath`); default render stability pinned by a new test asserting consumer argv == scaffold argv == the stock list.

**Adoption notes**, worth repeating in the 1.8.0 release notes:

- A consumer whose history contains non-conformant messages will start seeing local rejections on its next `nix flake update vigos`. That is the point of the fix, but it is a behavior change.
- Existing direnv consumers get the hooks with **stock defaults** until they hand-port the `.vig-os` reader into their scaffold-once `flake.nix` — the same one-time port as #1224/#1432, now documented in `docs/MIGRATION.md`. Relevant to exo-pet/vault#54: the port is needed for its custom commit types to be enforced *locally*, though CI enforces them from adoption.
- `check-agent-identity` now runs under a direnv consumer's `prek run --all-files` lint job, but returns 0 immediately when `CI`/`GITHUB_ACTIONS` is set, so consumer CI is unaffected.

Follow-up worth filing separately: `check-expirations`'s consumer fragment still uses `uv run check-expirations` — the same venv-resolution weakness this issue was about, and now the odd one out among the vig-utils consumer fragments.

Shipping in the 1.8.0 train.

