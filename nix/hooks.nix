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
#                   installation script (`null` = not generatable, e.g. the
#                   `uv run` generator/venv hooks like generate-docs or
#                   sync-manifest, which need THIS repo's scripts and venv).
#                   Stage-gated hooks ARE generatable (#1434): git-hooks.nix
#                   carries `stages`, and a vig-utils console script resolves
#                   as a store path via nix/vig-utils.nix — so the commit-msg
#                   / prepare-commit-msg / agent-identity hooks ship here too.
#                   Without them a direnv consumer's `.githooks/commit-msg`
#                   shim runs an empty stage, exits 0, and the repo has no
#                   local commit-message enforcement at all.
#
# `checkName`/`consumerName` map a committed hook id to the git-hooks.nix
# attribute name where they differ (git-hooks.nix pluralises some
# pre-commit-hooks ids, e.g. check-case-conflict -> check-case-conflicts).
{ lib }:
let
  # Topic-branch naming convention enforced by no-commit-to-branch:
  # chore/<summary>, <type>/<issue>-<summary>, worktree/<issue>, renovate/*;
  # main and dev are allowed (pushing there is blocked server-side, not here).
  #
  # Workflow-model aware (#1224): the `(?!dev$)` clause protects the long-lived
  # gitflow `dev` branch, which a trunk workspace does not have — so the trunk
  # pattern drops it, mirroring EXACTLY the `s|(?!dev$)||` deletion
  # `render_workflow_model` (assets/init-workspace.sh) applies to the scaffolded
  # `.pre-commit-config.yaml`. The committed runner/scaffold YAML stays gitflow
  # (its trunk render is the scaffold path's job); only the flake-generated
  # consumer surface follows `workflow`.
  #
  # The `renovate/` clause (#1433) admits the Renovate app's tool-owned branch
  # namespace (like `worktree/<n>`): the bot commits server-side, but
  # maintainer fix-up commits on its branches (changelog conflict merges,
  # dist/ rebuilds) are a legitimate local flow. Permissive `.+` after the
  # prefix — Renovate composes names from dep names/version ranges (dots,
  # parentheses), so a charset pin would re-break on the next scheme.
  # Issue-numbered branch-type set (#1432): the ONLY knob-driven clause of the
  # pattern — DEVKIT_BRANCH_TYPES replaces this list (scaffold path:
  # render_branch_types in assets/init-workspace.sh; flake path:
  # mkProjectShell's `branchTypes`). The chore/renovate/worktree clauses stay
  # fixed. The default must render the pattern byte-identically to the
  # pre-#1432 literal (drift gate + zero-hooks parity).
  defaultBranchTypes = [
    "feature"
    "bugfix"
    "hotfix"
    "release"
    "docs"
    "test"
    "refactor"
  ];
  branchNamePatternFor =
    workflow: branchTypes:
    let
      devClause = lib.optionalString (workflow != "trunk") "(?!dev$)";
      typesAlternation = lib.concatStringsSep "|" branchTypes;
    in
    "^(?!main$)${devClause}(?!^(chore)/[a-z0-9]+(-[a-z0-9]+)*$)(?!^(${typesAlternation})/[0-9]+-[a-z0-9]+(-[a-z0-9]+)*$)(?!^renovate/.+$)(?!^worktree/[0-9]+$).+$";
  # The gitflow default, used by the committed runner/scaffold YAML renders.
  branchNamePattern = branchNamePatternFor "gitflow" defaultBranchTypes;

  # ── validate-commit-msg argv (knob-driven; #1431 + #1282) ──────────────
  # The approved commit types (DEVKIT_COMMIT_TYPES, #1431) and the Refs
  # enforcement policy (DEVKIT_REFS_POLICY, #1282) are ONE key each with two
  # scaffold-path renderers already in lockstep — `render_commit_types` /
  # `render_refs_policy` (assets/init-workspace.sh) for the scaffolded YAML,
  # and resolve-toolchain's `commit-types` / `refs-optional-types` outputs for
  # CI's validate-commit-range. `validateCommitMsgArgs` is the THIRD renderer,
  # for the flake-generated consumer surface (#1434), and must resolve
  # identically: same default list, same `optional` mirror of the RESOLVED
  # types (never a hardcoded copy of the stock 11 — the #1431 composition
  # fix), same `none` sentinel for `required` (an empty list reads as falsy to
  # the CLI and reverts to its {chore} default). Charset validation lives at
  # the write paths (init-workspace.sh; mkProjectShell's eval-time assert).
  defaultCommitTypes = [
    "feat"
    "fix"
    "docs"
    "chore"
    "refactor"
    "perf"
    "test"
    "ci"
    "build"
    "revert"
    "style"
  ];
  refsOptionalTypesFor =
    refsPolicy: commitTypes:
    if refsPolicy == "optional" then
      lib.concatStringsSep "," commitTypes
    else if refsPolicy == "required" then
      "none"
    else
      "chore";
  validateCommitMsgArgs = refsPolicy: commitTypes: [
    "--types"
    (lib.concatStringsSep "," commitTypes)
    "--refs-optional-types"
    (refsOptionalTypesFor refsPolicy commitTypes)
    "--blocked-patterns"
    ".github/agent-blocklist.toml"
  ];
  # The unset-knob default, used by the committed runner/scaffold YAML renders
  # and as the parity baseline of the consumer render.
  defaultValidateCommitMsgArgs = validateCommitMsgArgs null defaultCommitTypes;

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
  };

  # Shared per-hook filters used by more than one artifact of the same hook.
  # .envrc files are direnv stdlib scripts with no shebang (SC2148).
  #
  # assets/guardrails/ is VENDORED shell (#1488). It is clean at
  # `-S warning` — the severity where real bugs live — and is covered by
  # `checks.guardrails-canary`, which runs every gate against a known-bad
  # fixture and asserts it fires. What it is NOT clean at is the default
  # `style` severity: 18 findings, ten of them SC2181 (`$?` rather than
  # `if cmd;`), several of them deliberate in a test harness.
  #
  # Rewriting 3,000 lines of working, fixture-covered shell for style points
  # is the trade this repo already declined once when it decided not to port
  # these gates to Python: the risk is asymmetric, because a subtly broken
  # gate REPORTS SUCCESS. The bar kept here is error+warning, enforced by
  # `checks.guardrails-shellcheck`, not an exemption from review.
  shellcheckExclude = "(^|/)\\.envrc$|^assets/guardrails/";
  # The three JSONC scaffold files carry a `//` provenance banner (#1053) that
  # VS Code and the devcontainer CLI accept but check-json's strict parser
  # rejects. Exclude them from every check-json surface (matched at repo root or
  # under assets/workspace/); strict-JSON files (renovate.json etc.) stay checked.
  checkJsonExclude = "(^|/)(\\.devcontainer/devcontainer\\.json|\\.vscode/settings\\.json|\\.devcontainer/workspace\\.code-workspace\\.example)$";
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
      yaml = {
        exclude = checkJsonExclude;
      };
      check = _: {
        enable = true;
        excludes = [ checkJsonExclude ];
      };
      consumer = _: {
        enable = true;
        excludes = [ checkJsonExclude ];
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
    # Secret scanner (#1172). Opt-in and default-DISABLED: it carries no
    # `yaml` (absent from the committed runner and scaffold configs) and no
    # `check` (absent from the sandbox gate), so devkit's own lanes never run
    # it — gitleaks needs a repo-specific `.gitleaks.toml` to tune false
    # positives and devkit ships none. It lives only on the consumer
    # generation surface with `enable = false`, so a secret-bearing consumer
    # opts in with `mkProjectShell { hooks = { gitleaks.enable = true; }; }`.
    # A repo-root `.gitleaks.toml` is picked up by gitleaks automatically — no
    # extra plumbing. v8.19+ invocation form (`gitleaks git --pre-commit`; the
    # nixpkgs pin is 8.30.x). Refs #1172.
    gitleaks = {
      consumer = pkgs: {
        enable = false;
        name = "gitleaks";
        entry = "${pkgs.gitleaks}/bin/gitleaks git --pre-commit --staged --redact --verbose";
        language = "system";
        pass_filenames = false;
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
    # Markdown lint — a language:system hook resolved from the flake toolchain
    # (pymarkdownlnt packaged in nix/pymarkdown.nix, #1170), retiring the last
    # runner-only remote-repo residual of the hook SSoT (#883). All three
    # artifacts run the SAME `-c .pymarkdown fix` command over the SAME
    # `.pymarkdown` JSON config and README/CONTRIBUTING/TESTING excludes.
    #
    # `fix` (not `scan`) is deliberate and matches the runner/CI: pymarkdown fix
    # rewrites auto-fixable violations and exits 0 while *tolerating* unfixable
    # ones (e.g. MD013 line-length), so the hook fails only when it MODIFIES a
    # file — the same modify-and-fail semantics the ruff/end-of-file-fixer gate
    # hooks above rely on. The Nix gate operates on the sandboxed source copy, so
    # a fix never mutates the real tree; `scan` would be stricter than the runner
    # and would newly fail the gate on pre-existing unfixable markdown debt.
    #
    # THE FIX-MODE TRAP (#1574): three of pymarkdown's fixers are unsafe on
    # ordinary documentation — fenced code indented inside ordered list items —
    # so `.pymarkdown` ships md029, md031 and md046 DISABLED. md031 de-indents
    # the second of two consecutive in-list fences to column 0 and still exits
    # "success"; md029 renumbers deliberate continuation numbering (and crashes
    # the whole run with BadPluginFixError when it collides with md031, which
    # this comment's "tolerates unfixable violations" contract otherwise
    # promises cannot happen); md046 converts fenced blocks to indented ones by
    # deleting the fence markers, dropping their language tags. `pyml` pragmas
    # gate `scan` but NOT `fix`, so there is no per-site opt-out. Because the
    # hook fails on "files were modified", the operator reflex — re-add,
    # re-commit — is exactly how such a rewrite lands as an unreviewed lint fix.
    # All three reproduce on the pin (0.9.23) and on upstream 0.9.39
    # (jackdewinter/pymarkdown#1672/#1673/#1674), so a pin bump is NOT the
    # remedy: tests/test_pymarkdown_fix_safety.py re-runs the reproducers
    # against whatever version the flake pins. A scan-only consumer can
    # re-enable the three rules in its own (preserved) `.pymarkdown`.
    pymarkdown = {
      scaffold = true;
      yaml = {
        name = "pymarkdown";
        entry = "pymarkdown";
        language = "system";
        types = [ "markdown" ];
        args = [
          "-c"
          ".pymarkdown"
          "fix"
        ];
        exclude = "^(README\\.md|CONTRIBUTING\\.md|TESTING\\.md)";
      };
      check =
        { pkgs, ... }:
        {
          enable = true;
          name = "pymarkdown";
          entry = "${import ./pymarkdown.nix pkgs}/bin/pymarkdown -c .pymarkdown fix";
          language = "system";
          types = [ "markdown" ];
          excludes = [ "^(README\\.md|CONTRIBUTING\\.md|TESTING\\.md)" ];
        };
      consumer = pkgs: {
        enable = true;
        name = "pymarkdown";
        entry = "${import ./pymarkdown.nix pkgs}/bin/pymarkdown -c .pymarkdown fix";
        language = "system";
        types = [ "markdown" ];
        excludes = [ "^(README\\.md|CONTRIBUTING\\.md|TESTING\\.md)" ];
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
        entry = "${pkgs.nixfmt}/bin/nixfmt --check";
        language = "system";
        files = "\\.nix$";
      };
    };
    # Nix linters, flake-generated consumer surface ONLY (#1171). No `yaml`
    # and `scaffold = false`, so neither committed hand-managed YAML (runner
    # or scaffold) changes — existing container-mode consumers see zero
    # change until they opt into flake hooks. Devkit's own coverage stays
    # with the authored-flake-scoped `checks.{statix,deadnix}` gates in
    # flake.nix (#777), which deliberately keep the STRICT deadnix defaults.
    statix = {
      scaffold = false;
      # statix accepts exactly ONE target, so run it repo-wide from the root
      # (it respects .gitignore) rather than on the changed filenames.
      consumer = pkgs: {
        enable = true;
        name = "statix";
        entry = "${pkgs.statix}/bin/statix check .";
        language = "system";
        files = "\\.nix$";
        pass_filenames = false;
      };
    };
    # deadnix relaxes the lambda checks (--no-lambda-arg
    # --no-lambda-pattern-names): the scaffolded consumer flake.nix ships the
    # idiomatic `{ self, … }` output pattern and the `extraPackages = pkgs:
    # [ ]` seed, whose intentionally-unused args strict deadnix flags — a
    # fresh scaffold must pass out of the box
    # (tests/test_flake_hooks.py::TestNixLintersConsumerSurface).
    deadnix = {
      scaffold = false;
      consumer = pkgs: {
        enable = true;
        name = "deadnix";
        entry = "${pkgs.deadnix}/bin/deadnix --fail --no-lambda-arg --no-lambda-pattern-names";
        language = "system";
        files = "\\.nix$";
      };
    };
    # `stages` is mandatory here (#1489): a hook with none runs at EVERY stage,
    # and typos passes filenames — so the commit-msg round hands it
    # COMMIT_EDITMSG. typos reads short letter runs inside abbreviated git
    # SHAs as misspelled words, and `git rebase --continue` writes the rebase
    # todo into that buffer as comment lines ("# pick <sha> # <subject>"), so
    # the commit is refused over a comment that never enters the message —
    # and the natural workarounds are editing git's own todo or --no-verify,
    # which this repo forbids. Pinning the pre-commit stage costs no coverage:
    # `prek run --all-files` and the CI lane both run it. The git-hooks.nix
    # surfaces (check/consumer) already default to pre-commit, so only the
    # portable YAML render needs the pin — all three are held by
    # tests/test_flake_hooks.py::TestTyposRunsOnlyAtPreCommit.
    typos = {
      scaffold = true;
      yaml = {
        name = "typos (source typo checker)";
        entry = "typos --force-exclude";
        language = "system";
        stages = [ "pre-commit" ];
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
    # Runner-only (no consumer fragment): the generator needs THIS repo's
    # scripts and venv. `stages` is the same fix as #1489 without the bug —
    # with none, the manifest generator reran at prepare-commit-msg and
    # commit-msg too, three `uv run` invocations per commit for one useful
    # result. It only ever has anything to say about staged files, so
    # pre-commit is the one stage it belongs at. Refs #1491.
    sync-manifest = {
      yaml = {
        name = "sync-manifest";
        entry = "uv run python scripts/sync_manifest.py sync assets/workspace/";
        language = "system";
        pass_filenames = false;
        stages = [ "pre-commit" ];
      };
    };
    # Runner-only and devkit-only (#1534): it guards THIS repo's CHANGELOG.md,
    # which is manifest-synced into the scaffold and git-tracked by every
    # devcontainer-mode consumer — whose `.typos.toml` is seeded once and never
    # overwritten, so a word needing a newer allowlist entry than that seed
    # breaks the consumer's upgrade at the commit step (#1529) and can never be
    # reworded once released. The gate lints the `## Unreleased` section with NO
    # allowlist (`typos --isolated`), before the text can reach a release;
    # released sections keep their allowlisted tokens and are out of scope. Not
    # scaffolded: a consumer's changelog is synced nowhere, and the entry is a
    # `uv run` script from this repo. Filtered + pre-commit-pinned so an ordinary
    # commit pays nothing for it (#1491).
    check-unreleased-typos = {
      yaml = {
        name = "check-unreleased-typos (no-allowlist lint of the Unreleased section)";
        entry = "uv run python scripts/check_unreleased_typos.py";
        language = "system";
        files = "^CHANGELOG\\.md$";
        pass_filenames = false;
        stages = [ "pre-commit" ];
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
    # (consumer repos carry .trivyignore/.vulnixignore too), so the committed
    # YAML renders keep the PATH-portable `uv run` entry, while the consumer
    # fragment resolves a nix/vig-utils.nix store path like every other
    # tool-naming consumer fragment (#1447, same defect as #1434): `uv run`
    # resolves against the *consumer's* project venv, which carries no
    # vig-utils and which many consumers do not have at all.
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
      consumer = pkgs: {
        enable = true;
        name = "check-expirations";
        entry = "${import ./vig-utils.nix pkgs}/bin/check-expirations .trivyignore .vulnixignore";
        language = "system";
        files = expirationsFiles;
        pass_filenames = false;
      };
    };

    # ── AI-agent identity + commit-message hooks (stage-gated / git-state
    #    hooks: `--all-files` never runs the two message hooks; Refs #163) ──
    #
    # All three carry a `consumer` fragment (#1434): a direnv consumer on
    # flake-generated hooks (#1167) otherwise got NO commit-msg stage at all,
    # so its `.githooks/commit-msg` shim exited 0 with nothing to run and
    # `git commit --author="Claude <…>"` passed locally. The consumer entries
    # resolve nix/vig-utils.nix store paths rather than the portable `uv run`
    # form — a consumer's project venv does not carry vig-utils, whereas the
    # flake ships it (nix/devtools.nix) — so the enforcement version follows
    # the devkit pin the consumer bumps with `nix flake update vigos`. Same
    # shape as every other tool-naming consumer fragment (nixfmt, statix,
    # deadnix, just-fmt, gitleaks, pymarkdown), and like pymarkdown it builds
    # from a plain `pkgs`, so the generation surface never depends on the
    # consumer having applied `overlays.default`.
    #
    # No `check` fragments: the sandbox gate has no git repo and no commit to
    # inspect, and `check-agent-identity` short-circuits under CI=true anyway.
    #
    # Scaffolded: the consumer's `.githooks/prepare-commit-msg` already runs
    # `prek run --hook-stage prepare-commit-msg`, and this must reach consumers
    # together with validate-commit-msg — it strips agent trailers *before* the
    # validator's blocklist gate sees them, so an agent-authored commit is
    # repaired rather than hard-rejected. Refs #1019.
    prepare-commit-msg-strip-trailers = {
      scaffold = true;
      yaml = {
        name = "strip agent trailers from commit message";
        entry = "uv run prepare-commit-msg-strip-trailers";
        language = "system";
        stages = [ "prepare-commit-msg" ];
        pass_filenames = true;
      };
      consumer = pkgs: {
        enable = true;
        name = "strip agent trailers from commit message";
        entry = "${import ./vig-utils.nix pkgs}/bin/prepare-commit-msg-strip-trailers";
        language = "system";
        stages = [ "prepare-commit-msg" ];
        pass_filenames = true;
      };
    };
    # Scaffolded: the two commit-msg hooks above guard the commit *message*,
    # but this is the only #163 hook that guards the *author/committer* —
    # the one that catches `git commit --author="Claude <...>"`. Without it
    # in the consumer render, a scaffolded repo rejects an AI-attributed
    # message while accepting an AI-authored commit, the exact false
    # guarantee its COMMIT_MESSAGE_STANDARD.md warns against. It is
    # pre-commit-stage, so `prek run --all-files` also enforces it in the
    # scaffold's lint job. The blocklist it reads (.github/agent-blocklist.toml)
    # is already manifest-synced into the scaffold. Refs #1031.
    #
    # "pre-commit-stage" above was only ever true of the consumer fragment,
    # which git-hooks.nix defaults there; the yaml fragment carried no `stages`
    # and so ran at all three, and the two surfaces disagreed about when this
    # hook fires. Pinning reconciles them, and the message stages are the ones
    # to drop: git exports GIT_AUTHOR_NAME/GIT_AUTHOR_EMAIL to every stage of
    # an ordinary commit with identical values — including under an `--author=`
    # override, the case this hook exists for — so the commit-msg round re-reads
    # what pre-commit already rejected on. The lone path where the message
    # stages fire and pre-commit does not is `git merge`, and git exports no
    # author there at all: the hook falls back to `git config user.*`, the
    # persistent identity that fails the committer's very next ordinary commit.
    # That leaves a merge as the one commit this no longer guards locally, in
    # exchange for dropping two of three runs per commit. Refs #1491.
    check-agent-identity = {
      scaffold = true;
      yaml = {
        name = "check agent identity";
        entry = "uv run check-agent-identity";
        language = "system";
        pass_filenames = false;
        stages = [ "pre-commit" ];
      };
      consumer = pkgs: {
        enable = true;
        name = "check agent identity";
        entry = "${import ./vig-utils.nix pkgs}/bin/check-agent-identity";
        language = "system";
        pass_filenames = false;
      };
    };
    # No `--scopes` allowlist: a scope is free-form "alphanumeric and hyphens
    # only" per docs/COMMIT_MESSAGE_STANDARD.md, which the validator's subject
    # regex already enforces. The old five-scope pin rejected ~49% of the
    # scopes in actual use and would break the bots (Renovate invents a scope
    # per ecosystem) the moment enforcement went live. Refs #1019.
    #
    # Scaffolded: without it the consumer's `.githooks/commit-msg` shim
    # (`prek run --hook-stage commit-msg`) has no hooks to run, so every
    # scaffolded repo shipped a COMMIT_MESSAGE_STANDARD.md it could not
    # enforce. Refs #1019.
    #
    # The consumer fragment ships the DEFAULT argv; `consumer` below overrides
    # it only when DEVKIT_COMMIT_TYPES / DEVKIT_REFS_POLICY resolve to
    # something else, exactly like the branch guard — so an unset-knob
    # consumer's generated config stays byte-identical to the pre-#1434
    # render.
    validate-commit-msg = {
      scaffold = true;
      yaml = {
        name = "validate commit message";
        entry = "uv run validate-commit-msg";
        language = "system";
        stages = [ "commit-msg" ];
        args = defaultValidateCommitMsgArgs;
      };
      consumer = pkgs: {
        enable = true;
        name = "validate commit message";
        entry = "${import ./vig-utils.nix pkgs}/bin/validate-commit-msg";
        language = "system";
        stages = [ "commit-msg" ];
        args = defaultValidateCommitMsgArgs;
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
  # (`mkProjectShell { hooks = …; }`). ctx: pkgs, then the `.vig-os` knobs the
  # scaffolded flake.nix forwards. Each knob tunes exactly one base hook so a
  # flake-hooks consumer's local enforcement follows the same manifest keys as
  # the scaffolded YAML renders:
  #
  #   workflow    — DEVKIT_WORKFLOW,     branch guard dev-clause      (#1224)
  #   branchTypes — DEVKIT_BRANCH_TYPES, branch guard alternation     (#1432)
  #   commitTypes — DEVKIT_COMMIT_TYPES, validate-commit-msg --types  (#1431)
  #   refsPolicy  — DEVKIT_REFS_POLICY,  --refs-optional-types        (#1282)
  #
  # An attrset (not positional args): every knob is an optional nullable value
  # and the list keeps growing. Each override is applied ONLY when the resolved
  # value differs from the default, so an unset-knob consumer's generated
  # config stays byte-identical to the pre-knob render (zero-hooks parity +
  # consumer-surface tests).
  consumer =
    pkgs:
    {
      workflow ? "gitflow",
      branchTypes ? null,
      commitTypes ? null,
      refsPolicy ? null,
    }:
    let
      base = collectFor "consumer" "consumerName" pkgs;
      # Branch guard: workflow (#1224) and branch-types (#1432) feed one
      # computation.
      effectiveBranchTypes = if branchTypes == null then defaultBranchTypes else branchTypes;
      effectivePattern = branchNamePatternFor workflow effectiveBranchTypes;
      # validate-commit-msg argv: commit-types (#1431) and the Refs policy
      # (#1282) feed one computation, because `optional` mirrors the resolved
      # types list.
      effectiveCommitTypes = if commitTypes == null then defaultCommitTypes else commitTypes;
      effectiveValidateArgs = validateCommitMsgArgs refsPolicy effectiveCommitTypes;
    in
    {
      excludes = baseExcludes;
      hooks =
        base
        // lib.optionalAttrs (effectivePattern != branchNamePattern) {
          no-commit-to-branch = base.no-commit-to-branch // {
            settings = base.no-commit-to-branch.settings // {
              pattern = [ effectivePattern ];
            };
          };
        }
        // lib.optionalAttrs (effectiveValidateArgs != defaultValidateCommitMsgArgs) {
          validate-commit-msg = base.validate-commit-msg // {
            args = effectiveValidateArgs;
          };
        };
    };
}
