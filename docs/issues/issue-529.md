---
type: issue
state: open
created: 2026-04-29T14:40:41Z
updated: 2026-06-07T12:11:29Z
author: renovate[bot]
author_url: https://github.com/renovate[bot]
url: https://github.com/vig-os/devcontainer/issues/529
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-08T06:53:32.498Z
---

# [Issue 529]: [Dependency Dashboard](https://github.com/vig-os/devcontainer/issues/529)

This issue lists Renovate updates and detected dependencies. Read the [Dependency Dashboard](https://docs.renovatebot.com/key-concepts/dashboard/) docs to learn more.<br>[View this repository on the Mend.io Web Portal](https://developer.mend.io/github/vig-os/devcontainer).

## Repository Problems

These problems occurred while renovating this repository. [View logs](https://developer.mend.io//github/vig-os/devcontainer).

 - ⚠️ WARN: Package lookup failures

## Rate-Limited

The following updates are currently rate-limited. To force their creation now, click on a checkbox below.

 - [ ] <!-- unlimit-branch=renovate/bats-file-0.x-lockfile -->build(npm): update dependency bats-file to v0.4.0
 - [ ] <!-- unlimit-branch=renovate/actions-dependency-review-action-5.x -->ci(actions): update actions/dependency-review-action action to v5
 - [ ] <!-- create-all-rate-limited-prs -->🔐 **Create all rate-limited PRs at once** 🔐


---

> [!WARNING]
> Renovate failed to look up the following dependencies: `Could not determine new digest for update (github-tags package bats-core/bats-action)`, `Could not determine new digest for update (github-tags package actions/dependency-review-action)`, `Failed to look up github-releases package aquasecurity/trivy: no-result`, `Could not determine new digest for update (github-tags package sigstore/cosign-installer)`.
> 
> Files affected: `.github/actions/setup-env/action.yml`, `.github/workflows/ci.yml`, `.github/workflows/promote-release.yml`, `.github/workflows/release.yml`, `.github/workflows/security-scan.yml`

---


## Open

The following updates have all been created. To force a retry/rebase of any, click on a checkbox below.

 - [ ] <!-- rebase-branch=renovate/pypi-pytest-vulnerability -->[build(pip): update dependency pytest to v9.0.3 [security]](../pull/528)
 - [ ] <!-- rebase-branch=renovate/pin-dependencies -->[build(pip): pin dependencies](../pull/530) (`bandit`, `bcrypt`, `github-backup`, `hatchling`, `ipykernel`, `jinja2`, `jupyter`, `matplotlib`, `numpy`, `pandas`, `pexpect`, `pip-licenses`, `pre-commit`, `pytest-cov`, `pytest-docker`, `pytest-testinfra`, `python`, `pyyaml`, `rich`, `ruff`, `scipy`, `testcontainers`, `testinfra`)
 - [ ] <!-- rebase-branch=renovate/python-3.12-slim-bookworm -->[build(docker): update python:3.12-slim-bookworm docker digest to 93ab4b7](../pull/531)
 - [ ] <!-- rebase-branch=renovate/actions-create-github-app-token-digest -->[chore(deps): update actions/create-github-app-token digest to bcd2ba4](../pull/532)
 - [ ] <!-- rebase-branch=renovate/astral-sh-setup-uv-digest -->[chore(deps): update astral-sh/setup-uv digest to 37802ad](../pull/533)
 - [ ] <!-- rebase-branch=renovate/github-codeql-action-digest -->[chore(deps): update github/codeql-action digest to 8aad20d](../pull/534)
 - [ ] <!-- rebase-branch=renovate/taiki-e-install-action-digest -->[chore(deps): update taiki-e/install-action digest to 957bad4](../pull/535)
 - [ ] <!-- rebase-branch=renovate/github-actions-(minor-and-patch) -->[ci(actions): update github-actions (minor and patch)](../pull/536) (`actions/cache`, `actions/checkout`, `actions/setup-node`, `actions/upload-artifact`, `aquasecurity/trivy-action`, `astral-sh/uv`, `docker/build-push-action`, `docker/login-action`, `docker/metadata-action`, `docker/setup-buildx-action`)
 - [ ] <!-- rebase-branch=renovate/python-3.x -->[build(docker): update python docker tag to v3.14](../pull/537)
 - [ ] <!-- rebase-branch=renovate/devcontainers-cli-0.x -->[build(npm): update dependency @devcontainers/cli to v0.87.0](../pull/538)
 - [ ] <!-- rebase-branch=renovate/python-(minor-and-patch) -->[build(pip): update python (minor and patch) to v3.14.5](../pull/539)
 - [ ] <!-- rebase-branch=renovate/actions-github-script-9.x -->[ci(actions): update actions/github-script action to v9](../pull/540)
 - [ ] <!-- rebase-branch=renovate/actions-setup-node-6.x -->[ci(actions): update actions/setup-node action to v6](../pull/541)
 - [ ] <!-- rebase-branch=renovate/astral-sh-setup-uv-8.x -->[ci(actions): update astral-sh/setup-uv action to v8](../pull/542)
 - [ ] <!-- rebase-branch=renovate/node-24.x -->[ci(actions): update dependency node to v24](../pull/543)
 - [ ] <!-- rebase-branch=renovate/ubuntu-24.x -->[ci(actions): update dependency ubuntu to v24](../pull/544)
 - [ ] <!-- rebase-all-open-prs -->**Click on this checkbox to rebase all open PRs at once**

## Detected Dependencies

<details><summary>dockerfile (1)</summary>
<blockquote>

<details><summary>Containerfile (1)</summary>

 - `python 3.12-slim-bookworm@sha256:d97792894a6a4162cae14da44542a83c75e56c77a27b92d58f3f83b7bc961292` → [Updates: `3.14-slim-bookworm`, `3.12-slim-bookworm`]

</details>

</blockquote>
</details>

<details><summary>github-actions (29)</summary>
<blockquote>

<details><summary>.github/actions/build-image/action.yml (5)</summary>

 - `docker/login-action v4.0.0@b45d80f862d83dbcd57f89517bcf500b2ab88fb2` → [Updates: `v4.2.0`]
 - `docker/setup-buildx-action v4.0.0@4d04d5d9486b7bd6fa91e7baf45bbb4f8b9deedd` → [Updates: `v4.1.0`]
 - `docker/metadata-action v6.0.0@030e881283bb7a6894de51c315a6bfe6a94e05cf` → [Updates: `v6.1.0`]
 - `docker/build-push-action v7.0.0@d08e5c354a6adb9ed34480a06d141179aa583294` → [Updates: `v7.2.0`]
 - `docker/build-push-action v7.0.0@d08e5c354a6adb9ed34480a06d141179aa583294` → [Updates: `v7.2.0`]

</details>

<details><summary>.github/actions/setup-env/action.yml (9)</summary>

 - `actions/setup-python v6@a309ff8b426b58ec0e2a45f0f869d46889d02405`
 - `actions/setup-python v6@a309ff8b426b58ec0e2a45f0f869d46889d02405`
 - `astral-sh/setup-uv v7@5a095e7a2014a4212f075830d4f7277575a9d098` → [Updates: `v8.2.0`, `v7`]
 - `astral-sh/setup-uv v7@5a095e7a2014a4212f075830d4f7277575a9d098` → [Updates: `v8.2.0`, `v7`]
 - `actions/setup-node v6.3.0@53b83947a5a98c8d113130e565377fae1a50d02f` → [Updates: `v6.4.0`]
 - `taiki-e/install-action just@01159adff8f38113be7211e869405f6f6abf02d7` → [Updates: `just`]
 - `bats-core/bats-action v4.0.0@77d6fb60505b4d0d1d73e48bd035b55074bbfb43`
 - `astral-sh/uv 0.10.0` → [Updates: `0.11.19`]
 - `astral-sh/uv 0.10.0` → [Updates: `0.11.19`]

</details>

<details><summary>.github/actions/test-image/action.yml (1)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]

</details>

<details><summary>.github/actions/test-integration/action.yml (1)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]

