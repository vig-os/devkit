---
type: issue
state: closed
created: 2026-07-15T08:31:17Z
updated: 2026-07-15T14:37:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1103
comments: 4
labels: refactor, priority:medium, area:image, effort:large, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: 1104, 1105, 1106, 1107, 1108
synced: 2026-07-15T20:04:06.107Z
---

# [Issue 1103]: [[EPIC] Slim the devcontainer image (~680 MiB, mode-neutral cuts)](https://github.com/vig-os/devkit/issues/1103)

### Description

The Nix-built devcontainer image ships at **~2.27 GB uncompressed** (735 MiB
compressed pull). Measured via `nix path-info -S` on `.#devkitImageEnv` — the
vulnix scan target whose runtime closure equals the image's package set
(`imageTools`): **2.14 GiB across 424 store paths**.

This epic recovers **~550 MiB uncompressed** through five cuts (revised 2026-07-15 from ~730 MiB — see the #1106 correction below): pure
de-duplication, retiring one dead feature (the sidecar / podman-in-podman
model), and evicting two redundant interpreter stacks. Expected result:
`podman images` shows **~1.7 GB** (from 2.27 GB); compressed pull drops
from ~735 MiB accordingly. The image **stays a self-contained, offline,
flake-free artifact** — the separate strategic question of whether image mode
should stop shipping user toolchains (node, neovim, lazygit, …) and become a
thin direnv substrate is **explicitly out of scope** — see the pinned comment.

### Contract note (semver)

Two cuts remove capabilities some consumer could theoretically have used:
in-container *isolated* container execution (nested podman runtime) and git's
perl/python porcelain (`send-email`, `svn`, `p4`, `gitk`). **These were never
part of the image contract**: the scaffold wires consumers for
Docker-out-of-Docker via the host socket
(`assets/workspace/.devcontainer/scripts/initialize.sh`), and the git workflow
is `gh`-driven. Their removal is therefore treated as **`semver:minor`**, with
this epic as the declaration of record.

### How the numbers were measured

- `nix build .#devkitImageEnv` (buildEnv whose runtime closure = `imageTools`).
- Ranked by **self NAR size** (`nix path-info -rS --json`), not closure size
  (which double-counts shared deps).
- Each cut's **marginal** saving = store paths that become unreferenced once
  that cut's top-level entries are dropped (reference-graph reachability), so
  the totals are real, not closure-sum inflation.

### Sub-issues

| # | Cut | Marginal saving | Notes |
|---|-----|-----------------|-------|
| 1 | Restrict `glibcLocales` to `en_US.UTF-8` | ~222 MiB | must rebind **both** the `imageTools` entry and the `LOCALE_ARCHIVE` Env reference (`flake.nix:1202`) — fixing only one ships *both* archives |
| 2 | Drop `bandit` from `imageTools` (stray CPython 3.13 stack) | ~74 MiB | hooks already run `uv run bandit` (venv); the baked copy is vestigial |
| 3 | Replace full `podman` runtime with a DooD-only client | **~67 MiB** (measured; was ~254 est.) | sidecar model retired; retained client binary (~54 MiB) + rpath-linked `systemd` account for the difference — strategic goal (criu gone) fully met |
| 4 | Evict the redundant second CPython 3.13 interpreter | ~127 MiB | `gitMinimal` + actionlint-without-pyflakes; **depends on #2 and #3** |
| 5 | Evict perl: rewrap `neovim` without `wl-clipboard` | ~55–60 MiB | **retires the perl 5.42 CVE exception batch** (`.vulnixignore`, #1097/#1098); **depends on #4's gitMinimal** |

Totals are marginal per cut with no double-count (~550 MiB combined; #1106 measured, others estimated pending merge).

### Why the sidecar retirement unlocks the podman cut

Everything the image does with podman is **Docker-out-of-Docker (DooD)**: the
`docker→podman` shim (`flake.nix:1043-1055`, honoring `DOCKER_HOST`), the test
harness (`tests/README.md:10`), and the consumer scaffold itself —
`initialize.sh` discovers the **host's** rootless podman socket and mounts it
as `/var/run/docker.sock`. Every `podman build/load/tag` in the justfiles runs
**host-side**. The full local runtime (`crun`, `criu`, `conmon`, `netavark`,
`passt`, `libkrun`, `aardvark-dns`, `fuse-overlayfs`, `runc`, `systemd`) is
only needed to *run isolated containers inside the container* — the retired
geant4-sidecar use case.

### The second CPython 3.13 has four anchors (all must fall)

`python3-3.13.13` (127 MiB) is dragged in — while the entire *chosen* toolchain
is 3.14 — by four independent consumers, traced with `nix why-depends`:

- `criu` (falls with sub-issue 3: podman → crun → criu)
- `bandit` → ddt/stevedore/gitpython/rich/pygments (falls with sub-issue 2)
- full `git-2.54.0` — git-p4 / python helpers (sub-issue 4: `gitMinimal`)
- `actionlint` → `pyflakes` (sub-issue 4: drop the optional wrap)

Similarly, **perl 5.42 has two anchors**: full `git` (falls with sub-issue 4)
and `neovim → wl-clipboard → xdg-utils` (sub-issue 5).

### Verification (each sub-issue)

Re-measure `nix path-info -Sh .#devkitImageEnv` before/after; confirm the
freed paths are gone from the closure; run the vulnix scan — both the closure
and the scan surface shrink.

### CI cost note

Several cuts introduce overridden derivations (`glibcLocales`, client-only
podman, neovim rewrap) that are **not** in cache.nixos.org — the first CI build
pays the rebuild; vig-os.cachix.org caches it thereafter.

### Out of scope

**Image-mode toolchain strategy** (whether to keep shipping node, neovim,
lazygit, etc., or become a direnv substrate) — a product decision about who
image mode is for. See the pinned comment; belongs in an RFC under
`docs/rfcs/`, not in this epic.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 08:43 AM_

**Deliberately out of scope: should image mode keep shipping user toolchains?**

Separate from the four size cuts in this epic — which are pure dedup + retiring
the sidecar model and do **not** touch the image's contract — there is a strategic
question this epic intentionally does **not** decide.

The image ships `nodejs-24` (+npm+corepack, ~90 MiB) and other user toolchains —
the same category includes `neovim` (~45 MiB wrapped), `lazygit` (20 MiB),
`charm-freeze` (15 MiB), `cargo-binstall` (20 MiB), `gh` (39 MiB). Relevant
finding: **`claude-code` does not bundle node** — its 246 MiB closure has zero
`nodejs` paths (node is vendored inside its own binary). So the shipped node is
purely *user-facing*, independent of the agent; dropping it would not break
Claude Code.

Two consumption modes now exist:

- **direnv mode** — no image; `mkProjectShell` + capability modules compose the
  toolchain from the project flake. Here "don't ship node" is *already* true and
  trivial.
- **image mode** — the fat OCI. Its entire value proposition is "one artifact,
  everything on `PATH`, no Nix eval at runtime, runs in plain Docker/CI without a
  flake."

Stripping node/toolchains from the image does **not** make image mode lean — it
**converts image mode into a flake-evaluator that must run `direnv` / `nix
develop` on entry** (network + cachix reachability + first-entry realise). That
deletes image mode's one advantage over direnv mode: hermetic, offline,
zero-startup, no-Nix-required. cachix speeds *pulls*, not the first-entry eval,
and adds a hard runtime dependency on cachix availability.

Where it runs decides it:

- **Ephemeral CI runners** (re-pull every job): the fat image is expensive — you
  pay 2.3 GB per run for ~10% utilisation. Thin substrate + cachix wins.
- **Long-lived dev containers** (pulled once, used for weeks): 2.3 GB amortises to
  ≈0; offline + zero-startup is pure upside. Fat wins.

So this is a **product decision about who image mode is for**, not a
size-optimisation — it belongs in an RFC under `docs/rfcs/`, not folded into this
epic. Deciding it by quietly deleting node would strand whichever consumer relied
on the mode we didn't pick.


---

# [Comment #2]() by [c-vigo]()

_Posted on July 15, 2026 at 12:50 PM_

**Size correction from #1106 (PR #1122):** the DooD-client cut nets **~67 MiB measured**, not the estimated ~254 MiB — the estimate assumed dropping podman entirely, but the retained client binary (~54 MiB) and `systemd` (rpath-linked into podman; `systemdMinimal` breaks `podman logs` per the nixpkgs pin) stay in the closure. Strategic goal fully met: **criu is gone**, removing one of the four CPython 3.13 anchors and unblocking #1107. Epic totals revised ~730 → ~550 MiB (expected final ~1.7 GB uncompressed). PRs so far: #1119 (locales, −220 MiB verified), #1120 (bandit, −74.5 MiB verified), #1122 (podman, −67 MiB verified).

---

# [Comment #3]() by [c-vigo]()

_Posted on July 15, 2026 at 02:27 PM_

**Final tally — all five sub-issues implemented and PR'd** (measured on `.#devkitImageEnv`, exact bytes):

| PR | Cut | Measured | Est. |
|---|---|---|---|
| #1119 (merged) | locales → en_US | −219.5 MiB | ~222 |
| #1120 (merged) | drop baked bandit | −74.5 MiB | ~74 |
| #1122 (merged) | podman → DooD client | −67.0 MiB | ~254 → corrected |
| #1126 (merged) | CPython 3.13 eviction (gitMinimal + actionlint) | −148.8 MiB | ~127 |
| #1128 (open) | perl eviction (neovim w/o wl-clipboard) | −108.3 MiB | ~55–60 |

**Total: 2,293,215,224 → 1,645,235,648 bytes = −618 MiB (−27%), 2.14 → 1.53 GiB uncompressed.** `podman images` will show ~1.65 GB (was 2.27 GB).

Structural outcomes beyond size:
- exactly **one** CPython (3.14) and **one** git (`gitMinimal`) in the image;
- **perl gone** → the perl 5.42.0 CVE exception batch (#1097/#1098) is *deleted* in #1128 rather than maintained;
- established, reusable pattern: image-scoped `builtins.filter` swaps against the `devTools` SSoT (`podmanClient`, `gitMinimal`, `actionlintImage`, `neovimImage`) — dev-shell behavior unchanged throughout.

Epic completes when #1128 merges. The image-mode toolchain question (node & friends) remains parked for the RFC per the pinned comment.

---

# [Comment #4]() by [c-vigo]()

_Posted on July 15, 2026 at 02:37 PM_

All five sub-issues implemented, merged to dev (435c62ed), and closed. **Final measured result: 2.14 → 1.53 GiB uncompressed (−618 MiB, −27%)** — see the [tally](https://github.com/vig-os/devkit/issues/1103#issuecomment-4981717345). Ships with the next release. The image-mode toolchain question (node & friends vs direnv substrate) stays parked for a future RFC per the pinned comment — not tracked by this epic.

