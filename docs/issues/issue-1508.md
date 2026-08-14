---
type: issue
state: closed
created: 2026-08-14T07:58:48Z
updated: 2026-08-14T08:48:50Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1508
comments: 1
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.10.0
projects: none
parent: none
children: none
synced: 2026-08-14T16:05:14.415Z
---

# [Issue 1508]: [[BUG] promote: the floating-tag push authenticates as the Actions identity (checkout extraheader overrides the App token) — unreachable from every current consumer, so #1377 was never exercised](https://github.com/vig-os/devkit/issues/1508)

### Description

`promote-release.yml`'s `floating-tags` job pushes tags with the Release App
token embedded in the push URL (`promote-release.yml:669`), while its
`actions/checkout` (`:618`) persists the default `GITHUB_TOKEN` as
`http.https://github.com/.extraheader`. **The extraheader outranks URL
userinfo**, so the push authenticates as the Actions identity — and the job
declares `permissions: contents: read` (`:607-609`), which cannot push a ref at
all.

This is the same defect as #1503 in a second job. #1503 is confirmed live (403
`denied to github-actions[bot]` on `vig-os/org-config`); the precedence itself
is now reproduced outside CI, against a **private** repo with the credential
helper disabled:

| | setup | result |
|---|---|---|
| A | valid token in extraheader, clean URL | SUCCESS — the header authenticates |
| C | bogus token in URL userinfo, no extraheader | FAIL — the bogus token really is bad |
| B | valid extraheader **+ bogus userinfo** | **SUCCESS — extraheader wins, userinfo ignored** |

**This has never executed anywhere.** The `git push` form arrived in e76c31da
("fix(workflows): move floating tags via git push with explicit App token",
`Refs: #1377`), first released in **1.7.0**. Only two consumers enable floating
tags — `vig-os/commit-action` and `vig-os/sync-issues-action`, both
`DEVKIT_FLOATING_TAGS=major,minor` — and both are still pinned to
`DEVKIT_VERSION=1.6.0`. devkit's own promote workflow has no floating-tags job.
So every successful floating-tag move on record ran the *pre-1.7.0* REST
implementation (`gh api PATCH /git/refs/tags/…`), where `gh` consumes `GH_TOKEN`
directly and no checkout credentials are involved.

**Upgrading those two repos would therefore be a regression, not a fix.**

- Today (1.6.0, REST): moves work; only the *first* creation of a new floating
  level fails — that is #1157, and the `POST /git/refs` ruleset denial is what
  #1377 set out to fix.
- After ≥1.7.0 (push): the App token is ignored, the push runs as the Actions
  token under `contents: read`, so **even the moves that work today would
  break**.

Which means **#1377 likely does not fix #1157**: it replaced a REST call the
ruleset denies with a push that authenticates as the wrong identity. Nobody has
noticed because no floating-tag consumer has adopted 1.7.0+.

### Steps to Reproduce

1. A consumer with `DEVKIT_FLOATING_TAGS` set (e.g. `major,minor`) on devkit
   **≥ 1.7.0** — no such repo exists today; `commit-action` and
   `sync-issues-action` are both on 1.6.0.
2. Run the release train through to `promote-release.yml` on a final release.
3. Watch the `Move floating tags` job, step *Move floating major/minor tags*.

Evidence for the surrounding claims, all on the 1.6.0 (REST) path:

