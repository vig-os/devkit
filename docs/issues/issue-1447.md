---
type: issue
state: closed
created: 2026-08-12T09:09:30Z
updated: 2026-08-12T09:35:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1447
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:40.518Z
---

# [Issue 1447]: [[BUG] check-expirations consumer fragment still resolves through the project venv (uv run) instead of a store path](https://github.com/vig-os/devkit/issues/1447)

### Description

`check-expirations` is the last vig-utils hook whose **consumer** fragment still resolves its entry through the project venv:

```nix
consumer = _: {
  enable = true;
  name = "check-expirations";
  entry = "uv run check-expirations .trivyignore .vulnixignore";
  ...
};
```

`uv run <tool>` resolves against the **consumer's** project venv — but a consumer venv has no `vig-utils`, and many consumers have no `pyproject.toml` at all. This is the exact venv-resolution weakness #1434 was filed about.

After #1434 shipped the commit-message and agent-identity hooks as store-path fragments, `check-expirations` is now the odd one out: every other tool-naming consumer fragment (`nixfmt`, `statix`, `deadnix`, `just-fmt`, `gitleaks`, `pymarkdown`, and now `validate-commit-msg` / `prepare-commit-msg-strip-trailers` / `check-agent-identity`) resolves a `${pkgs.<tool>}/bin/…` store path.

### Steps to Reproduce

In a direnv consumer on flake-generated hooks with no `vig-utils` in its venv (or no `pyproject.toml`), inside the dev shell, trigger the hook by touching a `.trivyignore` / `.vulnixignore`. The entry cannot resolve.

### Expected Behavior

The consumer fragment resolves `${vigUtils}/bin/check-expirations`, exactly like the three hooks fixed in #1434, so the hook version follows the devkit pin the consumer bumps with `nix flake update vigos`.

### Actual Behavior

The fragment shells out to `uv run check-expirations`, which depends on consumer venv state that devkit does not control and that most consumers do not have.

### Additional Context

`nix/vig-utils.nix` already exists (extracted in #1434 so hook fragments can build vig-utils from an un-overlaid `pkgs`), so the mechanism is in place — this is applying the established pattern to the one fragment that was missed.

Note the `yaml` (portable, committed-runner) representation must stay `uv run`; only the `consumer` fragment changes. The drift gate (`tests/test_flake_hooks.py`) pins that, so `.pre-commit-config.yaml` must come out byte-identical.

### Impact

All direnv-mode consumers on generated hooks that carry a `.trivyignore` / `.vulnixignore`. Latent rather than loud: the hook is `files`-scoped, so it only fires when those files change. Pre-existing, not a regression.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 09:35 AM_

Fixed by #1449, merged to `release/1.8.0` as 3ac6a5c1 (ships in 1.8.0-rc2).

`check-expirations`'s `consumer` fragment now resolves `${import ./vig-utils.nix pkgs}/bin/check-expirations .trivyignore .vulnixignore`, matching the three hooks fixed in #1434. The `yaml` (portable, committed-runner) representation deliberately stays `uv run`; the `check` (hermetic) fragment already used a store path.

**Behavioral proof**: a plain consumer config built from an un-overlaid `pkgs` now carries

```
/nix/store/…-python3.14-vig-utils-0.1.0/bin/check-expirations .trivyignore .vulnixignore
```

and executing that store binary directly with `VIRTUAL_ENV` unset gives `Validated 32 exception(s) across 2 file(s)`, exit 0 — no project venv involved.

**The class is now closed, not just this instance.** Alongside the specific contract tests, `TestNoConsumerHookResolvesVigUtilsThroughTheVenv` reads the console-script list from `packages/vig-utils/pyproject.toml` (SSoT — no second list to maintain), walks all seven generated consumer configs, and fails any hook naming a vig-utils script that does not resolve `/nix/store/…`. A future hook added to `hookDefs` cannot reintroduce the defect. Verified to have teeth: on the pristine tree it failed listing all 7 shells.

Invariants held — drift gate (`.pre-commit-config.yaml` absent from the diff entirely, both `TestPortableRenderFidelity` tests green) and zero-hooks parity (identical `drvPath`).

Changelog entry went into the `## [1.8.0] - TBD` section rather than `## Unreleased`, matching #1443/#1444 — the changelog was frozen for 1.8.0 at 046ca547, so an Unreleased entry would have been stranded out of these release notes.

