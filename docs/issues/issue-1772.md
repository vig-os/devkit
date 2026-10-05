---
type: issue
state: closed
created: 2026-09-29T15:36:35Z
updated: 2026-09-30T17:51:19Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1772
comments: 2
labels: discussion, area:workflow
assignees: none
milestone: none
projects: none
parent: 1769
children: 1779
synced: 2026-10-01T08:40:55.159Z
---

# [Issue 1772]: [[SPIKE] Publish lane: PyPI (Trusted Publishing, PEP 740 attestations, pure + PyO3/maturin wheels)](https://github.com/vig-os/devkit/issues/1772)

Parent spike: #1769. Research the 2026 best practice for publishing Python distributions (pure-Python and PyO3/maturin native wheels) to PyPI and decide what devkit manages.

## Motivation / why

The org has pure-Python repos and Rust+Python (pyo3 abi3) repos (tessera). Both need PyPI with no long-lived tokens and with attestations. Nothing exists today beyond a comment in the publish seam stub.

## Proposed approach (strawman)

- Trusted Publishing via `pypa/gh-action-pypi-publish` (PEP 740 attestations on by default) — or `uv publish` with OIDC; decide which is the 2026 default.
- Build: `uv build` for pure Python; `maturin` (or `PyO3/maturin-action` / cibuildwheel / nix-built abi3 wheel) for native — build stays a project recipe; wheels also land on the GitHub Release in the assets window.
- RCs → PyPI prerelease (`X.Y.ZrcN`) or TestPyPI — decide.

## What already exists

`publish-release-extension.yml` stub (on `dev`), uv-based toolchain in the image, `docs/rfcs/ADR-uv2nix-pyproject-nix.md`, `DEVKIT_PRERELEASE_FORMAT` (#1746).

## Scope / questions

- [ ] PyPI Trusted Publishing and reusable workflows: supported in 2026? If not, the managed publish workflow must be top-level.
- [ ] `gh-action-pypi-publish` vs `uv publish --trusted-publishing` — attestations parity?
- [ ] Native wheels: manylinux/musllinux/macOS/Windows matrix — cibuildwheel vs maturin-action vs nix; what should devkit template?
- [ ] Version mapping: train `1.2.3-rc1` → PEP 440 `1.2.3rc1`; where does the version get written (`pyproject.toml`, dynamic via VCS)?
- [ ] PEP 639 license metadata, sdist inclusion — any 2026 gates?

## Pitfalls

- A version on PyPI can never be re-uploaded, even after deletion.
- PyPI rejects non-PEP 440 versions; a SemVer prerelease string fails late.
- Pending publishers: first-time project creation via Trusted Publishing needs a pending publisher set up by a human.
- Wheel built in the assets window vs. uploaded after `release: published` must be the same bytes (attestation continuity).

## Acceptance criteria

- [ ] Dated verdict (verified-on / verified-how) on the 2026 best practice for this channel, with primary sources (registry docs, official actions)
- [ ] Gap table: best practice vs. what devkit ships today
- [ ] Concrete split: **devkit owns** (managed) / **devkit seeds** (template) / **repo owns** (build recipe, registry registration)
- [ ] Prerelease policy for this channel decided
- [ ] Implementation issue(s) filed, or an explicit "won't do" with reason

## References

Parent: #1769 · #1746 · #1748 · #1523 · #1519 · `docs/DOWNSTREAM_RELEASE.md` (on `dev`)

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 03:41 PM_

> Round-1 specialist review (fresh context, research only). Verified 2026-09-29 against primary sources; claims the reviewer could not verify are marked UNVERIFIED. Consolidated verdict: #1769.

## Verdict
- **Publisher:** `pypa/gh-action-pypi-publish`, not `uv publish`. uv does OIDC but **does not generate PEP 740 attestations**, so the two are not at parity.
- **Native wheels:** `PyO3/maturin-action` builds, the PyPA action uploads. `maturin generate-ci` emits `uv publish` and so loses attestations; treat it as a starting template only.
- **Reusable workflows cannot be the trusted publisher** ([gh-action-pypi-publish#166](https://github.com/pypa/gh-action-pypi-publish/issues/166), [warehouse#11096](https://github.com/pypi/warehouse/issues/11096)). The publish workflow must be a fixed-name top-level file.
- **Version:** dynamic from the git tag (`hatch-vcs` / `setuptools-scm` / `uv-dynamic-versioning`) and written as PEP 440 (`1.2.3rc1`).
- **Release candidates:** go to **production PyPI as prereleases**, not TestPyPI (which is pruned and not a staging channel). pip skips them unless `--pre` is passed.

## Split
- **Managed:** the upload job (PyPA action with `attestations: true`) and the skip-if-exists precheck.
- **Seeded:** the `just dist-pypi` recipe (`uv build`, or a maturin matrix) and a `pyproject.toml` skeleton with a dynamic version backend and a PEP 639 licence expression.
- **Repo:** pending-publisher registration (a one-time human step).

## New pitfalls
- **Some `DEVKIT_PRERELEASE_FORMAT` values have no PEP 440 spelling:** `nightly.YYYYMMDD.N` is unmappable and `beta` without N is invalid. devkit must refuse these, or normalise them, before publish.
- **Byte identity:** the wheel on the draft Release must be the same bytes as the wheel uploaded to PyPI, or attestation continuity is lost. Build once, feed both.
- Deleted PyPI filenames can never be reused.
- Seed legacy `License` or PEP 639 `License-Expression`, not both; mixing them is rejected.

Sources: [pypi-publish README](https://github.com/pypa/gh-action-pypi-publish) · [uv publish](https://docs.astral.sh/uv/guides/publish/) · [maturin distribution](https://www.maturin.rs/distribution) · [PEP 440](https://peps.python.org/pep-0440/#pre-releases) · [TestPyPI](https://packaging.python.org/en/latest/guides/using-testpypi/)


---

# [Comment #2]() by [c-vigo]()

_Posted on September 30, 2026 at 05:51 PM_

Spike complete. The dated verdict is in the review above; the cross-cutting decision is recorded in `docs/rfcs/ADR-publish-lanes.md` (PR #1785, merged to `dev` as 36e74ccc), per #1769's rule that the channel spikes close when the ADR lands.

Implementation continues in: #1779 (PyPI lane) (lane foundation: #1778).

