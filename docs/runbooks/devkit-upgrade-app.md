# Runbook: `vigos-devkit-upgrade` GitHub App

Human-executed procedure for creating, permissioning, and rotating the key of the GitHub App that
authenticates the scaffolded self-polling upgrade workflow
(`assets/workspace/.github/workflows/devkit-upgrade.yml`, #1296). As with the org-management App
(`docs/runbooks/github-app.md` in `vig-os/org-config`), this App is **never** created or configured
as code — it is the credential the scaffolded workflow runs on, so it is a human, in the GitHub web
UI, who creates it, installs it, and rotates its key.

The App exists because of #1302 (default `GITHUB_TOKEN` cannot open a PR that triggers CI, and a
static PAT is unsuitable — user-bound, expiring, single-owner); #1365 is the `DEVKIT_UPGRADE_APP_ID`
→ `DEVKIT_UPGRADE_APP_CLIENT_ID` rename, and #1366 retires the legacy numeric-ID fallback.

## Purpose

One GitHub App is the machine identity behind every consumer's scaffolded `devkit-upgrade.yml`:

- **One App**, slug `vigos-devkit-upgrade`, **owned by the `vig-os` org**.
- **Installed on every org that runs the scaffolded workflow** — `vig-os` itself, plus `exo-pet` (a
  foreign org relative to the owning org; confirmed installation id `151387251`, recorded beside the
  `APP VISIBILITY DECISION` comment in `vig-os/org-config`'s
  `otterdog/vig-os/vig-os.jsonnet`).
- Mints a **per-run, per-repo installation token** (via `actions/create-github-app-token`, minted
  fresh inside each `devkit-upgrade` run) that opens the adoption PR under the App's identity so the
  PR triggers CI — the same reason the org-management App exists as a dedicated identity rather than
  a shared token.

## Prerequisites

- You are an **owner of the `vig-os` org** (App creation, and editing its Permissions & events page,
  is owner-only on GitHub).
- To install the App on a downstream org (e.g. `exo-pet`), you are also an **owner of that target
  org** — a public App's install page still requires the installing account to own the target
  account it installs onto.

## Create the App

Go to <https://github.com/organizations/vig-os/settings/apps/new> and fill in:

