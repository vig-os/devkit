---
type: issue
state: open
created: 2026-04-29T14:40:41Z
updated: 2026-08-02T01:12:28Z
author: renovate[bot]
author_url: https://github.com/renovate[bot]
url: https://github.com/vig-os/devkit/issues/529
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-02T05:34:25.488Z
---

# [Issue 529]: [Dependency Dashboard](https://github.com/vig-os/devkit/issues/529)

This issue lists Renovate updates and detected dependencies. Read the [Dependency Dashboard](https://docs.renovatebot.com/key-concepts/dashboard/) docs to learn more.<br>[View this repository on the Mend.io Web Portal](https://developer.mend.io/github/vig-os/devkit).

## Awaiting Schedule

The following updates are awaiting their schedule. To get an update now, click on a checkbox below.

 - [ ] <!-- unschedule-branch=renovate/python-(minor-and-patch) -->build(pip): update dependency github-backup to v0.65.1
 - [ ] <!-- unschedule-branch=renovate/lock-file-maintenance -->build(pip): lock file maintenance
 - [ ] <!-- create-all-awaiting-schedule-prs -->🔐 **Create all awaiting schedule PRs at once** 🔐

## Detected Dependencies

<details><summary>github-actions (40)</summary>
<blockquote>

<details><summary>.github/actions/setup-env/action.yml (3)</summary>

 - `cachix/install-nix-action v31.11.0@630ae543ea3a38a9a4166f03376c02c50f408342`
 - `cachix/cachix-action v17@5f2d7c5294214f71b873db4b969586b980625e71`
 - `actions/setup-node v7.0.0@820762786026740c76f36085b0efc47a31fe5020`

</details>

<details><summary>.github/actions/test-image/action.yml (1)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`

</details>

<details><summary>.github/actions/test-integration/action.yml (1)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`

</details>

<details><summary>.github/actions/test-project/action.yml (3)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/cache v6.1.0@55cc8345863c7cc4c66a329aec7e433d2d1c52a9`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`

</details>

<details><summary>.github/workflows/ci.yml (29)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/dependency-review-action v5.0.0@a1d282b36b6f3519aa1f3fc636f609c47dddb294`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `aquasecurity/trivy v0.72.0`
 - `aquasecurity/trivy v0.72.0`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/codeql.yml (4)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `github/codeql-action v4@f205ea1c3313d32999d8d6a48b4f6530d4437b38`
 - `github/codeql-action v4@f205ea1c3313d32999d8d6a48b4f6530d4437b38`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/ghcr-cleanup.yml (2)</summary>

 - `dataaxiom/ghcr-cleanup-action v1.2.2@d52806a0dc70b430571a37da1fde39733ffd640f`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/home-matrix.yml (7)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `cachix/install-nix-action v31.11.0@630ae543ea3a38a9a4166f03376c02c50f408342`
 - `cachix/cachix-action v17@5f2d7c5294214f71b873db4b969586b980625e71`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `cachix/install-nix-action v31.11.0@630ae543ea3a38a9a4166f03376c02c50f408342`
 - `cachix/cachix-action v17@5f2d7c5294214f71b873db4b969586b980625e71`
 - `ubuntu 24.04-arm`

</details>

<details><summary>.github/workflows/nix-cachix.yml (4)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `cachix/install-nix-action v31.11.0@630ae543ea3a38a9a4166f03376c02c50f408342`
 - `cachix/cachix-action v17@5f2d7c5294214f71b873db4b969586b980625e71`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/nix-image.yml (6)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `cachix/install-nix-action v31.11.0@630ae543ea3a38a9a4166f03376c02c50f408342`
 - `cachix/cachix-action v17@5f2d7c5294214f71b873db4b969586b980625e71`
 - `docker/login-action v4.6.0@dbcb813823bdd20940b903addbd779551569679f`
 - `docker/login-action v4.6.0@dbcb813823bdd20940b903addbd779551569679f`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/prepare-release-extension.yml (5)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/prepare-release.yml (13)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/promote-release.yml (15)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `docker/login-action v4.6.0@dbcb813823bdd20940b903addbd779551569679f`
 - `sigstore/cosign-installer v4.1.2@6f9f17788090df1f26f669e9d70d6ae9567deba6`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `docker/login-action v4.6.0@dbcb813823bdd20940b903addbd779551569679f`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/release.yml (35)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `sigstore/cosign-installer v4.1.2@6f9f17788090df1f26f669e9d70d6ae9567deba6`
 - `docker/login-action v4.6.0@dbcb813823bdd20940b903addbd779551569679f`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `anchore/sbom-action v0.24.0@e22c389904149dbc22b58101806040fa8d37a610`
 - `anchore/sbom-action v0.24.0@e22c389904149dbc22b58101806040fa8d37a610`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/attest-build-provenance v4.1.1@0f67c3f4856b2e3261c31976d6725780e5e4c373`
 - `actions/attest-build-provenance v4.1.1@0f67c3f4856b2e3261c31976d6725780e5e4c373`
 - `actions/attest v4.2.1@508db95dd578ae2727ebd6217d5ba78e4fbda05d`
 - `actions/attest v4.2.1@508db95dd578ae2727ebd6217d5ba78e4fbda05d`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/github-script v9.0.0@3a2844b7e9c422d3c10d287c895573f7108da1b3`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/github-script v9.0.0@3a2844b7e9c422d3c10d287c895573f7108da1b3`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `aquasecurity/trivy v0.72.0`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/renovate-changelog-build.yml (3)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/renovate-changelog-commit.yml (4)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/renovate-validate.yml (4)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/setup-node v7.0.0@820762786026740c76f36085b0efc47a31fe5020`
 - `ubuntu 24.04`
 - `node 24`

</details>

<details><summary>.github/workflows/scorecard.yml (4)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `ossf/scorecard-action v2.4.4@2d1146689b8cda280b9bc96326124645441f03bc`
 - `github/codeql-action v4@f205ea1c3313d32999d8d6a48b4f6530d4437b38`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/security-scan.yml (8)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/cache v6.1.0@55cc8345863c7cc4c66a329aec7e433d2d1c52a9`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `ubuntu 24.04`
 - `aquasecurity/trivy v0.72.0`
 - `aquasecurity/trivy v0.72.0`

</details>

<details><summary>.github/workflows/sync-issues.yml (7)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/cache v6.1.0@55cc8345863c7cc4c66a329aec7e433d2d1c52a9`
 - `vig-os/sync-issues-action v0.4.0@285a0af876bac99a0e914a64a1cb925dd913f38a`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `actions/cache v6.1.0@55cc8345863c7cc4c66a329aec7e433d2d1c52a9`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/sync-main-to-dev.yml (6)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/update-nixpkgs-unstable.yml (6)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `cachix/install-nix-action v31.11.0@630ae543ea3a38a9a4166f03376c02c50f408342`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `ubuntu 24.04`

</details>

<details><summary>assets/smoke-test/.github/workflows/direnv-smoke.yml (5)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `cachix/install-nix-action v31.11.0@630ae543ea3a38a9a4166f03376c02c50f408342`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/smoke-test/.github/workflows/repository-dispatch.yml (22)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/actions/setup-devkit-toolchain/action.yml (3)</summary>

 - `cachix/install-nix-action v31.11.0@630ae543ea3a38a9a4166f03376c02c50f408342`
 - `cachix/cachix-action v17@5f2d7c5294214f71b873db4b969586b980625e71`
 - `astral-sh/setup-uv v9.0.0@c771a70e6277c0a99b617c7a806ffedaca235ff9`

</details>

<details><summary>assets/workspace/.github/workflows/ci.yml (9)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/dependency-review-action v5.0.0@a1d282b36b6f3519aa1f3fc636f609c47dddb294`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/codeql.yml (4)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `github/codeql-action v4@f205ea1c3313d32999d8d6a48b4f6530d4437b38`
 - `github/codeql-action v4@f205ea1c3313d32999d8d6a48b4f6530d4437b38`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/devkit-upgrade.yml (3)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `cachix/install-nix-action v31.11.0@630ae543ea3a38a9a4166f03376c02c50f408342`

</details>

<details><summary>assets/workspace/.github/workflows/prepare-release-extension.yml (1)</summary>

 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/prepare-release.yml (13)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/promote-release.yml (17)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/release-core.yml (11)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/release-extension.yml (1)</summary>

 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/release-publish.yml (3)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/release.yml (7)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/renovate-changelog-build.yml (5)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/renovate-changelog-commit.yml (4)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/scorecard.yml (4)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `ossf/scorecard-action v2.4.4@2d1146689b8cda280b9bc96326124645441f03bc`
 - `github/codeql-action v4@f205ea1c3313d32999d8d6a48b4f6530d4437b38`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/sync-issues.yml (9)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/cache v6.1.0@55cc8345863c7cc4c66a329aec7e433d2d1c52a9`
 - `vig-os/sync-issues-action v0.4.0@285a0af876bac99a0e914a64a1cb925dd913f38a`
 - `vig-os/commit-action v0.3.1@3a0588ec060d9647bf406e064cf9e6192a431864`
 - `actions/cache v6.1.0@55cc8345863c7cc4c66a329aec7e433d2d1c52a9`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/sync-main-to-dev.yml (8)</summary>

 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v7.0.1@3d3c42e5aac5ba805825da76410c181273ba90b1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

</blockquote>
</details>

<details><summary>npm (1)</summary>
<blockquote>

<details><summary>package.json (1)</summary>

 - `@devcontainers/cli 0.88.0`

</details>

</blockquote>
</details>

<details><summary>pep621 (3)</summary>
<blockquote>

<details><summary>packages/vig-utils/pyproject.toml</summary>


</details>

<details><summary>pyproject.toml (18)</summary>

 - `github-backup ==0.65.0` → [Updates: `==0.65.1`]
 - `jinja2 ==3.1.6`
 - `pexpect ==4.9.0`
 - `pytest ==9.1.1`
 - `pyyaml ==6.0.3`
 - `testinfra ==6.0.0`
 - `rich ==15.0.0`
 - `pip-licenses ==5.5.5`
 - `bandit ==1.9.4`
 - `pip-licenses ==5.5.5`
 - `bandit ==1.9.4`
 - `pytest ==9.1.1`
 - `pytest-cov ==7.1.0`
 - `pytest-testinfra ==10.2.2`
 - `pytest-docker ==3.2.5`
 - `pexpect ==4.9.0`
 - `testcontainers ==4.15.0`
 - `bcrypt ==5.0.0`

</details>

<details><summary>templates/python/pyproject.toml (2)</summary>

 - `pytest ==9.1.1`
 - `pytest-cov ==7.1.0`

</details>

</blockquote>
</details>

<details><summary>regex (1)</summary>
<blockquote>

<details><summary>flake.nix (1)</summary>

 - `pip-licenses 5.5.5`

</details>

</blockquote>
</details>

---

- [ ] <!-- manual job -->Check this box to trigger a request for Renovate to run again on this repository


