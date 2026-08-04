---
type: issue
state: closed
created: 2026-08-04T07:30:21Z
updated: 2026-08-04T08:05:38Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1333
comments: 2
labels: chore, priority:low, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:54.502Z
---

# [Issue 1333]: [chore(ci): root renovate.json extends preset via pre-rename vig-os/devcontainer slug](https://github.com/vig-os/devkit/issues/1333)

### Chore Type

Configuration change

### Description

Devkit's root `renovate.json` still extends the shared preset via the pre-rename repo slug:

```json
"extends": ["github>vig-os/devcontainer//assets/workspace/.github/renovate-default"]
```

The repo was renamed `devcontainer` → `devkit` (#781); this reference only works through GitHub's rename redirect. If a new repo ever claims the old `vig-os/devcontainer` name, the redirect breaks silently and devkit's renovate would load a foreign preset.

Scope is strictly the repo-slug preset reference in the root `renovate.json`. Container image references (`ghcr.io/vig-os/devcontainer`) are the image's actual name and are **not** in scope.

### Acceptance Criteria

- [ ] Root `renovate.json` extends `github>vig-os/devkit//assets/workspace/.github/renovate-default`
- [ ] A repo-wide grep confirms no other *repo-slug* references to `vig-os/devcontainer` remain (image-name references excluded)
- [ ] Renovate config still validates (renovate-validate workflow / config validator)

---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 07:37 AM_

Repo-wide audit of remaining `vig-os/devcontainer` references (per acceptance criteria), performed on `chore/1333-renovate-preset-slug` (PR #1334). Only the root `renovate.json` was fixed; everything below is left untouched.

**Container-image references — correct as-is** (the GHCR image is genuinely named `devcontainer`): `justfile:10`, `justfile.gh:108`, `install.sh:38`, `README.md` (88/90/96/103/106/120/210), `TESTING.md:57`, `flake.nix:1385,1387`, `.github/workflows/nix-image.yml:73,146`, `.github/workflows/ghcr-cleanup.yml:3` (org *package* name), `.github/actions/{build,test}-image`, `.github/actions/test-integration/action.yml:14,34`, `tests/bats/install.bats:95`, `tests/docker-compose.test.yml`, GHCR package paths in `docs/*RELEASE*`.

**Repo-slug references relying on the rename redirect — follow-up candidates:**
- Flake input / template URLs `github:vig-os/devcontainer`: `templates/personal/flake.nix:7-8`, `examples/nix2container-production/flake.nix:9`, `templates/python/README.md:7`, `README.md:237`, `docs/templates/README.md.j2:171`, `flake.nix:1637,1646` (comments), `docs/NIX.md:43,170`, `docs/NIX2CONTAINER.md:24,53`, `docs/MIGRATION.md:481,1043,1049`, `docs/home/BOOTSTRAP.md:36`, `docs/home/ROLLBACK.md:8`, `docs/rfcs/ADR-home-environment-modules.md:286`
- Raw-content install URL: `tests/bats/just.bats:96` (`vig-os/devcontainer/main/install.sh`)
- Template-assertion coupling: `tests/bats/init-workspace.bats:74` asserts the template flake still says `github:vig-os/devcontainer` — must move together with the template URLs above
- Prose naming the repo: `assets/smoke-test/README.md` (4/12/32/34/38/44/77/92), `assets/smoke-test/.github/workflows/repository-dispatch.yml:4`, `docs/RELEASE_CYCLE.md` (182/193/479/613), `docs/CROSS_REPO_RELEASE_GATE.md:67,69`, `docs/DOWNSTREAM_RELEASE.md:44` (+ scaffold copy), `nix/home/ghdash.nix:37`

**Not worth changing:** test-fixture repo strings (`packages/vig-utils/tests/*`), historical `vig-os/devcontainer#NNN` issue refs in comments, and archival records (`CHANGELOG.md`, `docs/pull-requests/*`, `docs/issues/*`).

If the flake-URL batch is wanted, it should be its own chore issue (template + docs + the coupled bats assertion in one PR).


---

# [Comment #2]() by [c-vigo]()

_Posted on August 4, 2026 at 08:05 AM_

Fixed in PR #1334, merged to dev @31f29c18: root renovate.json now extends github>vig-os/devkit//... . Remaining old-slug references audited and classified above; the flake-URL/docs batch is a candidate follow-up chore.

