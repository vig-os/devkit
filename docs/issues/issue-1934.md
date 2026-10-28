---
type: issue
state: open
created: 2026-10-27T08:54:46Z
updated: 2026-10-27T10:59:32Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1934
comments: 3
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:12:59.824Z
---

# [Issue 1934]: [#1908 S7b: Remaining docs and scrub](https://github.com/vig-os/devkit/issues/1934)

Implementation sub-issue **S7b** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:*
  - `docs/DOWNSTREAM_RELEASE.md` (both copies): `runner-json` → lanes;
  - `docs/WORKFLOW_SECURITY.md`: the predicate and the trigger rules;
  - a new `docs/GOING_PUBLIC.md` (§10 checklist);
  - `.site/` and site-init docs in `docs/SOLO_ADOPTION.md`;
  - the CHANGELOG `### Deprecated` entry for both legacy knobs;
  - scrub the site-specific label and site names from the
    `tests/bats/init-workspace.bats` fixtures and the
    `tests/test_setup_toolchain_env.py` comments and docstrings. The `.vig-os`
    and `tests/test_ci_runner.py` fixture scrubs land in S1, which owns those
    files.
- *Files:* the docs named above, `CHANGELOG.md`, the bats fixture strings and
  `tests/test_setup_toolchain_env.py`.
- *Acceptance:*
  - the scrub target is the **site-specific runner label** used as today's
    example in the `MIGRATION.md` self-hosted section, plus the site, org and
    repo names in the comments next to it in the files listed above. Other org
    and repo names elsewhere are out of scope;
  - a `git grep` for that label returns nothing outside `docs/issues/`,
    `docs/pull-requests/` and the **released** sections of `CHANGELOG.md` and
    `assets/workspace/.devcontainer/CHANGELOG.md`. Released entries are never
    edited, per the changelog rules;
  - the names next to the label are checked by running S6's `site-leak-check`
    over the tree with the owner's site pattern file, so the names never
    appear in devkit;
  - docs lint passes.

Refs #1908
---

# [Comment #1]() by [gerchowl]()

_Posted on October 27, 2026 at 09:16 AM_

Docs item from the pre-mortem of S1 (#1937), for S7b. This is a limit of the design, not a code defect. For `pull_request` runs, both `ci.yml` and the resolve action are loaded from the merge ref, which a fork controls. So a hostile fork can delete the fork predicate or write a literal self-hosted label: the predicate only prevents *accidental* routing. The real controls are runner groups that aren't open to public repos, and the 'require approval for fork PR workflows' setting. ADR §7 presents these only as defence in depth. The docs (MIGRATION.md self-hosted section, and §7 via an Amendments entry) should state plainly that they're the primary control for public repos, and what to configure.

---

# [Comment #2]() by [gerchowl]()

_Posted on October 27, 2026 at 10:55 AM_

From the review of #1947 (S2): `docs/DOWNSTREAM_RELEASE.md` (~L488) and `assets/workspace/docs/DOWNSTREAM_RELEASE.md` (~L491) still say the ci-extension `runner-json` input is derived from `DEVKIT_CI_RUNNER`. S2 already fixed the same wording in the `ci-extension.yml` header. Include both in the S7b scrub.

---

# [Comment #3]() by [gerchowl]()

_Posted on October 27, 2026 at 10:59 AM_

Correction to my earlier comment, for S7b. Runner groups that exclude public repos are **not** the control to document: a site may deliberately allow public repos in its self-hosted runner groups. The docs should state the principle without naming any site:

- **Self-hosted security must come from runner-side checks and org approval settings, never from workflow content.** A fork controls `ci.yml` and the resolve action on `pull_request`, so anything in workflow content can be removed by the fork.
- The primary controls are, first, a runner-side job-start hook (e.g. `ACTIONS_RUNNER_HOOK_JOB_STARTED`, set by the runner operator rather than the repo) that reads the event payload and rejects jobs whose `head.repo` differs from `base.repo`, and second, the org setting "Require approval for fork pull request workflows" set to all external contributors.
- Runner-group visibility (private repos only) is an optional extra layer for sites that can use it.
- devkit's fork predicate is the **accident-prevention layer**: it routes fork PRs to hosted runners so they still get CI. It is not a security boundary.

MIGRATION.md (self-hosted section) and the ADR §7 Amendments entry should say this, and list what the operator must configure.