- `vig-os/commit-action` run
  [30994674616](https://github.com/vig-os/commit-action/actions/runs/30994674616)
  (2026-08-05, v0.3.2) — `Move floating tags` **success**:
  `Moved floating tag v0 -> 0361e9aa…`, `Moved floating tag v0.3 -> 0361e9aa…`.
  Both refs still point there.
- `vig-os/sync-issues-action` run
  [31186320919](https://github.com/vig-os/sync-issues-action/actions/runs/31186320919)
  (2026-08-07, v0.5.0) — `Moved floating tag v0` succeeded, then the job exited 1
  **creating** `v0.5` (the #1157 denial). `refs/tags/v0.5` exists on the remote
  today, created by hand per the step's own remediation message.

### Expected Behavior

The floating-tag push authenticates as the Release App — the identity the Tag
ruleset grants a bypass to — so both moving an existing level and creating a new
one succeed, and #1157 is actually closed rather than re-expressed as a
different denial.

### Actual Behavior

Unknown in production, because the code path has never run. By construction it
pushes as the Actions identity under `contents: read`, which is refused before
the ruleset is even consulted. The identical construction is confirmed failing
in `reset-sync-mirror` (#1503).

### Environment

- **Devkit version**: 1.7.0 onwards (introduced by e76c31da, `Refs: #1377`);
  current `dev` still carries it at `promote-release.yml:669`
- **Affected consumers**: `vig-os/commit-action`, `vig-os/sync-issues-action`
  (the only two with `DEVKIT_FLOATING_TAGS` set) — both on `DEVKIT_VERSION=1.6.0`,
  so both are *blocked* from upgrading until this is fixed
- **Checkout**: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1)
- **Job permissions**: `contents: read`, `packages: read`

### Additional Context

Third instance of one shape: automation that is green-or-plausible because it has
never executed against a live repository in that configuration (#1479, #1502,
#1503). Here it is stronger — the job is not merely untested, it is *unreachable*
from every current consumer, so CI can never surface it. A deliberate rehearsal
target for mirror-mode and floating-tag promote would catch this class.

Note the fix ordering: this must land **before** `commit-action` /
`sync-issues-action` adopt 1.7.0+, otherwise their working tag moves regress.

### Possible Solution

Apply the #1503 shape (PR #1507): generate the Release App token **before**
`actions/checkout` and pass it as `token:` to the checkout, then push to `origin`
with no URL userinfo. That authenticates every git operation as the App and keeps
`contents: read` for the Actions token, which is the point — the job's identity
model should not be "fixed" by granting `contents: write`.

Alternatives, both worse: `persist-credentials: false` leaves the job's `git
fetch` unauthenticated (fine for a public consumer, broken for a private one), and
`git -c http.extraheader= push …` fixes only the line it is written on.

Once fixed, verify the #1157 case specifically — creating a floating level that
does not yet exist — since that is the scenario #1377 targeted and the one still
requiring a manual workaround today.

Refs #1157, #1377, #1503.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 14, 2026 at 08:48 AM_

Fixed on `dev` in #1509 (`fc95ed32`).

**What shipped.** `Generate release app token` moves before `Checkout repository` and checkout takes the token, so the credentials git actually uses are the App's. `REMOTE_URL` is gone — the shallow tag fetch and the force-push both use `origin`. `contents: read` stays, with a comment saying why granting `contents: write` would be the wrong fix.

**A test was asserting the defect.** `test_move_tag_force_pushes_with_explicit_app_token` pinned `x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}` in the script — it verified the token was *written into the URL*, which is exactly the thing that never takes effect. That is a large part of why #1377 read as done. Replaced with pins on the ordering, the checkout token, the absence of any URL userinfo in the job, and the read-only Actions permission.

**The move script now runs in tests.** `tests/test_floating_tag_move.py` executes the step's real bash against a throwaway `file://` remote with `gh` stubbed from that same remote: creation (the #1157 case), move, idempotent skip, annotated-tag peel, refused push still failing loud with its remediation annotation, unknown-level warning. Identity itself can't be reproduced locally — a local remote has no auth — so that stays pinned structurally.

**Two things this does not settle.**

1. **#1377's premise is still unproven in production.** That the App is a bypass actor for `git push` where it is not for `POST /git/refs` was never tested against a live ruleset, because the push never ran as the App. First real confirmation will be the next new floating level on `commit-action` or `sync-issues-action` after they adopt this.
2. **The upgrade those two repos were blocked on is now unblocked.** On 1.6.0 their tag moves work and only first creation fails (#1157); on 1.7.0–1.9.x the push ran as the wrong identity, so moves would have broken too. Worth watching their first promote after adoption.

Left deliberately untouched: `Cleanup git RC tags` still builds an `x-access-token:` URL for a `git ls-remote` in both promote copies. The token is ignored there as well, but it is a read that succeeds under either identity and its ref deletions go through `gh api -X DELETE` correctly — misleading dead weight, not a defect.

