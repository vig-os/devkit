---
type: issue
state: open
created: 2026-06-23T06:53:52Z
updated: 2026-06-23T06:55:22Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/625
comments: 0
labels: priority:high
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:53.734Z
---

# [Issue 625]: [[MASTER] Migrate devcontainer to a Nix toolchain + Claude-native setup](https://github.com/vig-os/devcontainer/issues/625)



## Context

`vigOS/devcontainer` publishes the shared image `ghcr.io/vig-os/devcontainer` (Debian
`python:3.14-slim-bookworm`) consumed across EXOMA/EXOPET/vigOS. Today the toolchain is
defined **twice** (curl-installed in `Containerfile` + a drifting `flake.nix` dev-shell),
the CVE posture is Debian/apt + Trivy + a `.trivyignore` expiry register, and agent tooling
is **Cursor-based** (`.cursor/` = SSoT for rules/skills; `cursor-agent` CLI drives the
worktree pipelines; `.claude/commands/*.md` are wrappers into `.cursor/skills/`).

This epic eliminates toolchain duplication by making `flake.nix` the SSoT, delivers it as
both a `nix develop`/direnv shell and a Nix-built (`buildLayeredImage`) devcontainer image,
reworks the CVE/audit posture for a non-apt image, and migrates agent tooling from Cursor
to Claude-native. The pattern then rolls out across repos. `nix2container` is reserved for
downstream production images.

## Confirmed decisions

- Flake = SSoT; **Nix builds the devcontainer image**.
- **Image built with `dockerTools.buildLayeredImage`** (not a Dockerfile `FROM`), with the
  Nix package manager included as a closure layer — minimal, *with* Nix live inside, **not**
  the NixOS distro. This is what makes the build bit-reproducible (identical-digest AC below).
  Same outcome as the original "base = `nixos/nix`" intent (nix CLI live in the container),
  assembled by Nix rather than pulled as a non-reproducible Docker base. Full NixOS distro = no.
- **`nix2container` reserved** for **production/runtime images in other packages**.
- **Evaluator (Lix vs CppNix) = swappable config, off the critical path.** Same language /
  flakes / store / cache, so the whole stack is identical under either. Only touches the CI
  installer (#631) and the in-container evaluator (#634: include CppNix or `pkgs.lix` in the
  image closure). Reversible without flake changes.
