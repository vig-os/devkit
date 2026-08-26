---
type: issue
state: closed
created: 2026-08-24T09:51:01Z
updated: 2026-08-26T13:06:05Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1562
comments: 1
labels: bug, priority:medium, area:workflow, effort:small, semver:patch
assignees: none
milestone: 1.11.1
projects: none
parent: none
children: none
synced: 2026-08-26T13:51:57.169Z
---

# [Issue 1562]: [[BUG] Suppress Claude Code session-link attribution in the workspace scaffold](https://github.com/vig-os/devkit/issues/1562)

## Description

Ship Claude Code attribution suppression in the downstream workspace template
(`assets/workspace/.claude/`), so no repo scaffolded from devkit emits a
`claude.ai` session link — or any other built-in AI attribution — into a commit
message or PR body.

## Problem Statement

Claude Code appends a session link to commits and PR bodies of **web and Remote
Control sessions**:

- commit trailer form — a `Claude-Session:` trailer holding a
  `https://claude.ai/code/session_…` URL
- PR-body form — a bare `https://claude.ai/code/session_…` footer, which a
  squash merge then folds into the merge commit message

This is governed by `attribution.sessionUrl`, which **defaults to `true` and is
a separate gate from `includeCoAuthoredBy`** — so a repo that already suppresses
the Co-Authored-By trailer still leaks the link. From the settings schema in
Claude Code 2.1.222:

```
attribution.commit     — "Attribution text for git commits, including any trailers.
                          Empty string hides attribution."
attribution.pr         — "Attribution text for pull request descriptions.
                          Empty string hides attribution."
attribution.sessionUrl — "Whether to append the claude.ai session link to commits and
                          PRs created from web or Remote Control sessions (default:
                          true). Set to false to omit the Claude-Session trailer and
                          PR-body link."
includeCoAuthoredBy    — "Deprecated: Use attribution instead."
```

Measured leak across the four orgs today: **10 PRs** carry the body footer, and
the trailer is already in merged `main` history in at least two repos
(`vig-os/devkit`, `exo-pet/org-config`).

A user-level `~/.claude/settings.json` fixes this on one workstation only.
**Cloud sessions — claude.ai/code, remote agents, `/code-review ultra` — run on
Anthropic infrastructure and never read the developer's home directory.** The
only configuration they see is what is committed in the repo, which makes the
devkit scaffold the single point that covers every repo, every org, and every
contributor.

## Proposed Solution

Add the attribution block to the scaffolded workspace `.claude/` settings:

```json
{
  "attribution": {
    "commit": "",
    "pr": "",
    "sessionUrl": false
  },
  "includeCoAuthoredBy": false
}
```

`includeCoAuthoredBy` is deprecated in favour of `attribution` but still read —
worth keeping as cheap insurance while both are honoured.

Open design question for whoever picks this up: `assets/workspace/.claude/`
currently ships `agent-models.toml`, `worktrees.json` and `skills/` but **no
`settings.json`**, while devkit's own root `.claude/settings.json` carries a
`permissions` block. So decide between:

1. a **managed** `assets/workspace/.claude/settings.json` (banner-stamped, synced
   by `scripts/sync_manifest.py`, regenerated on upgrade) — strongest guarantee,
   but it owns the whole file and would stomp any consumer `permissions` block; or
2. a **layered** split mirroring the justfile pattern already used here — managed
   attribution settings plus a preserved consumer-owned file — which costs more
   machinery but does not take ownership of consumer permissions.

Given the rule is absolute ("never, in any repo"), option 1 is the safer default
unless consumer-owned `permissions` in `.claude/settings.json` is already a
supported pattern in the wild.

## Alternatives Considered

- **User-level `~/.claude/settings.json`** — done on the maintainer's workstation
  (`vigo-nixos`, `modules/home/claude-config.nix`): `attribution` block plus
  `env.CLAUDE_CODE_SUPPRESS_SESSION_ATTRIBUTION = "1"`, which is a second,
  independent kill switch checked *before* `attribution.sessionUrl` and therefore
  survives an upstream rename of that key. Covers every local session on that
  machine, all orgs — but nothing running in the cloud, and nothing on any other
  contributor's machine. Not sufficient on its own.
- **`PreToolUse` guard hook** — also done on the same workstation: blocks a
  session link or AI-attribution trailer in `git commit` and in
  `gh pr create`/`gh pr edit` before the Bash tool runs. A good backstop against
  an upstream key rename, but it is a local hook, so it shares the same
  machine-scoped limitation.
- **Do nothing and clean up after the fact** — PR bodies are editable, but a
  trailer that reaches merged `main` needs a history rewrite. Prevention is much
  cheaper.

## Additional Context

- Verified against Claude Code **2.1.222**; the gate is
  `if (env.CLAUDE_CODE_SUPPRESS_SESSION_ATTRIBUTION) return null;` followed by
  `if (settings().attribution?.sessionUrl === false) return null;`.
- Existing offending history is out of scope here; recommendation is to strip the
  10 PR bodies with `gh pr edit --body-file` and leave the merged commits alone.

## Impact

Every repo scaffolded from devkit, across `vig-os`, `exo-pet`, `MorePET` and
`exoma-ch`. Backward compatible — the settings keys are additive and no consumer
behaviour changes other than the attribution text disappearing. Whether it is a
breaking change for consumers depends on which of the two options above is
chosen for file ownership.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 26, 2026 at 01:06 PM_

Resolved by #1567 (merged to dev): managed workspace-template .claude/settings.json ships attribution{commit:"",pr:"",sessionUrl:false} + includeCoAuthoredBy:false; devkit root settings carry the identical block, drift-gated by tests/test_attribution_settings.py. Consumers pick it up on their next devkit-upgrade after 1.11.1.

