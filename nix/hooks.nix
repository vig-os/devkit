# One definition of the pre-commit hook set (#883).
#
# Every hook lives exactly once in `hookDefs` below, with one record per
# artifact it appears in:
#
#   - `yaml`      — its PATH-portable representation in the committed runner
#                   config (`.pre-commit-config.yaml`; `scaffold = true` also
#                   places it in `assets/workspace/.pre-commit-config.yaml`).
#                   Rendered by `portable.{runner,scaffold}` and drift-gated
#                   against the committed files by tests/test_flake_hooks.py,
#                   so the YAMLs can no longer diverge from this definition.
#   - `check`     — its sandbox-pure git-hooks.nix fragment for the flake's
#                   `checks.pre-commit` gate (store-path entries, hermetic;
#                   `null` = runner-only, cannot run in the Nix sandbox).
#   - `consumer`  — its git-hooks.nix fragment for the consumer generation
#                   surface (`mkProjectShell { hooks = …; }`): entering the
#                   shell installs the rendered config via git-hooks.nix's
#                   installation script (`null` = not generatable, e.g.
#                   pymarkdown, which is not in nixpkgs — documented residual
#                   in docs/NIX.md).
#
# `checkName`/`consumerName` map a committed hook id to the git-hooks.nix
# attribute name where they differ (git-hooks.nix pluralises some
# pre-commit-hooks ids, e.g. check-case-conflict -> check-case-conflicts).
{ lib }:
let
  # Topic-branch naming convention enforced by no-commit-to-branch:
  # chore/<summary>, <type>/<issue>-<summary>, worktree/<issue>; main and dev
  # are allowed (pushing there is blocked server-side, not here).
  branchNamePattern = "^(?!main$)(?!dev$)(?!^(chore)/[a-z0-9]+(-[a-z0-9]+)*$)(?!^(feature|bugfix|hotfix|release|docs|test|refactor)/[0-9]+-[a-z0-9]+(-[a-z0-9]+)*$)(?!^worktree/[0-9]+$).+$";

  # Top-level exclude — one regex string in the committed YAML, a list for
  # git-hooks.nix (which joins with `|`). Same paths, two spellings.
  yamlExclude = "^.github_data/|^docs/issues/|^docs/pull-requests/";
  baseExcludes = [
    "^\\.github_data/"
    "^docs/issues/"
    "^docs/pull-requests/"
  ];

  # Upstream repos (pinned revs) for the portable render of hooks that the
  # runner installs from a remote pre-commit repo rather than the PATH.
  remoteRepos = {
    pre-commit-hooks = {
      repo = "https://github.com/pre-commit/pre-commit-hooks";
      rev = "cef0300fd0fc4d2a87a85fa2093c6b283ea36f4b"; # v5.0.0
    };
    yamllint = {
      repo = "https://github.com/adrienverge/yamllint";
      rev = "81e9f98ffd059efe8aa9c1b1a42e5cce61b640c6"; # v1.35.1
    };
    pymarkdown = {
      repo = "https://github.com/jackdewinter/pymarkdown";
      rev = "f93643d339dfee2a1022e7b05e8b5a281bfac553"; # v0.9.23
    };
  };

  # Shared per-hook filters used by more than one artifact of the same hook.
  shellcheckExclude = "(^|/)\\.envrc$";
  yamllintArgs = [
    "--format"
    "parsable"
    "--strict"
  ];
  justfileFiles = "^justfile(\\..*)?$";
  actionPinsFiles = "^\\.github/(workflows/.*\\.ya?ml|actions/.*/action\\.ya?ml)$";
  expirationsFiles = "^\\.(trivyignore|vulnixignore)$";

  hookDefs = {
    # ── Formatting ──────────────────────────────────────────────────────
    # The gate runs ONE treefmt hook (nixfmt-rfc-style + ruff-format +
    # taplo) reusing the flake's treefmt wrapper — the same formatting
    # `nix fmt` and `checks.formatting` use (#777, #778). The runner keeps
    # the individual PATH-portable formatter hooks below (ruff-format,
    # taplo-format, nixfmt), because the treefmt wrapper is a store path
    # and the committed config must stay PATH-portable.
    treefmt = {
      check =
        { treefmtWrapper, ... }:
        {
          enable = true;
          packageOverrides.treefmt = treefmtWrapper;
        };
    };

    # ── pre-commit-hooks meta hooks ─────────────────────────────────────
    # Enforce topic branch naming (runner-only: inspects git state, absent
    # in the Nix sandbox). Consumers can override the pattern via
    # `hooks."no-commit-to-branch".settings.{branch,pattern}`.
    no-commit-to-branch = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = {
        name = "branch-name (enforce <type>/<issue>-<summary>)";
        args = [
          "--branch"
          "__none__" # override default so main/dev are not protected
          "--pattern"
          branchNamePattern
        ];
      };
      consumer = _: {
        enable = true;
        settings = {
          branch = [ "__none__" ];
          pattern = [ branchNamePattern ];
        };
      };
    };
    check-added-large-files = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      check = _: {
        enable = true;
      };
      consumer = _: {
        enable = true;
      };
    };
    check-case-conflict = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      checkName = "check-case-conflicts";
      check = _: {
        enable = true;
      };
      consumerName = "check-case-conflicts";
      consumer = _: {
        enable = true;
      };
    };
    check-json = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      check = _: {
        enable = true;
      };
      consumer = _: {
        enable = true;
      };
    };
    check-merge-conflict = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      checkName = "check-merge-conflicts";
      check = _: {
        enable = true;
      };
      consumerName = "check-merge-conflicts";
      consumer = _: {
        enable = true;
      };
    };
    check-symlinks = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      check = _: {
        enable = true;
      };
      consumer = _: {
        enable = true;
      };
    };
    check-toml = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      check = _: {
        enable = true;
      };
      consumer = _: {
        enable = true;
      };
    };
    check-yaml = {
      repo = "pre-commit-hooks";
      scaffold = true;
      # git-hooks.nix' check-yaml built-in hardcodes --multi, so the runner
      # matches it here to keep runner and gate in agreement (#778).
      yaml = {
        args = [ "--allow-multiple-documents" ];
      };
      check = _: {
        enable = true;
      };
      consumer = _: {
        enable = true;
      };
    };
    # debug-statements parses the file's Python AST, so the gate pins the
    # hook's package to the project-interpreter (3.14) build: the default
    # is built for 3.13, which rejects PEP 758 parenthesis-free
    # `except A, B:` used in this repo (#778, #803).
    debug-statements = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      checkName = "python-debug-statements";
      check =
        { python, ... }:
        {
          enable = true;
          package = python.pkgs.pre-commit-hooks;
        };
      consumerName = "python-debug-statements";
      consumer = pkgs: {
        enable = true;
        package = pkgs.python314.pkgs.pre-commit-hooks;
      };
    };
    # Runner-only in the gate (git-state-dependent, and git-hooks.nix has no
    # built-in); the consumer render wires the pre-commit-hooks binary.
    destroyed-symlinks = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      consumer = pkgs: {
        enable = true;
        name = "destroyed-symlinks";
        entry = "${pkgs.python3Packages.pre-commit-hooks}/bin/destroyed-symlinks";
        language = "system";
        types = [ "file" ];
      };
    };
    detect-private-key = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      checkName = "detect-private-keys";
      check = _: {
        enable = true;
      };
      consumerName = "detect-private-keys";
      consumer = _: {
        enable = true;
      };
    };
    end-of-file-fixer = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      check = _: {
        enable = true;
      };
      consumer = _: {
        enable = true;
      };
    };
    mixed-line-ending = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      checkName = "mixed-line-endings";
      check = _: {
        enable = true;
      };
      consumerName = "mixed-line-endings";
      consumer = _: {
        enable = true;
      };
    };
    trailing-whitespace = {
      repo = "pre-commit-hooks";
      scaffold = true;
      yaml = { };
      checkName = "trim-trailing-whitespace";
      check = _: {
        enable = true;
      };
      consumerName = "trim-trailing-whitespace";
      consumer = _: {
        enable = true;
      };
    };

    # ── Linters (language: system, resolved from the flake toolchain) ───
    ruff = {
      scaffold = true;
      yaml = {
        name = "ruff (lint/fix python)";
        entry = "ruff check --fix";
        language = "system";
        types = [ "python" ];
      };
      check = _: {
        enable = true;
      };
      consumer = _: {
        enable = true;
      };
    };
    ruff-format = {
      scaffold = true;
      yaml = {
        name = "ruff-format (format python)";
        entry = "ruff format";
        language = "system";
        types = [ "python" ];
      };
      # Gate coverage comes from the treefmt hook above.
      consumer = _: {
        enable = true;
      };
    };
    yamllint = {
      repo = "yamllint";
      scaffold = true;
      yaml = {
        args = yamllintArgs;
      };
      check = _: {
        enable = true;
        args = yamllintArgs;
      };
      consumer = _: {
        enable = true;
        args = yamllintArgs;
      };
    };
    # taplo semantic lint + format (runner-only ids; the gate covers
    # formatting via treefmt and lint via a store-path taplo-lint below).
    taplo-format = {
      yaml = {
        name = "taplo-format";
        entry = "taplo format --config .taplo.toml";
        language = "system";
        types = [ "toml" ];
      };
    };
    taplo-lint = {
      yaml = {
        name = "taplo-lint";
        entry = "taplo lint --config .taplo.toml";
        language = "system";
        types = [ "toml" ];
      };
      check =
        { pkgs, ... }:
        {
          enable = true;
          name = "taplo-lint";
          entry = "${pkgs.taplo}/bin/taplo lint --config .taplo.toml";
          language = "system";
          types = [ "toml" ];
        };
    };
    # shellcheck runs as a language:system hook resolved from the flake
    # (the shellcheck-py manylinux wheel cannot run in the Nix image, #778).
    # .envrc files are direnv stdlib scripts with no shebang; excluded.
    shellcheck = {
      scaffold = true;
      yaml = {
        name = "shellcheck";
        entry = "shellcheck";
        language = "system";
        types = [ "shell" ];
        args = [ "-x" ];
        exclude = shellcheckExclude;
      };
      check = _: {
        enable = true;
        args = [ "-x" ];
        excludes = [ shellcheckExclude ];
      };
      consumer = _: {
        enable = true;
        args = [ "-x" ];
        excludes = [ shellcheckExclude ];
      };
    };
    # GitHub Actions workflow linter (#995). Runner-only and devkit-only: it
    # lints THIS repo's own .github/workflows/ via actionlint's auto-discovery
    # (pass_filenames = false). Not scaffolded to consumers and not in the
    # sandbox gate — the per-mode RENDERED consumer templates are validated in
    # tests/bats instead, because linting them in-place resolves the
    # reusable-workflow siblings against the wrong root (the devkit itself).
    # actionlint's bundled shellcheck pass over run-block scripts is enabled
    # (#1003); the standalone shellcheck hook above still covers .sh scripts.
    actionlint = {
      yaml = {
        name = "actionlint (lint GitHub Actions workflows)";
        entry = "actionlint";
        language = "system";
        files = "^\\.github/workflows/.*\\.ya?ml$";
        pass_filenames = false;
      };
    };
    # Markdown lint — runner-only everywhere: pymarkdown is not in nixpkgs,
    # so neither the sandbox gate nor the consumer generation can resolve
    # it (documented residual, docs/NIX.md).
    pymarkdown = {
      repo = "pymarkdown";
      scaffold = true;
      yaml = {
        name = "pymarkdown";
        args = [
          "-c"
          ".pymarkdown"
          "fix"
        ];
        exclude = "^(README\\.md|CONTRIBUTE\\.md|TESTING\\.md)";
      };
    };
    # just formats justfiles. The runner rewrites in place; the Nix gate
    # must not mutate the source, so it mirrors the hook in check mode
    # (`--check`) — justfile-format drift still fails the gate (#778).
    just-fmt = {
      scaffold = true;
      yaml = {
        name = "just (format justfiles)";
        entry = "just --fmt --unstable";
        language = "system";
        files = justfileFiles;
        pass_filenames = false;
      };
      check =
        { pkgs, ... }:
        {
          enable = true;
          name = "just-fmt";
          entry = "${pkgs.just}/bin/just --fmt --check --unstable";
          language = "system";
          files = justfileFiles;
          pass_filenames = false;
        };
      consumer = pkgs: {
        enable = true;
        name = "just-fmt";
        entry = "${pkgs.just}/bin/just --fmt --unstable";
        language = "system";
        files = justfileFiles;
        pass_filenames = false;
      };
    };
    nixfmt = {
      scaffold = true;
      yaml = {
        name = "nixfmt (format/check nix files)";
        entry = "nixfmt --check";
        language = "system";
        files = "\\.nix$";
        types = [ "file" ];
      };
      # Gate coverage comes from the treefmt hook above.
      consumer = pkgs: {
        enable = true;
        name = "nixfmt";
        entry = "${pkgs.nixfmt-rfc-style}/bin/nixfmt --check";
        language = "system";
        files = "\\.nix$";
      };
    };
    typos = {
      scaffold = true;
      yaml = {
        name = "typos (source typo checker)";
        entry = "typos --force-exclude";
        language = "system";
      };
      check = _: {
        enable = true;
      };
      consumer = _: {
        enable = true;
      };
    };

    # ── Repo generators / project-venv hooks (runner-only: need network,
    #    the uv venv, or repo scripts — impossible in the Nix sandbox) ────
    generate-docs = {
      yaml = {
        name = "generate-docs (regenerate from templates)";
        entry = "uv run python docs/generate.py";
        language = "system";
        files = "^(docs/templates/.*\\.j2|docs/narrative/.*\\.md|scripts/requirements\\.yaml|justfile|CHANGELOG\\.md|\\.claude/skills/.*/SKILL\\.md)$";
        pass_filenames = false;
      };
    };
    sync-manifest = {
      yaml = {
        name = "sync-manifest";
        entry = "uv run python scripts/sync_manifest.py sync assets/workspace/";
        language = "system";
        pass_filenames = false;
      };
    };
    pip-licenses = {
      yaml = {
        name = "pip-licenses (check dependency licenses)";
        entry = "uv run pip-licenses --fail-on=\"GPL-3.0-only;GPL-3.0-or-later;AGPL-3.0-only;AGPL-3.0-or-later\"";
        language = "system";
        files = "^(pyproject\\.toml|uv\\.lock|requirements.*\\.txt)$";
        pass_filenames = false;
      };
    };

    # ── vig-utils / bandit hooks — the gate wires the hermetic Nix
    #    binaries (${vigUtils}/bin/…, ${pkgs.bandit}/bin/bandit), the
    #    runner resolves them from the project venv via `uv run`. ─────────
    check-action-pins = {
      yaml = {
        name = "check-action-pins (verify SHA-pinned actions)";
        entry = "uv run check-action-pins";
        language = "system";
        files = actionPinsFiles;
        pass_filenames = false;
      };
      check =
        { vigUtils, ... }:
        {
          enable = true;
          name = "check-action-pins";
          entry = "${vigUtils}/bin/check-action-pins";
          language = "system";
          files = actionPinsFiles;
          pass_filenames = false;
        };
    };
    bandit = {
      yaml = {
        name = "bandit (Python security linting)";
        entry = "uv run bandit -r packages/vig-utils/src/ assets/workspace/ -ll";
        language = "system";
        types = [ "python" ];
        pass_filenames = false;
      };
      check =
        { pkgs, ... }:
        {
          enable = true;
          name = "bandit";
          entry = "${pkgs.bandit}/bin/bandit -r packages/vig-utils/src/ assets/workspace/ -ll";
          language = "system";
          types = [ "python" ];
          pass_filenames = false;
        };
    };
    check-skill-names = {
      yaml = {
        name = "check-skill-names (enforce naming convention)";
        entry = "uv run check-skill-names .claude/skills";
        language = "system";
        files = "^\\.claude/skills/";
        pass_filenames = false;
      };
      check =
        { vigUtils, ... }:
        {
          enable = true;
          name = "check-skill-names";
          entry = "${vigUtils}/bin/check-skill-names .claude/skills";
          language = "system";
          files = "^\\.claude/skills/";
          pass_filenames = false;
        };
    };
    # Security exception expiry enforcement (#566). Ships to the scaffold
    # (consumer repos carry .trivyignore/.vulnixignore too), so the
    # consumer render keeps the PATH-portable `uv run` entry.
    check-expirations = {
      scaffold = true;
      yaml = {
        name = "check-expirations (.trivyignore/.vulnixignore expiry enforcement)";
        entry = "uv run check-expirations .trivyignore .vulnixignore";
        language = "system";
        files = expirationsFiles;
        pass_filenames = false;
      };
      check =
        { vigUtils, ... }:
        {
          enable = true;
          name = "check-expirations";
          entry = "${vigUtils}/bin/check-expirations .trivyignore .vulnixignore";
          language = "system";
          files = expirationsFiles;
          pass_filenames = false;
        };
      consumer = _: {
        enable = true;
        name = "check-expirations";
        entry = "uv run check-expirations .trivyignore .vulnixignore";
        language = "system";
        files = expirationsFiles;
        pass_filenames = false;
      };
    };

    # ── AI-agent identity + commit-message hooks (stage-gated / git-state
    #    hooks: never run by `--all-files`, runner-only; Refs #163) ────────
    prepare-commit-msg-strip-trailers = {
      yaml = {
        name = "strip agent trailers from commit message";
        entry = "uv run prepare-commit-msg-strip-trailers";
        language = "system";
        stages = [ "prepare-commit-msg" ];
        pass_filenames = true;
      };
    };
    check-agent-identity = {
      yaml = {
        name = "check agent identity";
        entry = "uv run check-agent-identity";
        language = "system";
        pass_filenames = false;
      };
    };
    validate-commit-msg = {
      yaml = {
        name = "validate commit message";
        entry = "uv run validate-commit-msg";
        language = "system";
        stages = [ "commit-msg" ];
        args = [
          "--types"
          "feat,fix,docs,chore,refactor,test,ci,build,revert,style"
          "--scopes"
          "agent,ci,setup,image,vigutils"
          "--refs-optional-types"
          "chore"
          "--blocked-patterns"
          ".github/agent-blocklist.toml"
        ];
      };
    };
  };

  # ── Renders ───────────────────────────────────────────────────────────
  # PATH-portable pre-commit config data (the committed YAML artifacts).
  # `includeAll = false` restricts to the scaffold subset (`scaffold = true`).
  portableFor =
    includeAll:
    let
      selected = lib.filterAttrs (
        _: d: (d.yaml or null) != null && (includeAll || (d.scaffold or false))
      ) hookDefs;
      repoOrder = [
        "pre-commit-hooks"
        "local"
        "yamllint"
        "pymarkdown"
      ];
      hooksOf =
        repoKey:
        lib.mapAttrsToList (id: d: { inherit id; } // d.yaml) (
          lib.filterAttrs (_: d: (d.repo or "local") == repoKey) selected
        );
      blockFor =
        repoKey:
        let
          hs = hooksOf repoKey;
        in
        lib.optional (hs != [ ]) (
          (if repoKey == "local" then { repo = "local"; } else remoteRepos.${repoKey}) // { hooks = hs; }
        );
    in
    {
      exclude = yamlExclude;
      # Build python-language hooks with the project interpreter (3.14) so
      # PEP 758 syntax never false-flags under an older parser (#803).
      default_language_version.python = "python3.14";
      repos = lib.concatMap blockFor repoOrder;
    };

  # git-hooks.nix hook attrsets for a given artifact (`check`/`consumer`).
  collectFor =
    field: nameField: ctx:
    lib.listToAttrs (
      lib.mapAttrsToList (id: d: lib.nameValuePair (d.${nameField} or id) (d.${field} ctx)) (
        lib.filterAttrs (_: d: (d.${field} or null) != null) hookDefs
      )
    );
in
{
  # Data for `nix eval .#lib.hooksPortable` — the drift gate's SSoT side.
  portable = {
    runner = portableFor true;
    scaffold = portableFor false;
  };

  # Arguments for git-hooks.nix `run` building the sandbox-pure
  # `checks.pre-commit` gate. ctx: { pkgs, treefmtWrapper, vigUtils, python }.
  checkArgs = ctx: {
    excludes = baseExcludes;
    hooks = collectFor "check" "checkName" ctx;
  };

  # Base hook set for the consumer generation surface
  # (`mkProjectShell { hooks = …; }`). ctx: pkgs.
  consumer = pkgs: {
    excludes = baseExcludes;
    hooks = collectFor "consumer" "consumerName" pkgs;
  };
}
