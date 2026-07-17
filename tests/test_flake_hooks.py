"""Fidelity gate for the flake-defined pre-commit hook set (issue #883).

``nix/hooks.nix`` is the single definition of the pre-commit hook set. It
renders three artifacts:

1. the sandbox-pure ``checks.pre-commit`` gate (git-hooks.nix + prek),
2. the PATH-portable runner config — the committed ``.pre-commit-config.yaml``,
3. the scaffold template copy (``assets/workspace/.pre-commit-config.yaml``).

The committed YAML files stay committed (PATH-portable, no store-path churn —
see docs/NIX.md), so this module is the drift gate: it evaluates the portable
render from the flake (``nix eval .#lib.hooksPortable``) and asserts it is
data-identical to the committed files — every hook id, args, files, excludes
and stages. Any hand edit to either YAML that is not mirrored in
``nix/hooks.nix`` (or vice versa) fails CI here.

It also covers the consumer surface: ``mkProjectShell``'s ``hooks`` /
``hooksExcludes`` arguments (per-hook toggle/override, custom hooks, global
excludes) and the zero-hooks-arg parity guarantee (no generation side effects
unless a consumer opts in).

Refs: #883
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

# Repository root (two levels up: tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

ROOT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
SCAFFOLD_CONFIG = REPO_ROOT / "assets" / "workspace" / ".pre-commit-config.yaml"

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None,
    reason="nix is not installed; flake hook fidelity tests require Nix",
)


def _nix_env() -> dict[str, str]:
    """Environment for nix invocations with flakes enabled and the public cache."""
    env = os.environ.copy()
    env.setdefault(
        "NIX_CONFIG",
        "experimental-features = nix-command flakes\n"
        "extra-substituters = https://vig-os.cachix.org\n"
        "extra-trusted-public-keys = "
        "vig-os.cachix.org-1:yoOYRi3bvnM6ThxO0joLt7vtzhTfkq3r6jykeUMg7Bk=",
    )
    return env


def _run_nix(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["nix", *args],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=timeout,
        cwd=REPO_ROOT,
    )


# The only top-level keys the flake render emits. Anything else in a
# committed YAML (e.g. a hand-added ``fail_fast: true``) is drift the
# per-hook comparison would silently miss, so _normalize surfaces it.
KNOWN_TOP_LEVEL_KEYS = frozenset({"exclude", "default_language_version", "repos"})


def _normalize(config: dict[str, Any]) -> dict[str, Any]:
    """Flatten a pre-commit config into comparable, order-independent data.

    Returns ``{"exclude", "default_language_version", "unexpected_top_level",
    "hooks"}`` where ``hooks`` maps each hook id to its full dict (plus the
    owning ``repo`` and ``rev``), so repo-block grouping and ordering
    differences between the committed YAML and the flake render never mask
    (or fake) a real drift, and ``unexpected_top_level`` lists any top-level
    key outside the rendered schema.
    """
    hooks: dict[str, Any] = {}
    for repo_block in config.get("repos", []):
        for hook in repo_block.get("hooks", []):
            entry = dict(hook)
            entry["repo"] = repo_block["repo"]
            if "rev" in repo_block:
                entry["rev"] = repo_block["rev"]
            hook_id = entry.pop("id")
            assert hook_id not in hooks, f"duplicate hook id: {hook_id}"
            hooks[hook_id] = entry
    return {
        "exclude": config.get("exclude"),
        "default_language_version": config.get("default_language_version"),
        "unexpected_top_level": sorted(set(config) - KNOWN_TOP_LEVEL_KEYS),
        "hooks": hooks,
    }


def _diff_hooks(rendered: dict[str, Any], committed: dict[str, Any]) -> str:
    """Human-readable normalized diff (empty string == no drift)."""
    lines: list[str] = []
    for key in ("exclude", "default_language_version", "unexpected_top_level"):
        if rendered[key] != committed[key]:
            lines.append(
                f"{key}: rendered={rendered[key]!r} committed={committed[key]!r}"
            )
    all_ids = sorted(set(rendered["hooks"]) | set(committed["hooks"]))
    for hook_id in all_ids:
        r = rendered["hooks"].get(hook_id)
        c = committed["hooks"].get(hook_id)
        if r == c:
            continue
        if r is None:
            lines.append(f"{hook_id}: only in committed YAML: {c!r}")
        elif c is None:
            lines.append(f"{hook_id}: only in flake render: {r!r}")
        else:
            for field in sorted(set(r) | set(c)):
                if r.get(field) != c.get(field):
                    lines.append(
                        f"{hook_id}.{field}: rendered={r.get(field)!r} committed={c.get(field)!r}"
                    )
    return "\n".join(lines)


@pytest.fixture(scope="module")
def rendered_portable() -> dict[str, Any]:
    """The PATH-portable render of the hook set, straight from the flake."""
    result = _run_nix(["eval", "--json", ".#lib.hooksPortable"])
    assert result.returncode == 0, (
        "nix eval .#lib.hooksPortable failed (is nix/hooks.nix wired into the flake?):\n"
        + result.stderr
    )
    return json.loads(result.stdout)


class TestPortableRenderFidelity:
    """The one Nix definition renders exactly the committed YAML artifacts."""

    def test_normalize_flags_unexpected_top_level_keys(self) -> None:
        """A hand-added top-level key (e.g. fail_fast) cannot pass unnoticed."""
        sneaky = {"repos": [], "fail_fast": True}
        clean = {"repos": []}
        assert _normalize(sneaky)["unexpected_top_level"] == ["fail_fast"]
        assert _diff_hooks(_normalize(clean), _normalize(sneaky)) != ""

    def test_runner_render_matches_committed_config(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """Zero normalized diff between the flake render and the root YAML."""
        committed = _normalize(yaml.safe_load(ROOT_CONFIG.read_text()))
        rendered = _normalize(rendered_portable["runner"])
        diff = _diff_hooks(rendered, committed)
        assert diff == "", (
            f"nix/hooks.nix drifted from .pre-commit-config.yaml:\n{diff}"
        )

    def test_scaffold_render_matches_scaffold_config(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """Zero normalized diff between the flake render and the scaffold copy."""
        committed = _normalize(yaml.safe_load(SCAFFOLD_CONFIG.read_text()))
        rendered = _normalize(rendered_portable["scaffold"])
        diff = _diff_hooks(rendered, committed)
        assert diff == "", (
            "nix/hooks.nix (scaffold profile) drifted from "
            f"assets/workspace/.pre-commit-config.yaml:\n{diff}"
        )

    def test_scaffold_render_is_subset_of_runner(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """Every scaffold hook is the identical runner hook (one definition)."""
        runner = _normalize(rendered_portable["runner"])["hooks"]
        scaffold = _normalize(rendered_portable["scaffold"])["hooks"]
        for hook_id, hook in scaffold.items():
            assert hook == runner.get(hook_id), (
                f"scaffold hook {hook_id} diverges from runner"
            )


class TestCheckJsonExcludesJsoncBanners:
    """check-json skips the `//`-bannered JSONC scaffold files (#1053).

    The three JSONC scaffold files carry a `//` provenance banner (#1053) that
    VS Code and the devcontainer CLI accept but check-json's strict parser
    rejects. nix/hooks.nix excludes them from every check-json surface; both
    committed YAMLs must carry the rendered exclude.
    """

    def test_runner_and_scaffold_exclude_the_jsonc_paths(self) -> None:
        for cfg in (ROOT_CONFIG, SCAFFOLD_CONFIG):
            hooks = _normalize(yaml.safe_load(cfg.read_text()))["hooks"]
            exclude = hooks["check-json"].get("exclude", "")
            assert ".devcontainer/devcontainer\\.json" in exclude, cfg
            assert ".vscode/settings\\.json" in exclude, cfg
            assert "code-workspace" in exclude, cfg

    def test_strict_json_is_still_checked(self) -> None:
        """renovate.json and friends stay under strict check-json (no exclude)."""
        for cfg in (ROOT_CONFIG, SCAFFOLD_CONFIG):
            hooks = _normalize(yaml.safe_load(cfg.read_text()))["hooks"]
            exclude = hooks["check-json"].get("exclude", "")
            assert "renovate" not in exclude, cfg


class TestCommitMsgHookContract:
    """The commit-message validator's shipped argv (Refs #1019).

    Scope vocabulary is deliberately *not* an allowlist: the standard
    (``docs/COMMIT_MESSAGE_STANDARD.md``) defines a scope as free-form
    "alphanumeric and hyphens only", which the validator's subject regex
    already enforces. Pinning ``--scopes`` here re-introduces the drift that
    rejected ~49% of the scopes actually in use, and would break the bots the
    moment Renovate learns a new ecosystem.
    """

    def test_validate_commit_msg_pins_no_scope_allowlist(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        args = _normalize(rendered_portable["runner"])["hooks"]["validate-commit-msg"][
            "args"
        ]
        assert "--scopes" not in args, (
            "validate-commit-msg pins a --scopes allowlist; scope is free-form "
            "per docs/COMMIT_MESSAGE_STANDARD.md (Refs #1019)"
        )

    def test_validate_commit_msg_still_enforces_types_and_refs(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """Dropping the scope allowlist must not weaken the rest of the rule."""
        args = _normalize(rendered_portable["runner"])["hooks"]["validate-commit-msg"][
            "args"
        ]
        assert "--types" in args
        assert "--refs-optional-types" in args
        assert "--blocked-patterns" in args

    def test_commit_msg_hooks_are_scaffolded(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """Consumers get the commit-msg stage they are already wired to run.

        The scaffolded ``.githooks/commit-msg`` shells out to
        ``prek run --hook-stage commit-msg``; without these hooks in the
        consumer render that shim is a no-op, and every scaffolded repo ships
        a COMMIT_MESSAGE_STANDARD.md it cannot enforce. Refs #1019.

        ``prepare-commit-msg-strip-trailers`` is scaffolded alongside it on
        purpose: it strips agent trailers *before* the validator's blocklist
        gate sees them. Shipping the validator alone would turn an
        auto-repaired commit into a hard failure in consumer repos.
        """
        scaffold = _normalize(rendered_portable["scaffold"])["hooks"]
        assert "validate-commit-msg" in scaffold
        assert "prepare-commit-msg-strip-trailers" in scaffold
        assert scaffold["validate-commit-msg"]["stages"] == ["commit-msg"]

    def test_agent_identity_hook_is_scaffolded(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """Consumers guard the commit *author*, not only the message. Refs #1031.

        ``check-agent-identity`` is the only hook of the #163 pipeline that
        catches ``git commit --author="Claude <...>"``; the two commit-msg
        hooks scaffolded in #1026 guard the message text alone. Without this
        hook in the consumer render, a scaffolded repo rejects an
        AI-attributed *message* while accepting an AI-authored *commit* — the
        exact false guarantee its COMMIT_MESSAGE_STANDARD.md promises against.
        """
        scaffold = _normalize(rendered_portable["scaffold"])["hooks"]
        assert "check-agent-identity" in scaffold


@pytest.fixture(scope="module")
def consumer_config() -> dict[str, Any]:
    """Build the generated config for a customized consumer shell."""
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{ inherit system; }};
      shell = flake.lib.mkProjectShell {{
        inherit pkgs;
        hooks = {{
          typos.enable = false;
          detect-private-keys.excludes = [ "worker/src/index\\\\.ts" ];
          my-data-check = {{
            enable = true;
            name = "my-data-check";
            entry = "./scripts/check-dat.sh";
            files = "\\\\.dat$";
            language = "system";
          }};
        }};
        hooksExcludes = [ "^data/stopping/" ];
      }};
    in
    shell.hooksConfigFile
    """
    result = _run_nix(
        ["build", "--impure", "--no-link", "--print-out-paths", "--expr", expr],
        timeout=1800,
    )
    assert result.returncode == 0, (
        "building the generated hook config failed:\n" + result.stderr
    )
    # The generated file is JSON preceded by "# …" comment lines; YAML is
    # a JSON superset that treats them as comments, so parse with yaml.
    return yaml.safe_load(Path(result.stdout.strip()).read_text())


@pytest.fixture(scope="module")
def gitleaks_enabled_config() -> dict[str, Any]:
    """Generated config for a consumer that opts into the gitleaks hook (#1172)."""
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{ inherit system; }};
      shell = flake.lib.mkProjectShell {{
        inherit pkgs;
        hooks = {{
          gitleaks.enable = true;
        }};
      }};
    in
    shell.hooksConfigFile
    """
    result = _run_nix(
        ["build", "--impure", "--no-link", "--print-out-paths", "--expr", expr],
        timeout=1800,
    )
    assert result.returncode == 0, (
        "building the gitleaks-enabled hook config failed:\n" + result.stderr
    )
    return yaml.safe_load(Path(result.stdout.strip()).read_text())


class TestGitleaksOptInHook:
    """gitleaks is an opt-in, default-disabled consumer hook (#1172).

    It carries no runner/scaffold render and no sandbox-gate profile (devkit's
    own lanes never run it — there is no repo-root ``.gitleaks.toml`` tuning),
    and it stays off the consumer surface until a consumer sets
    ``gitleaks.enable = true``.
    """

    def test_gitleaks_absent_from_runner_render(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """devkit's own committed .pre-commit-config.yaml never runs gitleaks."""
        assert "gitleaks" not in _normalize(rendered_portable["runner"])["hooks"]

    def test_gitleaks_absent_from_scaffold_render(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """The scaffolded consumer config does not ship gitleaks."""
        assert "gitleaks" not in _normalize(rendered_portable["scaffold"])["hooks"]

    def test_gitleaks_disabled_by_default_on_consumer_surface(
        self, consumer_config: dict[str, Any]
    ) -> None:
        """A consumer that does not opt in gets no gitleaks hook."""
        assert "gitleaks" not in _normalize(consumer_config)["hooks"]

    def test_gitleaks_rendered_when_enabled(
        self, gitleaks_enabled_config: dict[str, Any]
    ) -> None:
        """Opting in renders gitleaks with the v8.19+ pre-commit invocation."""
        hooks = _normalize(gitleaks_enabled_config)["hooks"]
        assert "gitleaks" in hooks, "gitleaks.enable = true did not render the hook"
        entry = hooks["gitleaks"]["entry"]
        assert "gitleaks git --pre-commit --staged --redact --verbose" in entry
        assert hooks["gitleaks"]["language"] == "system"
        assert hooks["gitleaks"]["pass_filenames"] is False


@pytest.fixture(scope="module")
def default_shellhook() -> str:
    """The shellHook of the flake's own default dev-shell (``hooks = null``)."""
    result = _run_nix(["eval", "--raw", ".#devShells.x86_64-linux.default.shellHook"])
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture(scope="module")
def opted_in_shellhook() -> str:
    """The shellHook of a minimally opted-in (``hooks = { }``) shell."""
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{ inherit system; }};
      shell = flake.lib.mkProjectShell {{
        inherit pkgs;
        hooks = {{ }};
      }};
    in
    shell.shellHook
    """
    result = _run_nix(["eval", "--impure", "--raw", "--expr", expr])
    assert result.returncode == 0, result.stderr
    return result.stdout


class TestConsumerHooksSurface:
    """mkProjectShell's ``hooks`` / ``hooksExcludes`` consumer surface."""

    def test_custom_hook_is_rendered(self, consumer_config: dict[str, Any]) -> None:
        hooks = _normalize(consumer_config)["hooks"]
        assert "my-data-check" in hooks
        assert hooks["my-data-check"]["entry"] == "./scripts/check-dat.sh"

    def test_base_hook_can_be_disabled(self, consumer_config: dict[str, Any]) -> None:
        assert "typos" not in _normalize(consumer_config)["hooks"]

    def test_base_hooks_are_present(self, consumer_config: dict[str, Any]) -> None:
        hooks = _normalize(consumer_config)["hooks"]
        for expected in (
            "check-yaml",
            "ruff",
            "shellcheck",
            "yamllint",
            "no-commit-to-branch",
        ):
            assert expected in hooks, (
                f"base hook {expected} missing from generated config"
            )

    def test_per_hook_excludes_merge(self, consumer_config: dict[str, Any]) -> None:
        hooks = _normalize(consumer_config)["hooks"]
        assert "worker/src/index\\.ts" in hooks["detect-private-keys"]["exclude"]

    def test_global_excludes_merge(self, consumer_config: dict[str, Any]) -> None:
        exclude = consumer_config["exclude"]
        assert "^data/stopping/" in exclude
        # The base excludes stay active alongside the consumer additions.
        assert ".github_data" in exclude


class TestZeroHooksParity:
    """Without a ``hooks``/``hooksExcludes`` opt-in nothing changes."""

    def test_zero_hooks_shell_matches_default_devshell(self) -> None:
        """mkProjectShell without hooks args is the flake's own dev-shell (same drv)."""
        expr = f"""
        let
          flake = builtins.getFlake "path:{REPO_ROOT}";
          system = builtins.currentSystem;
          pkgs = import flake.inputs.nixpkgs {{
            inherit system;
            overlays = [ flake.overlays.default ];
            config.allowUnfree = true;
          }};
        in {{
          default = flake.devShells.${{system}}.default.drvPath;
          zeroHooks = (flake.lib.mkProjectShell {{ inherit pkgs; }}).drvPath;
        }}
        """
        result = _run_nix(["eval", "--impure", "--json", "--expr", expr])
        assert result.returncode == 0, result.stderr
        paths = json.loads(result.stdout)
        assert paths["default"] == paths["zeroHooks"]

    def test_zero_hooks_shellhook_has_no_generation(self) -> None:
        """The default shellHook carries no git-hooks.nix installation script."""
        result = _run_nix(
            ["eval", "--raw", ".#devShells.x86_64-linux.default.shellHook"],
        )
        assert result.returncode == 0, result.stderr
        assert ".pre-commit-config.yaml" not in result.stdout
        assert "git-hooks.nix" not in result.stdout

    def test_opted_in_shellhook_installs_config(self, opted_in_shellhook: str) -> None:
        """Opting in wires the config installation into the shellHook.

        The refuse-to-overwrite semantics (#878) must survive: a regular
        (non-symlink) ``.pre-commit-config.yaml`` is never clobbered.
        """
        assert ".pre-commit-config.yaml" in opted_in_shellhook
        assert "Refusing" in opted_in_shellhook

    def test_opted_in_shellhook_only_sanctions_githooks_path(
        self, opted_in_shellhook: str
    ) -> None:
        """Opting in adds no ``core.hooksPath`` mutation beyond the sanctioned set.

        The scaffold's ``.githooks`` directory stays the single hook entry
        point (its sanctioned-environment guard and any consumer-owned
        scripts keep running); the generated config is picked up by
        ``.githooks/pre-commit``'s ``prek run`` via the repo-root symlink.
        The base dev-shell now wires ``core.hooksPath`` -> ``.githooks`` for
        direnv consumers (#1112), *reinforcing* that entry point. Opting into
        the flake-generated config must add no *other* hooksPath mutation:
        the PR #908 defect was git-hooks.nix's stock installation script
        unsetting/resetting ``core.hooksPath`` and installing only the
        pre-commit stage into ``.git/hooks``, silently bypassing ``.githooks``.
        So every ``core.hooksPath`` *write* must set the sanctioned
        ``.githooks`` value, and nothing may unset/uninstall it. (A
        ``config --get core.hooksPath`` read is harmless and does not match
        the ``config core.hooksPath`` write form.)
        """
        assert opted_in_shellhook.count(
            "config core.hooksPath"
        ) == opted_in_shellhook.count("config core.hooksPath .githooks"), (
            "opting in introduced a non-`.githooks` core.hooksPath write (#908)"
        )
        assert "--unset" not in opted_in_shellhook
        assert "uninstall" not in opted_in_shellhook


class TestGithooksPathWiring:
    """The dev-shell wires ``.githooks`` as core.hooksPath for direnv mode (#1112).

    Devcontainer mode runs ``git config core.hooksPath .githooks`` from
    ``setup-git-conf.sh``; a direnv / ``nix develop`` consumer never got that,
    so commit-time hooks (pre-commit / commit-msg via prek) were silently
    inactive until the consumer set it by hand. The base shellHook now mirrors
    the devcontainer, guarded so it only touches a scaffold-shaped repo and
    never fights the worktree flow (justfile.worktree unsets core.hooksPath and
    installs prek hooks directly in a linked worktree).
    """

    def test_default_shellhook_sets_core_hookspath_to_githooks(
        self, default_shellhook: str
    ) -> None:
        """direnv mode mirrors the devcontainer: ``config core.hooksPath .githooks``."""
        assert "config core.hooksPath .githooks" in default_shellhook

    def test_default_shellhook_guards_on_githooks_dir(
        self, default_shellhook: str
    ) -> None:
        """Only a scaffold-shaped repo (a ``.githooks/`` dir at toplevel) is touched."""
        assert "/.githooks" in default_shellhook

    def test_default_shellhook_guards_on_main_worktree(
        self, default_shellhook: str
    ) -> None:
        """A linked worktree (owned by justfile.worktree) is left alone.

        The guard compares the worktree git-dir with the common git-dir; they
        differ only in a linked worktree, so the wiring runs solely in the main
        checkout and never re-fights the worktree's deliberate unset.
        """
        assert "--git-common-dir" in default_shellhook

    def test_default_shellhook_never_unsets_hookspath(
        self, default_shellhook: str
    ) -> None:
        """The wiring only ever *sets* ``.githooks``; it never unsets/uninstalls (#908)."""
        assert "--unset" not in default_shellhook
        assert "uninstall" not in default_shellhook
