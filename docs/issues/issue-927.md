---
type: issue
state: open
created: 2026-07-08T11:23:40Z
updated: 2026-11-03T11:50:34Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/927
comments: 2
labels: discussion, area:workspace, area:workflow, effort:large
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:24:04.038Z
---

# [Issue 927]: [[DISCUSSION] Standardize org Claude config via a plugin + private marketplace (retire per-repo .claude/ copies)](https://github.com/vig-os/devkit/issues/927)

## Context

Since #626 made `.claude/` the SSoT here and `install.sh` copies the skill tree into downstream repos, the copies drift. Concrete evidence (July 2026 audit across the workspace):

- Five repos still run **1.5–4-month-old** `.cursor` scaffolds (pre-0.4 payloads: `cursor-agent --yolo`, Cursor-era model names, missing skills). *(These `.cursor` trees are being deleted separately.)*
- The canonical skills carried ~19 broken `../../rules/*.mdc` links, duplicated `## Delegation` sections, a skill-name mismatch, and a PR-title contradiction — all fixed in #917, but the file-copy model means every fix has to re-propagate by hand.
- Org **prose** conventions (commit format, changelog, TDD, confidentiality) are copied 3–5× down the CLAUDE.md hierarchy, against our own "single source of truth" rule.

The file-copy distribution model is the root cause. Claude Code's supported org pattern is a **plugin distributed through a marketplace repo**, installed once per machine instead of vendored per repo.

## Proposal

Bundle our Claude config into one **plugin** and distribute it from a **private marketplace repo** (proposed home: **`vig-os/org-config`** — private, already has a `.claude/`, named for exactly this; alternative: a dedicated `vig-os/claude-plugin`). Teammates run `/plugin marketplace add vig-os/org-config` once, then `/plugin install`; updates ship via push + `/plugin update`.

A plugin can standardize all four layers:

| Layer | Today | With the plugin |
|---|---|---|
| **Skills** (`ci_check`, `pr_*`, `worktree_*`) | copied per repo, drift | one versioned copy |
| **Hooks** (e.g. block `--no-verify` / AI-attribution) | none shared | `hooks/hooks.json`, enforced for everyone |
| **Agents** | none shared | shipped in the bundle |
| **Prose conventions** | copied down every CLAUDE.md level | one canonical `CONVENTIONS.md`, repos defer to it |

A reference PreToolUse commit-guard hook (blocks `git commit --no-verify`/`-n` and `Co-Authored-By: Claude`/AI trailers) already exists and works; it's the natural seed for `hooks/hooks.json`.

### CLAUDE.md half

Keep one canonical `CONVENTIONS.md` in the marketplace repo; make each repo's CLAUDE.md **thin** — repo-specific facts only, plus a pointer to the canonical conventions. Repo-level files stay the source of truth for their own repo; they just stop restating org rules.

## Decisions to resolve as part of this (deferred from #917 on purpose — they need team eyes)

1. **Retire skills that overlap built-ins?** `code_debug` (≈ `/debug`) and `code_verify` (≈ `/verify`, minus our `just` command list). Rebase `code_review` on the built-in reviewer + our project checklist?
2. **Cut the `inception_*` family** (~900 lines of largely generic system-design/interview boilerplate) or move it out of the per-repo sync into an on-demand location?
3. **Dead config:** `worktrees.json` (unread Cursor leftover) and `agent-models.toml` (not a Claude Code file — only one shell script greps it). Drop from the synced payload, or keep and document?
4. **Re-enable model invocation** for the converted ambient rules (`tdd`, `branch-naming`, `subagent-delegation`) — currently `disable-model-invocation: true`, so they can never auto-fire.

## Migration path (incremental, low-risk)

1. Merge #917 (package clean skills, not the broken-link ones).
2. Add `.claude-plugin/marketplace.json` + `hooks/hooks.json` (seed from the reference guard) + move the repaired skills into the marketplace repo; add `CONVENTIONS.md`.
3. Pilot on one repo; confirm skills + hook fire.
4. Retire `install.sh`'s `.claude/` copying; delete per-repo skill copies.
5. Thin the repo CLAUDE.md files to defer to `CONVENTIONS.md`.

## Caveat (GitHub Free plan)

Plugin hooks run **client-side** and a teammate can disable the plugin — so they're consistency + defense-in-depth, not a hard gate. The real gates stay each repo's pre-commit hooks + CI. Same trust model we already rely on (no server-side branch protection on Free).

## Open questions for the team

- `vig-os/org-config` vs a dedicated `vig-os/claude-plugin` as the marketplace home?
- Scope of the built-in-overlap cleanup (decisions 1–2) — how aggressive?
- Do we want shared **agents** in v1, or skills + hooks + conventions first?

Refs: #626
---

# [Comment #1]() by [gerchowl]()

_Posted on July 8, 2026 at 03:05 PM_

yes - it's always a question where/how things should live

there is also claude config nix flake - which then in turn makes adding plugins/mcps/.. manually ephemeral ..

---

# [Comment #2]() by [gerchowl]()

_Posted on November 3, 2026 at 11:50 AM_

Consumer data point (`exoma-ch/ravmatic`, 1.18.0, direnv): `.claude/settings.json` is devkit-managed (overwritten on upgrade, checked by scaffold drift). So a consumer has **no committed place for a team-wide Claude Code config**. That includes a permission allowlist (`Bash(just *)`, `Bash(gh pr *)`, `Bash(nix develop *)`) and a SessionStart hook that warns when the session is outside the dev shell, which the git hooks require. The only option left is each contributor's own `.claude/settings.local.json`. A preserved `.claude/settings.project.json`, merged at scaffold time like `.gitignore.project`, or the plugin route discussed here, would close that.