</details>

<details><summary>.github/actions/test-project/action.yml (3)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/cache v5.0.3@cdf6c1fa76f9f475f3d7449005a359c84ca0f306` → [Updates: `v5.0.5`]
 - `actions/upload-artifact v7.0.0@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` → [Updates: `v7.0.1`]

</details>

<details><summary>.github/workflows/ci.yml (34)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/upload-artifact v7.0.0@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` → [Updates: `v7.0.1`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `actions/upload-artifact v7.0.0@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` → [Updates: `v7.0.1`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/upload-artifact v7.0.0@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` → [Updates: `v7.0.1`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `aquasecurity/trivy-action v0.35.0@57a97c7e7821a5776cebc9bb87c984fa69cba8f1` → [Updates: `v0.36.0`]
 - `aquasecurity/trivy-action v0.35.0@57a97c7e7821a5776cebc9bb87c984fa69cba8f1` → [Updates: `v0.36.0`]
 - `aquasecurity/trivy-action v0.35.0@57a97c7e7821a5776cebc9bb87c984fa69cba8f1` → [Updates: `v0.36.0`]
 - `aquasecurity/trivy-action v0.35.0@57a97c7e7821a5776cebc9bb87c984fa69cba8f1` → [Updates: `v0.36.0`]
 - `aquasecurity/trivy-action v0.35.0@57a97c7e7821a5776cebc9bb87c984fa69cba8f1` → [Updates: `v0.36.0`]
 - `actions/upload-artifact v7.0.0@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` → [Updates: `v7.0.1`]
 - `github/codeql-action v4@c10b8064de6f491fea524254123dbe5e09572f13` → [Updates: `v4`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/dependency-review-action v4@2031cfc080254a8a887f58cffee85186f0e49e48` → [Updates: `v5.0.0`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `aquasecurity/trivy v0.69.3`
 - `aquasecurity/trivy v0.69.3`
 - `aquasecurity/trivy v0.69.3`
 - `aquasecurity/trivy v0.69.3`
 - `aquasecurity/trivy v0.69.3`
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>.github/workflows/codeql.yml (4)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `github/codeql-action v4@c10b8064de6f491fea524254123dbe5e09572f13` → [Updates: `v4`]
 - `github/codeql-action v4@c10b8064de6f491fea524254123dbe5e09572f13` → [Updates: `v4`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>.github/workflows/prepare-release.yml (9)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>.github/workflows/promote-release.yml (15)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `docker/login-action v4.1.0@4907a6ddec9925e35a0a9e82d7399ccc52663121` → [Updates: `v4.2.0`]
 - `sigstore/cosign-installer v4@cad07c2e89fa2edd6e2d7bab4c1aa38e53f76003`
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `docker/login-action v4.1.0@4907a6ddec9925e35a0a9e82d7399ccc52663121` → [Updates: `v4.2.0`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>.github/workflows/release.yml (33)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `aquasecurity/trivy-action v0.35.0@57a97c7e7821a5776cebc9bb87c984fa69cba8f1` → [Updates: `v0.36.0`]
 - `actions/upload-artifact v7.0.0@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` → [Updates: `v7.0.1`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `sigstore/cosign-installer v4@cad07c2e89fa2edd6e2d7bab4c1aa38e53f76003`
 - `docker/login-action v4.1.0@4907a6ddec9925e35a0a9e82d7399ccc52663121` → [Updates: `v4.2.0`]
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `anchore/sbom-action v0.24.0@e22c389904149dbc22b58101806040fa8d37a610`
 - `anchore/sbom-action v0.24.0@e22c389904149dbc22b58101806040fa8d37a610`
 - `actions/upload-artifact v7.0.0@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` → [Updates: `v7.0.1`]
 - `actions/attest-build-provenance v4.1.0@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32`
 - `actions/attest-build-provenance v4.1.0@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32`
 - `actions/attest v4.1.0@59d89421af93a897026c735860bf21b6eb4f7b26`
 - `actions/attest v4.1.0@59d89421af93a897026c735860bf21b6eb4f7b26`
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/github-script v8.0.0@ed597411d8f924073f98dfc5c65a23a2325f34cd` → [Updates: `v9.0.0`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/github-script v8.0.0@ed597411d8f924073f98dfc5c65a23a2325f34cd` → [Updates: `v9.0.0`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `aquasecurity/trivy v0.69.3`
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>.github/workflows/renovate-changelog.yml (6)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>.github/workflows/renovate-validate.yml (4)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/setup-node v4.1.0@39370e3970a6d050c480ffad4ff0ed4d3fdee5af` → [Updates: `v4.4.0`, `v6.4.0`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `node 20` → [Updates: `24`]

</details>

<details><summary>.github/workflows/scorecard.yml (4)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `ossf/scorecard-action v2.4.3@4eaacf0543bb3f2c246792bd56e8cdeffafb205a`
 - `github/codeql-action v4@c10b8064de6f491fea524254123dbe5e09572f13` → [Updates: `v4`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>.github/workflows/security-scan.yml (12)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `aquasecurity/trivy-action v0.35.0@57a97c7e7821a5776cebc9bb87c984fa69cba8f1` → [Updates: `v0.36.0`]
 - `aquasecurity/trivy-action v0.35.0@57a97c7e7821a5776cebc9bb87c984fa69cba8f1` → [Updates: `v0.36.0`]
 - `aquasecurity/trivy-action v0.35.0@57a97c7e7821a5776cebc9bb87c984fa69cba8f1` → [Updates: `v0.36.0`]
 - `aquasecurity/trivy-action v0.35.0@57a97c7e7821a5776cebc9bb87c984fa69cba8f1` → [Updates: `v0.36.0`]
 - `actions/upload-artifact v7.0.0@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` → [Updates: `v7.0.1`]
 - `github/codeql-action v4@c10b8064de6f491fea524254123dbe5e09572f13` → [Updates: `v4`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `aquasecurity/trivy v0.69.3`
 - `aquasecurity/trivy v0.69.3`
 - `aquasecurity/trivy v0.69.3`
 - `aquasecurity/trivy v0.69.3`

</details>

<details><summary>.github/workflows/sync-issues.yml (9)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/cache v5.0.3@cdf6c1fa76f9f475f3d7449005a359c84ca0f306` → [Updates: `v5.0.5`]
 - `vig-os/sync-issues-action v0.2.2@bad447d330526a7313ffddae084010c39b335fc1`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `actions/cache v5.0.3@cdf6c1fa76f9f475f3d7449005a359c84ca0f306` → [Updates: `v5.0.5`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>.github/workflows/sync-main-to-dev.yml (8)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/smoke-test/.github/workflows/repository-dispatch.yml (22)</summary>

 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/ci.yml (7)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/codeql.yml (4)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `github/codeql-action v4@c10b8064de6f491fea524254123dbe5e09572f13` → [Updates: `v4`]
 - `github/codeql-action v4@c10b8064de6f491fea524254123dbe5e09572f13` → [Updates: `v4`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/prepare-release.yml (9)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/promote-release.yml (10)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/release-core.yml (13)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/release-extension.yml (1)</summary>

 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/release-publish.yml (5)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/release.yml (6)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/renovate-changelog.yml (6)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/scorecard.yml (4)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `ossf/scorecard-action v2.4.3@4eaacf0543bb3f2c246792bd56e8cdeffafb205a`
 - `github/codeql-action v4@c10b8064de6f491fea524254123dbe5e09572f13` → [Updates: `v4`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/sync-issues.yml (9)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/cache v5.0.3@cdf6c1fa76f9f475f3d7449005a359c84ca0f306` → [Updates: `v5.0.5`]
 - `vig-os/sync-issues-action v0.2.2@bad447d330526a7313ffddae084010c39b335fc1`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `actions/cache v5.0.3@cdf6c1fa76f9f475f3d7449005a359c84ca0f306` → [Updates: `v5.0.5`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

<details><summary>assets/workspace/.github/workflows/sync-main-to-dev.yml (8)</summary>

 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `actions/checkout v6.0.2@de0fac2e4500dabe0009e67214ff5f5447ce83dd` → [Updates: `v6.0.3`]
 - `actions/create-github-app-token v3@f8d387b68d61c58ab83c6c016672934102569859` → [Updates: `v3`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]
 - `ubuntu 22.04` → [Updates: `24.04`]

</details>

</blockquote>
</details>

<details><summary>npm (1)</summary>
<blockquote>

<details><summary>package.json (5)</summary>

 - `@devcontainers/cli 0.85.0` → [Updates: `0.87.0`]
 - `bats 1.13.0`
 - `bats-support v0.3.0`
 - `bats-assert v2.2.4`
 - `bats-file v0.4.0` → [Updates: `v0.4.0`]

</details>

</blockquote>
</details>

<details><summary>pep621 (3)</summary>
<blockquote>

<details><summary>assets/workspace/pyproject.toml (11)</summary>

 - `python >=3.12` → [Updates: `==3.14.5`]
 - `hatchling >=1.25` → [Updates: `==1.30.1`]
 - `rich >=13.0.0` → [Updates: `==14.3.3`]
 - `pytest >=8.0` → [Updates: `>=8.0`]
 - `pytest-cov >=4.0` → [Updates: `==7.0.0`]
 - `ipykernel >=6.0` → [Updates: `==7.2.0`]
 - `jupyter >=1.0` → [Updates: `==1.1.1`]
 - `numpy >=2.0` → [Updates: `==2.4.6`]
 - `scipy >=1.14` → [Updates: `==1.17.1`]
 - `pandas >=2.2` → [Updates: `==3.0.3`]
 - `matplotlib >=3.9` → [Updates: `==3.10.9`]

</details>

<details><summary>packages/vig-utils/pyproject.toml (1)</summary>

 - `python >=3.10` → [Updates: `==3.14.5`]

</details>

<details><summary>pyproject.toml (24)</summary>

 - `python ==3.12.10` → [Updates: `==3.14.5`]
 - `github-backup >=0.50.3` → [Updates: `==0.61.5`]
 - `jinja2 >=3.1.0` → [Updates: `==3.1.6`]
 - `pexpect >=4.9.0` → [Updates: `==4.9.0`]
 - `pre-commit >=4.3.0` → [Updates: `==4.5.1`]
 - `pytest >=9.0.1` → [Updates: `>=9.0.1`]
 - `pyyaml >=6.0.3` → [Updates: `==6.0.3`]
 - `testinfra >=6.0.0` → [Updates: `==6.0.0`]
 - `rich >=13.0.0` → [Updates: `==14.3.3`]
 - `pre-commit >=4.3.0` → [Updates: `==4.5.1`]
 - `ruff >=0.14.3` → [Updates: `==0.15.5`]
 - `pip-licenses >=5.0.0` → [Updates: `==5.5.1`]
 - `bandit >=1.7.5` → [Updates: `==1.9.4`]
 - `pre-commit >=4.3.0` → [Updates: `==4.5.1`]
 - `ruff >=0.14.3` → [Updates: `==0.15.5`]
 - `pip-licenses >=5.0.0` → [Updates: `==5.5.1`]
 - `bandit >=1.7.5` → [Updates: `==1.9.4`]
 - `pytest >=8.4.1` → [Updates: `>=8.4.1`]
 - `pytest-cov >=6.0` → [Updates: `==7.0.0`]
 - `pytest-testinfra >=10.2.2` → [Updates: `==10.2.2`]
 - `pytest-docker >=3.2.3` → [Updates: `==3.2.5`]
 - `pexpect >=4.8.0` → [Updates: `==4.9.0`]
 - `testcontainers >=4.9.0` → [Updates: `==4.14.1`]
 - `bcrypt >=5.0.0` → [Updates: `==5.0.0`]

</details>

</blockquote>
</details>

---

- [ ] <!-- manual job -->Check this box to trigger a request for Renovate to run again on this repository