- **GitHub App name**: `vigos-devkit-upgrade` (the slug used throughout this runbook and in
  `vig-os/org-config`'s jsonnet comments is derived from this name).

  > **Gap — verify against the live App:** neither the workflow header, the `org-config` jsonnet,
  > nor issue #1739 records the App's exact display name if it differs from its slug, or its
  > **Homepage URL**. Read both off the App's own Settings page before recreating it, rather than
  > guessing a value here.

- **Webhook**: **uncheck "Active"**. The App subscribes to no events (`events: []`, confirmed in
  `vig-os/org-config`'s jsonnet comment) — drift/failure detection is the scheduled workflow run
  itself, not a webhook. Leave the webhook URL and secret **empty**.
- **Permissions**: set exactly the table below and nothing else.
- **Where can this GitHub App be installed?**: **Any account** — public by decision (2026-09-28,
  [vig-os/org-config#271](https://github.com/vig-os/org-config/issues/271)). See
  [Visibility](#visibility) below; do not re-decide this here.

### Permissions

| Category   | Permission     | Access | Why                                                                    |
| ---------- | -------------- | ------ | ----------------------------------------------------------------------- |
| Repository | Contents       | Write  | create the branch and commit the upgrade + adoption PR                  |
| Repository | Pull requests  | Write  | open the adoption PR                                                    |
| Repository | Workflows      | Write  | the upgrade commits can touch `.github/workflows/*` (scaffold regen)    |
| Repository | Issues         | Write  | **optional** — files/updates/closes the one-per-repo failure-tracking issue (#1530) |
| Repository | Metadata       | Read   | mandatory baseline (auto-selected by GitHub on every App); never remove |

Set every unlisted permission to **No access** — in particular no `organization_administration`, no
Secrets, no Members, no Administration (confirmed absent by the `APP VISIBILITY DECISION` jsonnet
comment, which contrasts this App's narrow grant against the org-management App's much wider one).

**`issues:write` is the one optional grant, not a fourth load-bearing permission alongside the other
three.** The scaffolded workflow's own preflight step says so directly: without it, the `report` job
(#1530) degrades to a logged warning and the upgrade path itself is unaffected — `contents`,
`pull_requests`, and `workflows` write plus `metadata` read are the minimum that makes the upgrade
PR possible at all. Issue #1739 lists the same five permissions without singling one out as
optional; the two framings are consistent (`issues` is on the grant table either way), but this
runbook keeps the workflow header's nuance because it is the operationally relevant one: an
installation that withholds `issues:write` is still a fully working upgrade identity, just one with
a quieter failure mode.

### Webhooks

**Disabled.** No webhook URL, no webhook secret, `events: []`. Failure detection is the scheduled
run itself (weekly Monday cron) plus the `report` job's tracking issue (#1530); nothing needs to be
pushed to this App.

### Visibility

**Public — "Any account"**, decided 2026-09-28 under
[vig-os/org-config#271](https://github.com/vig-os/org-config/issues/271). **This runbook links to
that decision rather than re-deciding it** — the full reasoning (why public, the two accepted costs,
the #256 ruleset-bypass coupling that does *not* apply here, and the UI-only verification procedure)
lives in two places, both outside this repo:

- The `APP VISIBILITY DECISION` comment beside the `DEVKIT_UPGRADE_APP_CLIENT_ID` /
  `DEVKIT_UPGRADE_APP_ID` / `DEVKIT_UPGRADE_APP_PRIVATE_KEY` declarations in
  `vig-os/org-config`'s `otterdog/vig-os/vig-os.jsonnet` — the App's **only appearance in code**,
  and the source of truth for exactly which repositories each credential secret is scoped to (see
  [Bootstrap secrets](#bootstrap-secrets) below).
- [`vig-os/org-config#271`](https://github.com/vig-os/org-config/issues/271), the issue that
  recorded the decision, following the precedent of the org-management App's own visibility
  decision ([`vig-os/org-config#261`](https://github.com/vig-os/org-config/issues/261),
  `docs/runbooks/github-app.md` → Visibility, in that same repo).

In short: public is not a preference, it is a consequence of the install model. A **private** App
can only be installed on the account that owns it; this App is installed on `exo-pet` — a foreign
org relative to `vig-os` — so that installation could not exist if the App were private. The same
one-App/N-installations reasoning as the org-management App's own visibility call. The grant this
App carries is far narrower than that App's, which is what makes the same posture cheaper here: no
`organization_administration`, no Secrets, no Members, no Administration — an anonymous
`GET /apps/vigos-devkit-upgrade` publishes only the five permissions above, the numeric App ID, the
owner, the creation date, the Client ID, and `events: []`. It does **not** publish the private key,
the installation set, or which repositories the org secrets below name.

**Do not re-verify or flip this here.** If you need to confirm the live setting, follow the
identical UI procedure recorded for the org-management App (`docs/runbooks/github-app.md` in
`vig-os/org-config`, § Verifying the setting), substituting `vigos-devkit-upgrade` for
`vig-os-org-config` in the Settings path. If what you find contradicts the recorded decision, that
is drift in the App itself — open an issue and reconcile it there, never flip the setting back by
hand.

## Installation

After the App is created:

1. Click **Install App** and install it on **`vig-os`**.
2. Repeat for **`exo-pet`** (as an owner of that org, from the App's public install page,
   `https://github.com/apps/vigos-devkit-upgrade`) — the whole reason this App is public (see
   [Visibility](#visibility)).
3. From the App's **General** page, copy the **Client ID** and **generate a private key**
   (**Generate a private key** → downloads a `.pem`). Store both in the bootstrap secrets below,
   then delete the downloaded `.pem` from disk.

   > **Gap — verify against the live App:** neither source read for this runbook states the
   > installation **repository scope** ("All repositories" vs. "Only select repositories") actually
   > chosen on `vig-os` or on `exo-pet`. Confirm the live setting in each org's
   > **Settings → GitHub Apps → Configure** page rather than assuming "All repositories" by analogy
   > with the org-management App.

## Bootstrap secrets

The credentials are **`vig-os` organization Actions secrets**, declared as code (visibility
`selected`, naming specific consumer repositories) in `vig-os/org-config`'s
`otterdog/vig-os/vig-os.jsonnet`. **That jsonnet file is the source of truth for which secrets exist
and which repositories each one is scoped to** — read it there rather than re-deriving the list here,
since it changes independently of this repo (every devkit consumer re-scaffolded to devkit ≥ 1.6
adds itself to the relevant list, per the jsonnet's own maintenance-coupling comment).

| Secret name                      | Value                                              |
| --------------------------------- | --------------------------------------------------- |
| `DEVKIT_UPGRADE_APP_CLIENT_ID`     | the App's Client ID (preferred; #1365)              |
| `DEVKIT_UPGRADE_APP_ID`            | the App's legacy numeric App ID — **deprecated**, retired by #1366; either value is a valid App JWT issuer |
| `DEVKIT_UPGRADE_APP_PRIVATE_KEY`   | the full `.pem` private key, PEM-encoded             |

At the time this runbook was written, `otterdog/vig-os/vig-os.jsonnet` scoped
`DEVKIT_UPGRADE_APP_CLIENT_ID` and `DEVKIT_UPGRADE_APP_PRIVATE_KEY` to `commit-action`,
`devkit-smoke-test`, `h5v`, `org-config`, `scitadel`, `sync-issues-action`, and `tessera`, and the
legacy `DEVKIT_UPGRADE_APP_ID` to the subset still on a pre-1.7 scaffold form
(`commit-action`, `devkit-smoke-test`, `org-config`, `sync-issues-action`). Treat these lists as a
snapshot, not a promise — `vig-os/org-config` is authoritative going forward. `devkit` itself does
not upgrade itself, so `devkit` is not on either list. `exo-pet`'s own consuming repositories carry
their own copies of these secrets, declared in `exo-pet`'s own private `org-config` repo (out of
scope for this runbook — it belongs to a different repo and a different confidentiality boundary).

These are **bootstrap secrets and are never managed as application config**: they are the credential
the scaffolded workflow runs *on*. They are set once, by hand, in `vig-os`'s org Actions secrets and
rotated by hand.

## Key rotation

The private key is the whole App's secret; rotate it on schedule and on any suspected exposure. The
**Client ID and the legacy numeric App ID do not change** on rotation — only
`DEVKIT_UPGRADE_APP_PRIVATE_KEY` is touched.

1. On the App's **General** page → **Private keys** → **Generate a private key**. GitHub keeps the
   old key valid alongside the new one, so there is no outage window.
2. Update the `DEVKIT_UPGRADE_APP_PRIVATE_KEY` org secret's value on `vig-os` (via `vig-os/org-config`
   otterdog `apply`, or by hand in `vig-os`'s Actions secrets if applying out of band), and, if this
   App's credentials are ever independently mirrored elsewhere (e.g. `exo-pet`'s own org-config),
   there too.
3. Trigger a `devkit-upgrade` run (`workflow_dispatch`, since the schedule is weekly) in a repo that
   consumes the secret and confirm the App-token mint step succeeds.
4. Only after that is confirmed green, return to the App and **delete the old key**.
5. If rotating due to suspected compromise, delete the old key **immediately** in step 4 and audit
   the App's recent activity.
6. **While you hold the key, sweep `GET /app/installations` (JWT signed with
   `DEVKIT_UPGRADE_APP_PRIVATE_KEY`) and confirm every installation is one of ours** (`vig-os`,
   `exo-pet`). This is a **required** step, not optional cleanup: the App is public and carries no
   webhook, so with `events: []` there is no `installation` event to catch a stray install as it
   happens — this sweep, tied to key rotation, is the **only** compensating control for a public
   App's install page. A stray installation is inert while the key is sound; what it widens is the
   blast radius of a *key compromise*, from our orgs to our orgs plus whoever installed it.

## What this App must NOT be given

Keep the surface exactly at the permissions table above. In particular, do **not** grant or attach:

- **Organization Administration, Members, or Secrets** — this App's entire value is a narrow,
  repo-scoped write surface for one automated PR; any organization-level grant would make a public,
  install-anywhere App able to reconfigure an org that installs it, which is exactly the risk the
  narrow grant exists to avoid.
- **A webhook or webhook secret** — on any org. Nothing this App does is event-driven; a webhook adds
  no capability and only multiplies a shared secret across every install for nothing.
- **`issues:write` treated as load-bearing for the upgrade itself** — it is optional (see
  [Permissions](#permissions)); do not reason about this App as if losing that grant breaks the
  upgrade path, and do not widen anything else to compensate for an installation that lacks it.
- **Anything beyond `contents`, `pull_requests`, `workflows`, `issues` (write) and `metadata`
  (read)** — no Actions, Administration, Secrets, Variables, or Deployments scope unless a future
  issue records a concrete need. Widen only through a recorded decision, never opportunistically.
- **Repo-transfer or App-management scope** — not App-capable on GitHub anyway; these remain human
  owner actions.
