---
type: issue
state: open
created: 2026-10-16T14:44:57Z
updated: 2026-10-16T14:44:57Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1898
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-17T06:49:13.947Z
---

# [Issue 1898]: [[BUG] dev shell's claude-code shadows the host's claude (version + auth wrapper) in every consumer repo](https://github.com/vig-os/devkit/issues/1898)

## What happens

`nix/devtools.nix` puts `claude-code` in the tool list every consumer's dev shell gets. With direnv, entering any consumer repo prepends that store path to PATH, so plain `claude` there runs the devkit-pinned claude-code instead of the host's.

Seen on a fleet host: sessions resumed inside consumer repos ran claude-code 2.1.283 from the dev shell, while the host provides 2.1.296/2.1.287 through a wrapper. That wrapper sets per-profile config and auth (it exports `CLAUDE_CODE_OAUTH_TOKEN` from the selected profile). The dev-shell binary bypasses it, so those sessions started **without any credentials**. A fresh shell in the same directory doesn't help, because the dev shell activates again. Shell functions that end in `command claude` (e.g. a `cld` alias for `--dangerously-skip-permissions`) resolve to the same shadowing binary.

## Why it's wrong

An agent CLI is host and seat tooling, like the editor or the terminal. It isn't a project build dependency:
- it carries per-user auth and profile state the dev shell knows nothing about;
- it moves fast, so a project-pinned copy is almost always older than the host's;
- it isn't needed to build, test or lint the project.

## Proposal

Drop `claude-code` (and any other agent CLI) from the dev-shell tool list. Keep it where it belongs:
- the home-environment module (`nix/home/claude.nix`), for people who use devkit to set up their machine;
- the devcontainer image, where there is no host install to shadow.

If a fallback is wanted for machines that have no claude at all, append it to PATH rather than prepending it, or make it opt-in per consumer.
