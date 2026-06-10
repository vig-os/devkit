---
type: issue
state: open
created: 2026-04-29T14:40:41Z
updated: 2026-06-10T09:39:11Z
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
synced: 2026-06-10T10:26:40.504Z
---

# [Issue 529]: [Dependency Dashboard](https://github.com/vig-os/devcontainer/issues/529)

This issue lists Renovate updates and detected dependencies. Read the [Dependency Dashboard](https://docs.renovatebot.com/key-concepts/dashboard/) docs to learn more.<br>[View this repository on the Mend.io Web Portal](https://developer.mend.io/github/vig-os/devcontainer).

## Awaiting Schedule

The following updates are awaiting their schedule. To get an update now, click on a checkbox below.

 - [ ] <!-- unschedule-branch=renovate/taiki-e-install-action-digest -->chore(deps): update taiki-e/install-action digest to 7592c42
 - [ ] <!-- unschedule-branch=renovate/bats-file-0.x-lockfile -->build(npm): update dependency bats-file to v0.4.0
 - [ ] <!-- unschedule-branch=renovate/python-(minor-and-patch) -->build(pip): update python (minor and patch) (`ipykernel`, `testcontainers`)
 - [ ] <!-- create-all-awaiting-schedule-prs -->🔐 **Create all awaiting schedule PRs at once** 🔐


---

> [!WARNING]
> Renovate failed to look up the following dependencies: `Could not determine new digest for update (github-tags package bats-core/bats-action)`, `Could not determine new digest for update (github-tags package sigstore/cosign-installer)`.
> 
> Files affected: `.github/actions/setup-env/action.yml`, `.github/workflows/promote-release.yml`, `.github/workflows/release.yml`

---


## Detected Dependencies

<details><summary>dockerfile (1)</summary>
<blockquote>

<details><summary>Containerfile (1)</summary>

 - `python 3.14-slim-bookworm@sha256:ec58d916f9e24a6035cab2bdf07f6206c4cc092a16613c60597534711332d9d6`

</details>

</blockquote>
</details>

<details><summary>github-actions (31)</summary>
<blockquote>

<details><summary>.github/actions/build-image/action.yml (5)</summary>

 - `docker/login-action v4.2.0@650006c6eb7dba73a995cc03b0b2d7f5ca915bee`
 - `docker/setup-buildx-action v4.1.0@d7f5e7f509e45cec5c76c4d5afdd7de93d0b3df5`
 - `docker/metadata-action v6.1.0@80c7e94dd9b9319bd5eb7a0e0fe9291e23a2a2e9`
 - `docker/build-push-action v7.2.0@f9f3042f7e2789586610d6e8b85c8f03e5195baf`
 - `docker/build-push-action v7.2.0@f9f3042f7e2789586610d6e8b85c8f03e5195baf`

</details>

<details><summary>.github/actions/setup-env/action.yml (9)</summary>

 - `actions/setup-python v6@a309ff8b426b58ec0e2a45f0f869d46889d02405`
 - `actions/setup-python v6@a309ff8b426b58ec0e2a45f0f869d46889d02405`
 - `astral-sh/setup-uv v8.2.0@fac544c07dec837d0ccb6301d7b5580bf5edae39`
 - `astral-sh/setup-uv v8.2.0@fac544c07dec837d0ccb6301d7b5580bf5edae39`
 - `actions/setup-node v6.4.0@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e`
 - `taiki-e/install-action just@e75cfd3544e409eb8da0d09dd5d918cd3e6e3982` → [Updates: `just`]
 - `bats-core/bats-action v4.0.0@77d6fb60505b4d0d1d73e48bd035b55074bbfb43`
 - `astral-sh/uv 0.11.19`
 - `astral-sh/uv 0.11.19`

</details>

<details><summary>.github/actions/test-image/action.yml (1)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`

</details>

<details><summary>.github/actions/test-integration/action.yml (1)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`

</details>

<details><summary>.github/actions/test-project/action.yml (3)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/cache v5.0.5@27d5ce7f107fe9357f9df03efb73ab90386fccae`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`

</details>

<details><summary>.github/workflows/ci.yml (34)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `github/codeql-action v4@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/dependency-review-action v5.0.0@a1d282b36b6f3519aa1f3fc636f609c47dddb294`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `aquasecurity/trivy v0.71.0`
 - `aquasecurity/trivy v0.71.0`
 - `aquasecurity/trivy v0.71.0`
 - `aquasecurity/trivy v0.71.0`
 - `aquasecurity/trivy v0.71.0`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/codeql.yml (4)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `github/codeql-action v4@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
 - `github/codeql-action v4@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/prepare-release.yml (9)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/promote-release.yml (15)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `docker/login-action v4.2.0@650006c6eb7dba73a995cc03b0b2d7f5ca915bee`
 - `sigstore/cosign-installer v4@cad07c2e89fa2edd6e2d7bab4c1aa38e53f76003`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `docker/login-action v4.2.0@650006c6eb7dba73a995cc03b0b2d7f5ca915bee`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/release.yml (33)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `sigstore/cosign-installer v4@cad07c2e89fa2edd6e2d7bab4c1aa38e53f76003`
 - `docker/login-action v4.2.0@650006c6eb7dba73a995cc03b0b2d7f5ca915bee`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `anchore/sbom-action v0.24.0@e22c389904149dbc22b58101806040fa8d37a610`
 - `anchore/sbom-action v0.24.0@e22c389904149dbc22b58101806040fa8d37a610`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `actions/attest-build-provenance v4.1.0@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32`
 - `actions/attest-build-provenance v4.1.0@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32`
 - `actions/attest v4.1.0@59d89421af93a897026c735860bf21b6eb4f7b26`
 - `actions/attest v4.1.0@59d89421af93a897026c735860bf21b6eb4f7b26`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/github-script v9.0.0@3a2844b7e9c422d3c10d287c895573f7108da1b3`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/github-script v9.0.0@3a2844b7e9c422d3c10d287c895573f7108da1b3`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `aquasecurity/trivy v0.71.0`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/renovate-changelog-build.yml (5)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/renovate-changelog-commit.yml (4)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/renovate-validate.yml (4)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/setup-node v6.4.0@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e`
 - `ubuntu 24.04`
 - `node 24`

</details>

<details><summary>.github/workflows/scorecard.yml (4)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `ossf/scorecard-action v2.4.3@4eaacf0543bb3f2c246792bd56e8cdeffafb205a`
 - `github/codeql-action v4@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/security-scan.yml (12)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `aquasecurity/trivy-action v0.36.0@ed142fd0673e97e23eac54620cfb913e5ce36c25`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `github/codeql-action v4@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
 - `ubuntu 24.04`
 - `aquasecurity/trivy v0.71.0`
 - `aquasecurity/trivy v0.71.0`
 - `aquasecurity/trivy v0.71.0`
 - `aquasecurity/trivy v0.71.0`

</details>

<details><summary>.github/workflows/sync-issues.yml (9)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/cache v5.0.5@27d5ce7f107fe9357f9df03efb73ab90386fccae`
 - `vig-os/sync-issues-action v0.2.2@bad447d330526a7313ffddae084010c39b335fc1`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `actions/cache v5.0.5@27d5ce7f107fe9357f9df03efb73ab90386fccae`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>.github/workflows/sync-main-to-dev.yml (8)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/smoke-test/.github/workflows/repository-dispatch.yml (22)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
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

<details><summary>assets/workspace/.github/workflows/ci.yml (7)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/codeql.yml (4)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `github/codeql-action v4@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
 - `github/codeql-action v4@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/prepare-release.yml (9)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/promote-release.yml (10)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/release-core.yml (13)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/release-extension.yml (1)</summary>

 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/release-publish.yml (5)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/release.yml (6)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/renovate-changelog-build.yml (5)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/upload-artifact v7.0.1@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/renovate-changelog-commit.yml (4)</summary>

 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/download-artifact v8.0.1@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/scorecard.yml (4)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `ossf/scorecard-action v2.4.3@4eaacf0543bb3f2c246792bd56e8cdeffafb205a`
 - `github/codeql-action v4@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/sync-issues.yml (9)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/cache v5.0.5@27d5ce7f107fe9357f9df03efb73ab90386fccae`
 - `vig-os/sync-issues-action v0.2.2@bad447d330526a7313ffddae084010c39b335fc1`
 - `vig-os/commit-action v0.2.0@1bc004353d08d9332a0cb54920b148256220c8e0`
 - `actions/cache v5.0.5@27d5ce7f107fe9357f9df03efb73ab90386fccae`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

<details><summary>assets/workspace/.github/workflows/sync-main-to-dev.yml (8)</summary>

 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `actions/checkout v6.0.3@df4cb1c069e1874edd31b4311f1884172cec0e10`
 - `actions/create-github-app-token v3@bcd2ba49218906704ab6c1aa796996da409d3eb1`
 - `ubuntu 24.04`
 - `ubuntu 24.04`
 - `ubuntu 24.04`

</details>

</blockquote>
</details>

<details><summary>npm (1)</summary>
<blockquote>

<details><summary>package.json (5)</summary>

 - `@devcontainers/cli 0.87.0`
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

 - `python ==3.14.5`
 - `hatchling ==1.30.1`
 - `rich ==15.0.0`
 - `pytest ==9.0.3`
 - `pytest-cov ==7.1.0`
 - `ipykernel ==7.2.0` → [Updates: `==7.3.0`]
 - `jupyter ==1.1.1`
 - `numpy ==2.4.6`
 - `scipy ==1.17.1`
 - `pandas ==3.0.3`
 - `matplotlib ==3.10.9`

</details>

<details><summary>packages/vig-utils/pyproject.toml (1)</summary>

 - `python ==3.14.5`

</details>

<details><summary>pyproject.toml (24)</summary>

 - `python ==3.14.5`
 - `github-backup ==0.62.1`
 - `jinja2 ==3.1.6`
 - `pexpect ==4.9.0`
 - `pre-commit ==4.6.0`
 - `pytest ==9.0.3`
 - `pyyaml ==6.0.3`
 - `testinfra ==6.0.0`
 - `rich ==15.0.0`
 - `pre-commit ==4.6.0`
 - `ruff ==0.15.16`
 - `pip-licenses ==5.5.5`
 - `bandit ==1.9.4`
 - `pre-commit ==4.6.0`
 - `ruff ==0.15.16`
 - `pip-licenses ==5.5.5`
 - `bandit ==1.9.4`
 - `pytest ==9.0.3`
 - `pytest-cov ==7.1.0`
 - `pytest-testinfra ==10.2.2`
 - `pytest-docker ==3.2.5`
 - `pexpect ==4.9.0`
 - `testcontainers ==4.14.1` → [Updates: `==4.14.2`]
 - `bcrypt ==5.0.0`

</details>

</blockquote>
</details>

---

- [ ] <!-- manual job -->Check this box to trigger a request for Renovate to run again on this repository


