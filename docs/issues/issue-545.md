---
type: issue
state: open
created: 2026-05-15T13:50:24Z
updated: 2026-05-15T13:50:24Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/545
comments: 0
labels: feature, priority:medium, area:image, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-16T05:32:49.904Z
---

# [Issue 545]: [[FEATURE] Bake agent-CLI toolkit + Claude Code into image (rg/fd/bat/eza/delta/lazygit/zoxide/starship/freeze/expect/nvim + IS_SANDBOX=1)](https://github.com/vig-os/devcontainer/issues/545)

### Description

Bundle the modern-CLI + TUI-debug + Claude Code toolkit into the devcontainer image so AI-assisted development sessions land in a fully-equipped environment without per-project tool installs.

### Problem Statement

Claude / cursor-agent sessions inside the devcontainer hit the same gaps repeatedly:

1. **Modern CLI absent.** `rg`/`fd` (which agents reach for on every code search), `bat`/`eza`/`delta` (pretty inspection), `lazygit` (git TUI), `zoxide`/`starship` (navigation/prompt) — none in the image. Agents fall back to slower POSIX tools or fail outright.
2. **TUI debugging tooling absent.** Agents working with TUI apps (k9s, htop, vim, etc.) need `tmux capture-pane` for screen sampling, `expect` for prompt automation, `freeze` for rendering colored output as PNG (claude reads images natively). None present.
3. **Claude Code itself not baked.** Each container session starts with no claude binary; first launch requires `npm install` or `curl install.sh | bash` (~20s) every time.
4. **`--dangerously-skip-permissions` blocked under root.** Claude refuses with "uid 0" check unless `IS_SANDBOX=1`. Container is the trust boundary; this should be set globally.
5. **No `cc` / `cld` aliases.** Users repeat `claude --dangerously-skip-permissions` constantly.

### Proposed Solution

Single Containerfile commit that adds:

**apt block extension** (TUI + modern CLI essentials):
- `expect`, `neovim`, `ripgrep`, `fd-find`, `bat`, `fzf`
- Symlinks `/usr/local/bin/{fd,bat}` → Debian's `fdfind`/`batcat`

**Binary release downloads** (not in apt for bookworm):
- `eza`, `delta`, `lazygit`, `zoxide`, `starship`, `charm-freeze`

**Claude Code baked in:**
- Install via official installer with 3-attempt retry (mirrors cursor-agent pattern)
- Symlinked to `/usr/local/bin/claude`
- `ENV IS_SANDBOX=1` — bypasses uid-0 check for `--dangerously-skip-permissions` (container = trust boundary, this is the documented escape hatch)
- Aliases `cc=claude` and `cld='claude --dangerously-skip-permissions'` in `/root/.bashrc`

### Validation

Image builds (linux/arm64); all 14 added tools resolve on PATH; `IS_SANDBOX=1` set; aliases written. Image size delta ~+200MB.

### Out of Scope

- Tailscale (separate issue, in-flight)
- Claude Code auth injection (separate issue, in-flight)
- ZSH integration / shell hooks (defer)

### Changelog Category

Added
