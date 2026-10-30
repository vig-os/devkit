---
type: issue
state: open
created: 2026-10-30T00:19:17Z
updated: 2026-10-30T00:19:17Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1974
comments: 0
labels: chore
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-30T08:26:25.287Z
---

# [Issue 1974]: [agent CLI opt-in: test and docs follow-ups from #1967 reviews](https://github.com/vig-os/devkit/issues/1974)

Follow-ups from the reviews of PR #1968 and its 1.18.1 carry, PR #1972 (#1967). None of them blocks.

1. **The image's `claude` has no test.** It used to be covered by the image test that reads `devShellTools` (`tests/test_image.py`). `claude` has left that list, and `agentCliPolicy` doesn't cover the image, so the CHANGELOG claim that the container image keeps the CLI is untested. The code itself is correct (`imageTools ++ agentTools pkgs`). Add an eval-level assertion for the image's tool set.
2. **The docs' "same fast-mover pin" claim is conditional.** NIX.md says both options use the same pin. That only holds when the caller's `pkgs` has `overlays.default` applied, as the scaffold does. A raw `mkProjectShell` consumer gets the stable `claude-code`, or an unfree error. Document the condition.
3. **The Rust guard is missing on the 1.18.x line.** On `main`/1.18.x, `withAgentCli` is tested only through `mkProjectShell`, because the Rust fixture (`templates/rust`) doesn't exist there. dev has the guard. No action is needed unless a further 1.18.x patch touches `mk-rust-project.nix`.

Refs: #1967