- CVE/audit rework (vulnix + SBOM) is **in-scope**.
- **Drop all Cursor references → Claude-native** (keep `cursor` in the commit-msg agent
  *blocklist* — that's the "never name an AI" control, not a dependency).
- **Install picker:** the `curl`-able install script lets the user choose
  **devcontainer / direnv / both** (#641).
- **Minimal flake only.** Ship a *minimal* downstream flake with placeholders +
  instructions; user expansions must survive dev-env updates (scaffold-once, never-overwrite
  — mirrors `justfile.base→project→local`). Modular shells (C++/Geant4/Data-Analysis) =
  **future, out of scope**, mentioned only.

## Scope

**In:**
- Tracking only — links the sub-issues below.
- Holds the confirmed decisions, dependency graph, and the #639 go/no-go gate.

**Out:**
- Modular language shells (C++ / Geant4 / Data-Analysis) — future work.

## Sub-issues

- **Track C — Cursor → Claude-native:** #626, #627, #628, #629, #630
- **Track 1 — Flake as SSoT:** #631, #632, #633
- **Track 2 — Nix-built image:** #634, #635, #636
- **Track 3 — CVE/audit rework:** #637, #638
- **Track 4 — Cutover & rollout:** #639, #640, #641, #642

## Dependency graph & parallelism

```
   start in parallel:  #626   #627   #631   #635
   #627 ─► #628 ─► #630            #626 ─► #629
   #628 ──────────────► (precedes) #634
   #631 ─► #632
     │  └─► #633 ─────────────┐
     ├─► #638                 │
     └─► #634 ─► #636 ─┐      │
   #635 ─(parallel)──► ┘ gates #634-green
        #634 ─► #637 ─┐       │
                      ▼       ▼
                    #639 ─► #640 ─► #641 ─► #642
```

- **Critical path:** `#631 → #634 → #637 → #639 → #640 → #641 → #642`.
- **Hard gate:** #637 CVE gate (no unexcepted HIGH/CRITICAL) before the publish-cutover (#639).
- **Start in parallel:** #626, #627, #631, #635.
- **Conservative early-exit:** stopping after T1.x + #635 still delivers flake-as-dev-SSoT +
  direnv onboarding while keeping the Debian image; T4.x is the only irreversible-ish step.

## Acceptance criteria

- All sub-issues closed.
- Debian path decommissioned (#642).
- `grep -ri cursor` returns only CHANGELOG history + the intentional commit-msg blocklist.
- Reproducible rebuild from the same `flake.lock` yields an identical image digest.

## Global verification (end-to-end)

- **Dev-shell/direnv:** `nix develop -c bash -lc '<tool> --version'` per tool; clean clone +
  `direnv allow` → working shell (warm cache: seconds).
- **Image parity:** portable `just test-image` + `npx bats tests/bats/` green on **both**
  Debian and Nix images through T2–#639.
- **Multi-arch:** `docker buildx imagetools inspect …:<tag>` shows amd64+arm64; downstream
  digest-pin resolves unchanged.
- **CVE gate:** no unexcepted HIGH/CRITICAL vulnix finding on the Nix image; exception register
  expiry checks pass. Trivy-vs-vulnix overlap diff archived as supporting evidence (not a
  numeric parity requirement — different scan surfaces).
- **Claude-native:** worktree pipelines drive `claude`; commit-msg validation blocks both
  `cursor` and `claude`; `grep -ri cursor` → only CHANGELOG history + the intentional blocklist.
- **Install picker:** `--mode=devcontainer|direnv|both` each scaffolds exactly the right files.
- **Non-overwrite:** simulated dev-env update preserves user `extraPackages` in the downstream
  `flake.nix`.
- **Reproducibility:** rebuild from the same `flake.lock` on another host → identical image
  digest.

## Related existing issues

Scan of open repo issues (as of 2026-06-22) and how this epic relates to each.

| Issue | Relation | Verdict |
|-------|----------|---------|
| **#27** Adopt Nix/devenv for reproducible, auditable dependency management | This epic **is** the decided execution of #27 (same goal; #27 proposed devenv-or-flake + hybrid start, we go full flake-SSoT + `nixos/nix` image). Its IEC 62304 / SBOM / air-gapped framing is preserved in #637. | **Superseded** — close #27, pointing here, after this epic is filed. |
| **#255** Document Nix flake as alternative dev setup | Covered by **#633** (note: targets `docs/templates/CONTRIBUTE.md.j2` + experimental-features guidance). | **Superseded by #633** — close when #633 lands. |
| **#545** Bake agent-CLI toolkit + Claude Code into image | Install *mechanism* (apt/curl) is replaced by Nix `devTools` (#631/#634); its *requirements* (tool list, `claude` baked, `IS_SANDBOX=1`, `cc`/`cld` aliases) must be **absorbed** into #631 + #634 + #627/#628. | **Partially superseded** — re-scope to a requirements checklist consumed by #631/#634. |
| **#546** Slim Claude Code OAuth-token forwarding | Shares the "claude baked" assumption (#545); its `setup-claude.sh`/non-root-user removal touches #629-adjacent scripts. Mostly remote-devc auth, otherwise independent. | **Related** — cross-link; keep. |
| **#604** Consolidate Trivy scan categories / clean stale alerts | The "single authoritative scan + document SSoT" goal is exactly **#637**'s outcome; the orphaned-alert cleanup is worth doing regardless. | **Partially superseded by #637.** |
| **#602 / #521** Nightly scan HIGH/CRITICAL in `:latest` | Tied to the Debian/apt image; the apt-CVE surface changes under the Nix image (#637) and these gates are re-pointed at vulnix. #521 (Apr) already stale vs #602 (Jun). | **Will be superseded by #637 + #642.** |
| **#144** generate-docs hook misses skill dirs | `docs/generate.py` scans `.cursor/skills/*/SKILL.md`; **#626** moves skills to `.claude/skills/`, changing both the hook filter and the scan path. | **Changed/absorbed by #626.** |
| **#40** Migration to prek | Nix migration is the natural moment to choose `pre-commit` vs `prek` (both in nixpkgs). | **Decision point** — light ref from #634; not superseded. |
| **#162 / #178 / #157** worktree-skill features | Built on the `.cursor/skills/` + `cursor-agent` pipeline; **#626** moves the paths and **#627** swaps the CLI. | **Path/CLI changes** — coordinate, not superseded. |
| **#231 / #153** Cursor *editor* remote wrappers | **Scope resolved: VS Code only.** Cursor IDE support is dropped along with `cursor-agent`. | **Close #153; de-scope #231 to `code-remote` only** (see #629). |


