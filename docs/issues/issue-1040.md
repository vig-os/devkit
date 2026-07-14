---
type: issue
state: open
created: 2026-07-14T08:34:10Z
updated: 2026-07-14T16:39:31Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1040
comments: 2
labels: feature, priority:high, area:ci, area:workspace, effort:large, semver:minor
assignees: c-vigo
milestone: Backlog
projects: none
parent: none
children: 1038, 1039
synced: 2026-07-14T20:06:30.309Z
---

# [Issue 1040]: [[EPIC] Onboard exoma-ch/cad2gdml as first external devkit consumer (direnv mode)](https://github.com/vig-os/devkit/issues/1040)

### Description

Onboard [`exoma-ch/cad2gdml`](https://github.com/exoma-ch/cad2gdml) as the **first devkit consumer outside the `vig-os` org**. The repo is a Python CLI converting CAD STEP files to GDML for Geant4 (morePET PET scanner): private, GPL-3.0, single maintainer, ~2 800 LOC, 132 pytest tests, active. It currently has **no** packaging, lockfile, linting, pre-commit, justfile, or devcontainer — a clean slate for the devkit — but one heavy dependency: **FreeCAD**, today injected via an AppImage extract with hardcoded paths inside a hand-built Podman image (CPython 3.11 ABI).

Decisions already taken:

- **Delivery mode: `direnv`.**
- **FreeCAD comes from nixpkgs via `extraPackages`** (1.1.1 in the current pin) — per the `docs/rfcs/ADR-capability-modules.md` escape hatch. **No `freecad` capability module**; too niche until a second consumer asks.

Being the first external onboarding, this epic doubles as the shakedown for a reusable onboarding runbook (org pre-flight, secrets/apps, ruleset standards, workflow registration) that later consumers (EXOMA/EXOPET repos) will follow.

### Readiness audit (2026-07-14)

Verified:

- `vig-os/devkit` is **public** → the consumer flake input, the `install.sh` one-liner, and the reusable actions are all reachable from a private exoma-ch repo with no auth plumbing.
- Pinned nixpkgs ships `freecad` **1.1.1** and `python3Packages.pythonocc-core` 7.9.0.
- exoma-ch org already has the `commit-action-bot` and `vig-os-release-app` GitHub Apps installed (**all repos**) and the `COMMIT_APP_*` / `RELEASE_APP_*` org secrets.
- devkit rulesets exist as the standard to replicate: *Main protection*, *Dev protection*, *Release protection*, *Signed commits*.

Gaps found (blocking or noteworthy):

- **ABI blocker**: `mkProjectShell` pins `pkgs.python314` with no override, while nixpkgs FreeCAD is built against Python 3.13 → `import FreeCAD` cannot work today. → #1038
- Scaffold `codeql.yml`/`scorecard.yml` have no private-repo guards → would land permanently red on cad2gdml (Free plan, no GHAS; Scorecard is public-only). → #1039
- ~~No Renovate app installed on exoma-ch~~ **Correction (2026-07-14):** Renovate **is** installed on exoma-ch (`repository_selection: all`) — the initial audit truncated the installation list.
- ~~exoma-ch lacks the `APP_SYNC_ISSUES_*` secrets~~ **Correction (2026-07-14):** the *scaffold* `sync-issues.yml` uses `COMMIT_APP_*` (present); `APP_SYNC_ISSUES_*` is devkit-own. `GHCR_PULL_TOKEN` falls back to `github.token`; no `CACHIX_*` reference exists in the scaffold. **No missing secrets.**
- Known consumer-affecting bug in a scaffolded workflow: #1034 (`sync-main-to-dev`).
- Rulesets are **not enforceable on private repos under GitHub Free** — see Phase 1.

### Phase 0 — devkit prerequisites

- [x] #1038 — `mkProjectShell` Python interpreter override (FreeCAD ABI alignment)
- [x] #1039 — visibility-aware `codeql.yml`/`scorecard.yml` in the scaffold
- [x] Resolve or confirm-unaffected #1034 for the scaffolded `sync-main-to-dev.yml` copy
- [x] Spike in a scratch consumer: `mkProjectShell { python = pkgs.python313; extraPackages = [ pkgs.freecad ]; }` (+ whatever `PYTHONPATH`/env the FreeCAD derivation needs) until `python3 -c "import FreeCAD"` passes headless; record the exact snippet for the onboarding doc *(done — recipe + Draft caveat in the Phase 1 execution comment below)*

### Phase 1 — exoma-ch / repo pre-flight (GitHub plumbing)

- [x] ~~Install the Renovate (Mend) app on exoma-ch~~ already installed (`repository_selection: all`)
- [x] Verify org-secret repository access includes `cad2gdml` (`COMMIT_APP_*`, `RELEASE_APP_*` — all `visibility=all`)
- [x] Enumerate remaining secrets/vars — **none missing** (see corrected audit above)
- [x] Check exoma-ch Actions policy (`enabled_repositories: all`, `allowed_actions: all`)
- [x] Branch model: `dev` created from `main`; default branch stays `main`; merge policy mirrored from devkit (merge-commit only, delete-branch-on-merge, web commit signoff)
- [x] **Rulesets**: decision = **repo made PUBLIC** (2026-07-14, after a clean gitleaks scan over all 91 commits); devkit's four rulesets imported and **active** (Main/Dev/Release protection + Signed commits, ids 18937429–33), required status check adapted `Test Summary` → `CI Summary` (the scaffold `ci.yml` summary job name)
- [x] Provision labels from `.github/label-taxonomy.toml` (`setup-labels` applied; pruning org-default labels left as optional)
- [ ] `CODEOWNERS` for the scaffolded copy (maintainer + reviewer) — lands with the Phase 2 scaffold
- [x] Milestones (`Backlog` #1 created)

### Phase 2 — scaffold deployment

- [ ] Run `install.sh --mode direnv` on a feature branch; review the diff carefully against existing files (three READMEs, `COPYING.txt` — the scaffold ships `LICENSE`; **must not clobber the GPL licensing**), `.gitignore` merge
- [ ] Author the consumer `flake.nix`: `mkProjectShell` with the Python override (#1038), `extraPackages = [ pkgs.freecad ]`, opt-in generated hooks; `.envrc`; `.vig-os` manifest (`DEVKIT_MODE=direnv`, version, identity)
- [ ] **Land the scaffold on the default branch early** — workflows with `schedule` / `workflow_dispatch` / issue-event triggers only register once they exist on the default branch. Merge the scaffold PR before the phases that depend on those workflows; verify the Actions tab lists all of them
- [ ] Maintainer environment onboarding: Nix + direnv install, `direnv allow`, pointer to `docs/NIX.md`; plus a short commit-standard note — current history uses `area: summary`, hooks will enforce `type(scope): summary` + `Refs: #<issue>` from day one

### Phase 3 — repo migration (implementation issues live in exoma-ch/cad2gdml)

- [ ] Packaging: `pyproject.toml` + `uv.lock`; make `GUIMeshLibs`/CLI an installable package; remove `sys.path` injection and the hardcoded `/usr/local/bin/squashfs-root/...` FreeCAD paths (env-var seam; nixpkgs provides the path); pin `requires-python` to the FreeCAD ABI (3.13)
- [ ] Lint/format: one-time ruff format+lint commit on the existing code; pre-commit suite green
- [ ] CI migration: replace `tests.yml` + `build-container.yml` with the mode-aware scaffold `ci.yml`; keep the existing two-tier test split (headless unit tests with mocked FreeCAD / integration tests needing real FreeCAD, now provided by the nix shell on the runner)
- [ ] **Regenerate and physically validate the golden GDML/HDF5 fixtures under FreeCAD 1.1.1** (currently generated with 1.0.1 — tessellation/precision output may shift; this is a scientific-validation step, not a mechanical one)
- [ ] Hygiene: untrack committed `__pycache__/*.pyc`; remove personal-path scripts (`build/Podman/start_container.sh` hardcodes a home directory); decide the fate of `build/Podman/` (the slim runtime image could become a `nix2container` follow-up or stay as-is for now)
- [ ] `CHANGELOG.md` bootstrap (Keep a Changelog, `## Unreleased`); preserve the existing `v1.0` tag; smoke the release pipeline (`prepare-release` dry-run) once wired

### Phase 4 — validation & exit criteria

- [ ] Fresh clone → `direnv allow` → `just test-pytest` green **including** the FreeCAD integration tier
- [ ] CI green on PR and on the default branch; scheduled workflows registered and green (or intentionally skipped per #1039)
- [ ] End-to-end smoke: `Crystal.step` and `ring6x1.step` conversions reproduce the regenerated goldens; crystal-lookup HDF5 extraction works
- [ ] Renovate dashboard issue opens; the renovate-changelog automation works on a real Renovate PR
- [ ] Distill this rollout into a general external-consumer onboarding doc (new `docs/ONBOARDING.md` or a MIGRATION.md section): org pre-flight checklist, secrets/apps matrix, ruleset export, default-branch workflow registration

### Out of scope

- Replacing FreeCAD with pythonocc/OCC (upstream exoma-ch/cad2gdml#2) — worthwhile, but a separate future effort in that repo
- A `freecad`/`cad` capability module — promote from `extraPackages` only when a second consumer asks (ADR policy)
- cad2gdml feature work (config-file CLI exoma-ch/cad2gdml#22, image baking exoma-ch/cad2gdml#11)

### Additional context

- Consumer repo state: 89 commits, one maintainer, good issue→branch→PR discipline, pytest culture already in place — the social cost of adoption is low; the technical crux is FreeCAD packaging and the Python-ABI pin.
- Precedent: the vig-os-internal rollout pilot (#988, `commit-action`) validated mode-aware CI; this epic validates the cross-org path.


---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 04:30 PM_

## Phase 0 + Phase 1 execution log (2026-07-14)

### Phase 0 — devkit prerequisites: DONE

#1038, #1039, #1034 all merged/closed; release train **1.2.0** in flight (release PR #1068). The FreeCAD spike ran against `github:vig-os/devkit/dev`:

**Working consumer recipe** (proven on x86_64-linux, headless, sandboxed shell):

```nix
devShells.default = vigos.lib.mkProjectShell {
  inherit pkgs;
  python = pkgs.python313;          # match nixpkgs FreeCAD's CPython ABI (#1038)
  extraPackages = [ pkgs.freecad ]; # FreeCAD 1.1.1
  shellHook = ''
    export PYTHONPATH="${pkgs.freecad}/lib:''${PYTHONPATH:-}"
  '';
};
```

Result: `import FreeCAD, Part, Import, FreeCADGui` → **all OK** (FreeCAD 1.1.1, Python 3.13.13). Set `QT_QPA_PLATFORM=offscreen` in CI for safety.

**Caveat — `import Draft` segfaults** (SIGSEGV in `libpyside6` `SignalManager::retrieveMetaObject`, swallowed by FreeCAD's crash handler as a silent `exit(1)`). Reproduced with FreeCAD's own `FreeCADCmd -c "import Draft"` → **upstream nixpkgs/FreeCAD 1.1.1 + PySide 6.11 issue, not a devkit or recipe defect**. Materially irrelevant here: cad2gdml imports `Draft` but **never calls any `Draft.` API** (dead import inherited from GUIMesh3) → Phase 3 drops the import. Worth an upstream nixpkgs report at some point.

### Phase 1 — pre-flight: DONE (checkboxes ticked in the body; two audit corrections struck through)

| Item | Result |
|---|---|
| Pre-publication scan | gitleaks over all 91 commits (~180 MB): **no leaks** |
| Visibility | `exoma-ch/cad2gdml` → **public** |
| `dev` branch | created from `main` (`refs/heads/dev`) |
| Rulesets | 4 imported + **active** (ids 18937429–33), Main/Dev/Release protection + Signed commits; required check adapted `Test Summary` → `CI Summary` (scaffold job name) |
| Merge policy | merge-commit only, delete-branch-on-merge, web commit signoff — mirrors devkit |
| Labels | taxonomy applied via `setup-labels` |
| Milestone | `Backlog` (#1) |
| Apps | commit-action-bot, vig-os-release-app, **Renovate** — all installed org-wide (audit correction: Renovate was already there) |
| Secrets | `COMMIT_APP_*`/`RELEASE_APP_*` org secrets `visibility=all`; **nothing missing** — scaffold `sync-issues.yml` uses `COMMIT_APP_*`, `GHCR_PULL_TOKEN` falls back to `github.token`, no `CACHIX_*` in the scaffold |
| Actions policy | org: all repos enabled, all actions allowed |
| CodeQL default setup | already `not-configured` → matches the advanced-config-authoritative rollout standard, nothing to disable |

### Remaining before Phase 2

1. **Promote devkit 1.2.0** (release PR #1068 in flight) — Phase 2 scaffolds with `install.sh --version 1.2.0`.
2. **Maintainer onboarding (blocking for her, not for scaffolding):** the *Signed commits* ruleset is now active on **all branches** — commit signing must be configured before any push. Plus: Nix + direnv install, commit-standard heads-up (`type(scope): summary` + `Refs: #<issue>` enforced by hooks), and confirmation she's aware the repo is now public.
3. `CODEOWNERS` — arrives with the scaffold PR.


---

# [Comment #2]() by [c-vigo]()

_Posted on July 14, 2026 at 04:39 PM_

Consumer-side migration issue filed: exoma-ch/cad2gdml#23 — Phases 2/3 (scaffold + repo migration) and the maintainer-onboarding checklist are tracked there; commits/PRs in that repo use it as their `Refs:` target. Labels on cad2gdml pruned to the taxonomy.

