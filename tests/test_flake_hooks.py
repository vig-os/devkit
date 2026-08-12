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
unless a consumer opts in), including the stage-gated commit-message /
agent-identity hooks and the commit-policy knobs that steer them (#1434).

Refs: #883, #1434
"""

from __future__ import annotations

import functools
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from .nix_helpers import REPO_ROOT
from .nix_helpers import nix_env as _nix_env

ROOT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
SCAFFOLD_CONFIG = REPO_ROOT / "assets" / "workspace" / ".pre-commit-config.yaml"

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None,
    reason="nix is not installed; flake hook fidelity tests require Nix",
)


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


def _branch_guard(config: dict[str, Any]) -> str:
    """The no-commit-to-branch entry (carries the ``--pattern`` regex).

    git-hooks.nix renders the ``settings.pattern`` into the hook's ``entry``
    (``… --pattern <regex>``), so the branch-guard regex is read straight off
    the generated config's no-commit-to-branch entry.
    """
    return _normalize(config)["hooks"]["no-commit-to-branch"]["entry"]


def _pattern_arg(hook: dict[str, Any]) -> str:
    """The ``--pattern`` regex from a portable no-commit-to-branch args list.

    The committed YAML artifacts carry the regex as the value following
    ``--pattern`` in ``args`` (unlike the consumer surface, where git-hooks.nix
    bakes it into ``entry`` — see ``_branch_guard``).
    """
    args = hook["args"]
    return args[args.index("--pattern") + 1]


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

    def test_pymarkdown_is_a_system_hook(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """pymarkdown resolves from the flake toolchain, not an upstream repo (#1170).

        Packaging ``pymarkdownlnt`` in the flake (nix/pymarkdown.nix) retires the
        one runner-only remote-repo residual: the committed runner + scaffold
        render it as a ``language: system`` local hook on PATH, same ``fix`` args
        and excludes as before, with no pinned ``rev``.
        """
        for profile in ("runner", "scaffold"):
            hook = _normalize(rendered_portable[profile])["hooks"]["pymarkdown"]
            assert hook["repo"] == "local", profile
            assert hook.get("language") == "system", profile
            assert hook.get("entry") == "pymarkdown", profile
            assert hook.get("args") == ["-c", ".pymarkdown", "fix"], profile
            assert "rev" not in hook, profile


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


@functools.cache
def _consumer_config_set() -> dict[str, dict[str, Any]]:
    """Build every consumer hook config in ONE nix build (#1417).

    The customized, gitleaks-enabled, trunk-workflow, branch-types and
    commit-policy consumer shells are independent ``mkProjectShell`` calls
    whose ``hooksConfigFile`` outputs are collected into a single ``linkFarm``,
    so the suite pays one build instead of one per shell. Cached for the whole
    pytest run.

    ``pkgs`` carries ``overlays.default`` (as the scaffolded consumer flake
    builds it): the vig-utils console scripts the commit-message hooks resolve
    (#1434) come from that overlay, exactly like the ``devTools`` toolchain
    every ``mkProjectShell`` consumer already gets.
    """
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = [ flake.overlays.default ];
        config.allowUnfree = true;
      }};
      customized = flake.lib.mkProjectShell {{
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
      gitleaks = flake.lib.mkProjectShell {{
        inherit pkgs;
        hooks = {{
          gitleaks.enable = true;
        }};
      }};
      trunk = flake.lib.mkProjectShell {{
        inherit pkgs;
        workflow = "trunk";
        hooks = {{ }};
      }};
      branchtypes = flake.lib.mkProjectShell {{
        inherit pkgs;
        hooks = {{ }};
        branchTypes = [ "feature" "bugfix" "hotfix" "release" "docs" "test" "refactor" "record" ];
      }};
      branchtypes-trunk = flake.lib.mkProjectShell {{
        inherit pkgs;
        workflow = "trunk";
        hooks = {{ }};
        branchTypes = [ "feature" "bugfix" "record" ];
      }};
      commitpolicy = flake.lib.mkProjectShell {{
        inherit pkgs;
        hooks = {{ }};
        commitTypes = [
          "feat" "fix" "docs" "chore" "refactor" "perf" "test" "ci" "build"
          "revert" "style" "record"
        ];
        refsPolicy = "optional";
      }};
      refsrequired = flake.lib.mkProjectShell {{
        inherit pkgs;
        hooks = {{ }};
        refsPolicy = "required";
      }};
    in
    pkgs.linkFarm "consumer-hook-configs" [
      {{ name = "customized"; path = customized.hooksConfigFile; }}
      {{ name = "gitleaks"; path = gitleaks.hooksConfigFile; }}
      {{ name = "trunk"; path = trunk.hooksConfigFile; }}
      {{ name = "branchtypes"; path = branchtypes.hooksConfigFile; }}
      {{ name = "branchtypes-trunk"; path = branchtypes-trunk.hooksConfigFile; }}
      {{ name = "commitpolicy"; path = commitpolicy.hooksConfigFile; }}
      {{ name = "refsrequired"; path = refsrequired.hooksConfigFile; }}
    ]
    """
    result = _run_nix(
        ["build", "--impure", "--no-link", "--print-out-paths", "--expr", expr],
        timeout=1800,
    )
    assert result.returncode == 0, (
        "building the consumer hook configs failed:\n" + result.stderr
    )
    root = Path(result.stdout.strip())
    # The generated files are JSON preceded by "# …" comment lines; YAML is
    # a JSON superset that treats them as comments, so parse with yaml.
    return {
        name: yaml.safe_load((root / name).read_text())
        for name in (
            "customized",
            "gitleaks",
            "trunk",
            "branchtypes",
            "branchtypes-trunk",
            "commitpolicy",
            "refsrequired",
        )
    }


@pytest.fixture(scope="module")
def consumer_config() -> dict[str, Any]:
    """The generated config for a customized consumer shell."""
    return _consumer_config_set()["customized"]


@pytest.fixture(scope="module")
def gitleaks_enabled_config() -> dict[str, Any]:
    """Generated config for a consumer that opts into the gitleaks hook (#1172)."""
    return _consumer_config_set()["gitleaks"]


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
def trunk_consumer_config() -> dict[str, Any]:
    """Generated config for a trunk-workflow consumer (#1224).

    A ``DEVKIT_WORKFLOW=trunk`` workspace has no long-lived ``dev`` branch, so
    the flake-generated branch guard must drop the ``(?!dev$)`` clause — exactly
    what ``render_workflow_model`` does to the scaffolded YAML. Mirrors the
    ``consumer_config`` fixture but threads ``workflow = "trunk"`` (built in
    the same single derivation set, #1417).
    """
    return _consumer_config_set()["trunk"]


class TestWorkflowModelBranchGuard:
    """The flake-generated branch guard follows DEVKIT_WORKFLOW (#1224).

    The scaffolded ``.pre-commit-config.yaml`` is workflow-model-aware
    (``render_workflow_model`` drops the ``(?!dev$)`` clause for trunk), but a
    direnv consumer on flake-generated hooks (#1167) gets its guard from
    ``mkProjectShell``. Passing ``workflow`` makes that generated guard mirror
    the scaffold render, so the two artifacts can no longer disagree.
    """

    def test_gitflow_consumer_guards_dev(self, consumer_config: dict[str, Any]) -> None:
        """The default (gitflow) consumer keeps the dev-branch protect-clause."""
        entry = _branch_guard(consumer_config)
        assert "(?!main$)" in entry
        assert "(?!dev$)" in entry

    def test_trunk_consumer_drops_dev_clause(
        self, trunk_consumer_config: dict[str, Any]
    ) -> None:
        """A trunk consumer drops the ``(?!dev$)`` clause; main stays protected."""
        entry = _branch_guard(trunk_consumer_config)
        assert "(?!main$)" in entry
        assert "(?!dev$)" not in entry

    def test_trunk_guard_mirrors_scaffold_trunk_render(
        self, consumer_config: dict[str, Any], trunk_consumer_config: dict[str, Any]
    ) -> None:
        """Trunk guard == gitflow guard minus the ``(?!dev$)`` clause.

        The exact parity ``render_workflow_model`` produces on the scaffolded
        path (a lone ``s|(?!dev$)||`` deletion), proven here on the flake path.
        """
        gitflow = _branch_guard(consumer_config)
        trunk = _branch_guard(trunk_consumer_config)
        assert trunk == gitflow.replace("(?!dev$)", "")

    def test_invalid_workflow_is_rejected(self) -> None:
        """An unknown ``workflow`` value is refused loudly at eval time."""
        expr = f"""
        let
          flake = builtins.getFlake "path:{REPO_ROOT}";
          system = builtins.currentSystem;
          pkgs = import flake.inputs.nixpkgs {{ inherit system; }};
        in
        (flake.lib.mkProjectShell {{
          inherit pkgs;
          workflow = "bogus";
          hooks = {{ }};
        }}).drvPath
        """
        result = _run_nix(["eval", "--impure", "--raw", "--expr", expr])
        assert result.returncode != 0
        assert "workflow" in result.stderr


class TestRenovateBranchAllowance:
    """The default branch guard admits Renovate's tool-owned namespace (#1433).

    The Renovate app commits server-side, where local hooks never run — but
    maintainer fix-up commits on ``renovate/*`` branches (changelog conflict
    merges, ``dist/`` rebuilds) are a real flow the guard used to block,
    forcing a commit-on-a-compliant-branch-then-push-to-ref workaround.
    Renovate branch names carry no issue number and use a charset outside the
    slug rule (live example: ``renovate/github-actions-(minor-and-patch)``),
    so the namespace gets its own lookahead clause next to ``worktree/<n>``
    rather than a ``DEVKIT_BRANCH_TYPES`` value.

    ``no-commit-to-branch`` BLOCKS a branch whose name matches ``--pattern``,
    so "allowed" asserts the regex does NOT match.
    """

    ALLOWED = (
        "renovate/lock-file-maintenance",
        "renovate/github-actions-(minor-and-patch)",
    )
    BLOCKED = (
        # Prefix confusion is not the Renovate namespace.
        "renovated/x",
        # The guard still bites outside every allowance clause.
        "random-branch",
    )

    def test_runner_render_allows_renovate_branches(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """The committed runner/scaffold pattern admits renovate/* only."""
        pattern = _pattern_arg(
            _normalize(rendered_portable["runner"])["hooks"]["no-commit-to-branch"]
        )
        for branch in self.ALLOWED:
            assert re.match(pattern, branch) is None, f"{branch} must be allowed"
        for branch in self.BLOCKED:
            assert re.match(pattern, branch) is not None, f"{branch} must be blocked"

    def test_consumer_surface_carries_renovate_allowance(
        self, consumer_config: dict[str, Any]
    ) -> None:
        """The flake-generated (gitflow) guard carries the same clause."""
        assert "(?!^renovate/.+$)" in _branch_guard(consumer_config)

    def test_trunk_consumer_keeps_renovate_allowance(
        self, trunk_consumer_config: dict[str, Any]
    ) -> None:
        """The trunk variant drops only the dev clause, never this one."""
        assert "(?!^renovate/.+$)" in _branch_guard(trunk_consumer_config)


@pytest.fixture(scope="module")
def branch_types_config() -> dict[str, Any]:
    """Generated config for a consumer passing a custom ``branchTypes`` (#1432)."""
    return _consumer_config_set()["branchtypes"]


@pytest.fixture(scope="module")
def branch_types_trunk_config() -> dict[str, Any]:
    """Custom ``branchTypes`` composed with ``workflow = "trunk"`` (#1432)."""
    return _consumer_config_set()["branchtypes-trunk"]


class TestBranchTypesKnob:
    """mkProjectShell's ``branchTypes`` argument (#1432).

    ``DEVKIT_BRANCH_TYPES`` steers the issue-numbered alternation of the
    branch guard. The scaffolded YAML render is covered in bats; here the
    flake-generated consumer surface must follow the same set — the template
    flake.nix reads the key from ``.vig-os`` and forwards it, mirroring the
    #1224 ``workflow`` threading. Null (the default) keeps the stock
    alternation byte-identical, so the drift gate and the zero-hooks parity
    stay green.
    """

    STOCK_ALTERNATION = "(feature|bugfix|hotfix|release|docs|test|refactor)"

    def test_custom_types_extend_alternation(
        self, branch_types_config: dict[str, Any]
    ) -> None:
        """The custom set renders into the issue-numbered alternation."""
        entry = _branch_guard(branch_types_config)
        assert "(feature|bugfix|hotfix|release|docs|test|refactor|record)" in entry

    def test_custom_types_regex_semantics(
        self, branch_types_config: dict[str, Any]
    ) -> None:
        """``record/<issue>-<slug>`` commits pass; issue-less record stays blocked."""
        pattern = _branch_guard(branch_types_config).split("--pattern ")[1]
        assert re.match(pattern, "record/54-supplier-x") is None
        assert re.match(pattern, "record/no-issue") is not None

    def test_null_default_keeps_stock_alternation(
        self, consumer_config: dict[str, Any]
    ) -> None:
        """A consumer not passing ``branchTypes`` keeps the stock pattern."""
        assert self.STOCK_ALTERNATION in _branch_guard(consumer_config)

    def test_composes_with_trunk_workflow(
        self, branch_types_trunk_config: dict[str, Any]
    ) -> None:
        """Custom types and the trunk dev-clause drop apply together."""
        entry = _branch_guard(branch_types_trunk_config)
        assert "(feature|bugfix|record)" in entry
        assert "(?!dev$)" not in entry
        assert "(?!main$)" in entry

    @pytest.mark.parametrize(
        "bad_types",
        [
            pytest.param('[ "feature" "Bad-Type" ]', id="bad-charset"),
            pytest.param("[ ]", id="empty-list"),
        ],
    )
    def test_invalid_branch_types_rejected(self, bad_types: str) -> None:
        """A malformed ``branchTypes`` list is refused loudly at eval time."""
        expr = f"""
        let
          flake = builtins.getFlake "path:{REPO_ROOT}";
          system = builtins.currentSystem;
          pkgs = import flake.inputs.nixpkgs {{ inherit system; }};
        in
        (flake.lib.mkProjectShell {{
          inherit pkgs;
          branchTypes = {bad_types};
          hooks = {{ }};
        }}).drvPath
        """
        result = _run_nix(["eval", "--impure", "--raw", "--expr", expr])
        assert result.returncode != 0
        assert "branchTypes" in result.stderr


STOCK_COMMIT_TYPES = "feat,fix,docs,chore,refactor,perf,test,ci,build,revert,style"
# The argv the scaffolded .pre-commit-config.yaml ships with every knob unset —
# the default the flake-generated surface must reproduce exactly (#1434).
STOCK_VALIDATE_ARGS = [
    "--types",
    STOCK_COMMIT_TYPES,
    "--refs-optional-types",
    "chore",
    "--blocked-patterns",
    ".github/agent-blocklist.toml",
]


def _arg_value(hook: dict[str, Any], flag: str) -> str:
    """The value following ``flag`` in a hook's rendered ``args`` list."""
    args = hook["args"]
    return args[args.index(flag) + 1]


class TestCommitMsgHooksConsumerSurface:
    """The #163/#1019/#1031 hooks reach flake-generated consumers (#1434).

    A direnv consumer on flake-generated hooks (#1167 default) got a
    ``.pre-commit-config.yaml`` with no ``commit-msg``/``prepare-commit-msg``
    stage at all, so the scaffolded ``.githooks/commit-msg`` shim
    (``prek run --hook-stage commit-msg``) exited 0 with nothing to run, and
    ``check-agent-identity`` was absent too — ``git commit --author="Claude
    <…>"`` passed locally. The three hooks must render on the consumer surface
    with the same stages and argv the scaffolded YAML carries.
    """

    IDS = (
        "validate-commit-msg",
        "prepare-commit-msg-strip-trailers",
        "check-agent-identity",
    )

    def test_all_three_hooks_reach_the_consumer_surface(
        self, consumer_config: dict[str, Any]
    ) -> None:
        hooks = _normalize(consumer_config)["hooks"]
        for hook_id in self.IDS:
            assert hook_id in hooks, (
                f"{hook_id} missing from the flake-generated consumer config — "
                "local commit-message/agent-identity enforcement is a no-op (#1434)"
            )

    def test_validate_commit_msg_runs_at_the_commit_msg_stage(
        self, consumer_config: dict[str, Any]
    ) -> None:
        """Without this stage the ``.githooks/commit-msg`` shim has nothing to run."""
        hook = _normalize(consumer_config)["hooks"]["validate-commit-msg"]
        assert hook["stages"] == ["commit-msg"]

    def test_strip_trailers_runs_at_the_prepare_commit_msg_stage(
        self, consumer_config: dict[str, Any]
    ) -> None:
        """Trailers are stripped BEFORE the validator's blocklist gate sees them."""
        hook = _normalize(consumer_config)["hooks"]["prepare-commit-msg-strip-trailers"]
        assert hook["stages"] == ["prepare-commit-msg"]
        assert hook["pass_filenames"] is True

    def test_check_agent_identity_stays_a_pre_commit_hook(
        self, consumer_config: dict[str, Any]
    ) -> None:
        """It guards the author/committer, so it runs on the pre-commit stage."""
        hook = _normalize(consumer_config)["hooks"]["check-agent-identity"]
        assert hook["stages"] == ["pre-commit"]
        assert hook["pass_filenames"] is False

    def test_entries_resolve_the_pinned_vig_utils(
        self, consumer_config: dict[str, Any]
    ) -> None:
        """Store-path entries, not ``uv run``: the consumer venv has no vig-utils.

        Every other tool-naming consumer fragment (nixfmt, statix, deadnix,
        just-fmt, gitleaks, pymarkdown) resolves a ``pkgs.<tool>`` store path,
        so the hook follows the devkit pin the consumer bumps with
        ``nix flake update vigos`` instead of whatever the project venv happens
        to hold.
        """
        hooks = _normalize(consumer_config)["hooks"]
        for hook_id in self.IDS:
            entry = hooks[hook_id]["entry"]
            assert entry.startswith("/nix/store/"), (
                f"{hook_id} entry is not a store path: {entry!r}"
            )
            assert entry.endswith(f"/bin/{hook_id}"), entry
            assert hooks[hook_id]["language"] == "system"

    def test_default_args_match_the_scaffolded_render(
        self, consumer_config: dict[str, Any], rendered_portable: dict[str, Any]
    ) -> None:
        """Default-render stability: both surfaces ship identical argv (#1434).

        A docker-mode consumer (scaffolded YAML) and a direnv consumer
        (flake-generated) must enforce the same rule with the knobs unset —
        the hook/CI desync class #1074 and #1282 exist to prevent.
        """
        consumer = _normalize(consumer_config)["hooks"]["validate-commit-msg"]
        scaffold = _normalize(rendered_portable["scaffold"])["hooks"][
            "validate-commit-msg"
        ]
        assert consumer["args"] == scaffold["args"] == STOCK_VALIDATE_ARGS


@pytest.fixture(scope="module")
def commit_policy_config() -> dict[str, Any]:
    """Generated config for custom ``commitTypes`` + ``refsPolicy = optional``."""
    return _consumer_config_set()["commitpolicy"]


@pytest.fixture(scope="module")
def refs_required_config() -> dict[str, Any]:
    """Generated config for ``refsPolicy = "required"`` (#1282)."""
    return _consumer_config_set()["refsrequired"]


class TestCommitPolicyKnobsOnTheFlakeSurface:
    """``commitTypes`` / ``refsPolicy`` on mkProjectShell (#1434).

    #1431 (``DEVKIT_COMMIT_TYPES``) and #1282 (``DEVKIT_REFS_POLICY``) render
    into the scaffolded YAML and CI's ``validate-commit-range``; a direnv
    consumer's local hook comes from ``mkProjectShell`` instead, so the same
    two keys must reach it — threaded like ``workflow`` (#1224) and
    ``branchTypes`` (#1432). The resolution semantics (defaults, charset,
    the ``optional`` mirror of the resolved types list, the ``required``
    ``none`` sentinel) must match ``render_commit_types`` /
    ``render_refs_policy`` in ``assets/init-workspace.sh`` and
    ``resolve-toolchain`` exactly — two renderers, one key.
    """

    def test_custom_commit_types_render_into_the_types_arg(
        self, commit_policy_config: dict[str, Any]
    ) -> None:
        hook = _normalize(commit_policy_config)["hooks"]["validate-commit-msg"]
        assert _arg_value(hook, "--types") == f"{STOCK_COMMIT_TYPES},record"

    def test_refs_policy_optional_mirrors_the_resolved_commit_types(
        self, commit_policy_config: dict[str, Any]
    ) -> None:
        """The #1431 composition fix, on the flake surface.

        ``optional`` must mirror the RESOLVED types list, never a hardcoded
        copy of the stock 11 — otherwise the hook requires ``Refs:`` for a
        custom type it just accepted.
        """
        hook = _normalize(commit_policy_config)["hooks"]["validate-commit-msg"]
        assert _arg_value(hook, "--refs-optional-types") == _arg_value(hook, "--types")

    def test_refs_policy_required_uses_the_none_sentinel(
        self, refs_required_config: dict[str, Any]
    ) -> None:
        """An empty list reads as falsy to the CLI, so ``required`` sends ``none``."""
        hook = _normalize(refs_required_config)["hooks"]["validate-commit-msg"]
        assert _arg_value(hook, "--refs-optional-types") == "none"
        assert _arg_value(hook, "--types") == STOCK_COMMIT_TYPES

    def test_unset_knobs_keep_the_stock_argv(
        self, consumer_config: dict[str, Any]
    ) -> None:
        """Null/absent knobs resolve to today's behavior, byte for byte."""
        hook = _normalize(consumer_config)["hooks"]["validate-commit-msg"]
        assert hook["args"] == STOCK_VALIDATE_ARGS

    @pytest.mark.parametrize(
        ("arg", "value", "message"),
        [
            pytest.param(
                "commitTypes",
                '[ "feat" "Bad-Type" ]',
                "commitTypes",
                id="types-charset",
            ),
            pytest.param("commitTypes", "[ ]", "commitTypes", id="types-empty"),
            pytest.param(
                "refsPolicy", '"garbage"', "refsPolicy", id="refs-policy-enum"
            ),
        ],
    )
    def test_invalid_values_are_refused_at_eval_time(
        self, arg: str, value: str, message: str
    ) -> None:
        """A bad value fails loudly, mirroring init-workspace.sh's loud abort."""
        expr = f"""
        let
          flake = builtins.getFlake "path:{REPO_ROOT}";
          system = builtins.currentSystem;
          pkgs = import flake.inputs.nixpkgs {{ inherit system; }};
        in
        (flake.lib.mkProjectShell {{
          inherit pkgs;
          {arg} = {value};
          hooks = {{ }};
        }}).drvPath
        """
        result = _run_nix(["eval", "--impure", "--raw", "--expr", expr])
        assert result.returncode != 0
        assert message in result.stderr

    def test_template_flake_reads_and_forwards_both_knobs(self) -> None:
        """The scaffolded flake.nix wires ``.vig-os`` -> ``mkProjectShell``.

        Same one-time port as #1224/#1432: the reader lives in the
        scaffold-once ``flake.nix``, and the forwarding is gated behind a
        ``builtins.functionArgs`` probe so a floating ``vigos`` input that
        predates the argument still evaluates (#1249).
        """
        flake = (REPO_ROOT / "assets" / "workspace" / "flake.nix").read_text()
        for key, arg in (
            ("DEVKIT_COMMIT_TYPES", "commitTypes"),
            ("DEVKIT_REFS_POLICY", "refsPolicy"),
        ):
            assert f'vigOsValue "{key}"' in flake, f"flake.nix does not read {key}"
            assert f"inherit {arg};" in flake, f"flake.nix does not forward `{arg}`"
            assert f"builtins.functionArgs vigos.lib.mkProjectShell ? {arg}" in flake, (
                f"flake.nix forwards `{arg}` unconditionally — the floating vigos "
                "input may resolve a devkit that predates the argument (#1249)"
            )


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
            # pymarkdown joins the consumer generation surface once packaged
            # in the flake (#1170) — direnv/bare consumers regain markdown lint.
            "pymarkdown",
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


class TestNixLintersConsumerSurface:
    """statix + deadnix live on the flake-generated consumer surface (#1171).

    Nix-oriented consumers (exo-fleet, vigo-nixos) need the statix/deadnix
    lint pair; today they exist only as devkit-internal ``nix flake check``
    gates. ``nix/hooks.nix`` defines them as consumer-only ``language: system``
    hooks: they render into ``mkProjectShell``'s generated config but are NOT
    injected into either committed hand-managed YAML (``scaffold = false`` —
    existing container-mode consumers must see zero change).
    """

    def test_statix_is_on_the_consumer_surface(
        self, consumer_config: dict[str, Any]
    ) -> None:
        hooks = _normalize(consumer_config)["hooks"]
        assert "statix" in hooks, "statix missing from generated consumer config"
        assert "/bin/statix" in hooks["statix"]["entry"]
        # statix accepts exactly ONE target, so filenames must not be appended.
        assert hooks["statix"].get("pass_filenames") is False

    def test_deadnix_is_on_the_consumer_surface(
        self, consumer_config: dict[str, Any]
    ) -> None:
        hooks = _normalize(consumer_config)["hooks"]
        assert "deadnix" in hooks, "deadnix missing from generated consumer config"
        entry = hooks["deadnix"]["entry"]
        assert "/bin/deadnix" in entry
        assert "--fail" in entry, "deadnix must fail the hook on findings"

    def test_nix_linters_stay_out_of_the_committed_yaml(
        self, rendered_portable: dict[str, Any]
    ) -> None:
        """Neither committed YAML gains the pair (scaffold = false, #1171).

        The hand-managed runner/scaffold configs are what existing
        container-mode consumers re-scaffold from; injecting statix/deadnix
        there would surprise every one of them on the next upgrade.
        """
        for profile in ("runner", "scaffold"):
            hooks = _normalize(rendered_portable[profile])["hooks"]
            assert "statix" not in hooks, f"statix leaked into the {profile} YAML"
            assert "deadnix" not in hooks, f"deadnix leaked into the {profile} YAML"

    def test_template_flake_passes_both_linters_as_configured(
        self, consumer_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """The scaffolded consumer flake.nix passes both hooks out of the box.

        deadnix flags intentionally-unused lambda args — the template's
        ``{ self, … }`` output pattern and the ``extraPackages = pkgs: [ ]``
        seed — so the hook entries must carry the flags that keep a FRESH
        scaffold green. Run the exact rendered entries against a copy of the
        template (statix's single-target ``check .`` from the copy's root,
        mirroring a fresh consumer repo).
        """
        template = REPO_ROOT / "assets" / "workspace" / "flake.nix"
        (tmp_path / "flake.nix").write_text(template.read_text())
        hooks = _normalize(consumer_config)["hooks"]

        deadnix_cmd = shlex.split(hooks["deadnix"]["entry"]) + ["flake.nix"]
        result = subprocess.run(
            deadnix_cmd, capture_output=True, text=True, cwd=tmp_path
        )
        assert result.returncode == 0, (
            "deadnix (as configured) rejects the scaffolded flake.nix:\n"
            f"{result.stdout}{result.stderr}"
        )

        statix_cmd = shlex.split(hooks["statix"]["entry"])
        result = subprocess.run(
            statix_cmd, capture_output=True, text=True, cwd=tmp_path
        )
        assert result.returncode == 0, (
            "statix (as configured) rejects the scaffolded flake.nix:\n"
            f"{result.stdout}{result.stderr}"
        )


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

    def test_zero_hooks_shellhook_has_no_generation(
        self, default_shellhook: str
    ) -> None:
        """The default shellHook carries no git-hooks.nix installation script."""
        assert ".pre-commit-config.yaml" not in default_shellhook
        assert "git-hooks.nix" not in default_shellhook

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
