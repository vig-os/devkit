# Nix in the vigOS devcontainer

This repository is **Nix-first**: the Nix flake (`flake.nix`) is the single source
of truth for the development toolchain *and* the basis of the built devcontainer
image, so the dev-shell and the image can never drift. This document is the
consolidated reference for how the flake is structured and why. For day-one
onboarding (clone → `direnv allow`) see the fast path in
[`CONTRIBUTING.md`](../CONTRIBUTING.md); for the downstream production-image pattern
see [`docs/NIX2CONTAINER.md`](NIX2CONTAINER.md).

## The flake as the toolchain SSoT

The flake exposes one list, `devTools`, that enumerates every CLI in the
environment (`just`, `git`, `gh`, `uv`, `nodejs`, `jq`, `tmux`, `ripgrep`, `fd`,
`bat`, `eza`, `delta`, `lazygit`, `zoxide`, `starship`, `neovim`,
`podman`, `taplo`, `shellcheck`, …). Adding a tool there adds it
everywhere — the dev-shell now and the image's `imageTools` set.

- **`devShells.default`** is built from `devTools` via `mkProjectShell`, so
  `nix develop` (or `direnv`) gives you exactly that toolchain.
- **`mkProjectShell`** is also a reusable `lib` output: downstream repos build
  their own shell as `devTools ++ extraPackages` (see the scaffolded
  `assets/workspace/flake.nix`), optionally composing opt-in
  [capability modules](#capability-modules-mkprojectshell-modules) via
  `modules = [ "native" ]`. For projects that compile native Python
  extensions, the `native` module (or a hand-rolled `extraPackages`) is where
  the C/C++ toolchain comes from — see the
  [native-build contract](./MIGRATION.md#the-native-build-contract).
- **`mkProjectServices`** is the local-dev-services counterpart (#795): a `lib`
  builder that turns declared [services-flake](https://github.com/juspay/services-flake)
  modules into a daemonless `process-compose` stack (`nix run .#services`) —
  see [Local dev services](#local-dev-services-mkprojectservices) below.
- **`overlays.default`** and **`lib.{mkProjectShell,mkProjectServices,devTools}`**
  are exported as system-independent outputs so consumers can follow the same
  pinned `nixpkgs`.
- **`nixosModules.default`** / **`homeManagerModules.default`** install the same
  `devTools` set plus the machine-level agent CLI into a NixOS or home-manager configuration — flip
  `programs.vigos-devtools.enable = true`. `claude-code` is unfree, so the
  consumer must allow it (`nixpkgs.config.allowUnfree`). The NixOS module applies
  `overlays.default` for the fast-movers; a home-manager consumer that passes its
  own `pkgs` should apply the overlay itself (home-manager rejects a module-set
  `nixpkgs.overlays` in that case).
- **`apps.install`** wraps the host installer, so `nix run github:vig-os/devcontainer#install -- --help`
  bootstraps a consumer project straight from the flake — no prior `curl | bash`.
  `install.sh` remains the behavior SSoT; the app just wraps it.

### Agent CLI opt-in

Project shells leave `claude` to the machine by default. Install it machine-wide,
including through `vigos.packages.enable = true` (or the legacy
`programs.vigos-devtools.enable` home option). `nix/home/claude.nix` configures
Claude; the packages module continues to install its CLI. `templates/personal`
continues to use these machine-level modules.

Machines without their own CLI can set `withAgentCli = true` in
`vigos.lib.mkProjectShell { inherit pkgs; withAgentCli = true; }`, including in
the scaffolded `flake.nix`, or in `mkRustProject`. This adds the CLI to the
consumer's own project shell. To enter devkit's own project shell with the CLI,
use `nix develop github:vig-os/devkit#with-agent-cli` (inside a devkit checkout,
`nix develop .#with-agent-cli`). That output opens devkit's shell, not the
consumer's; consumers should set `withAgentCli = true` in their own flake.
Both options use the same fast-mover pin as the machine module. **Opting in shadows any system `claude` wrapper**, including its release
channel selection and per-profile credential loading. Updating an existing
scaffold's input adopts the new default; its project settings remain yours.

The image retains its agent CLI. The shared project tool list remains
`nix/devtools.nix`; the agent package is defined once in `nix/agent-tools.nix`.
To check the policy without building Claude Code, run
`nix eval .#checks.x86_64-linux.agentCliPolicy.drvPath` (substitute your system).

### Formatting, linting, and flake quality gates

`nix fmt` runs [`treefmt`](https://github.com/numtide/treefmt-nix) over every
supported language in one pass — `nixfmt-rfc-style` for `*.nix`, `ruff format` for
`*.py`, `taplo` for `*.toml`. It wraps the same formatters the pre-commit hooks
run, so the editor `nix fmt`, the hooks, and CI all agree on one formatting.

`nix flake check` runs the lightweight gates the sandbox can (recursive `nix`
access is unavailable, so the dev-shell/image parity test stays a CI pytest):

- **`formatting`** — the tree is `treefmt`-clean (the `nix fmt` idempotency gate).
- **`deadnix`** / **`statix`** — `flake.nix` carries no dead Nix code or lint
  anti-patterns. Scoped to the authored flake; the downstream scaffold
  (`assets/workspace/flake.nix`) and example keep their idiomatic `{ self, … }`
  signatures whose intentionally-unused args those linters would otherwise flag.
- **`devShell`** — the dev-shell closure builds.
- **`devShellTools`** — the parity-test SSoT evaluates to a non-empty list.
- **`agentCliPolicy`** — evaluation-only assertions exclude `claude-code` from
  default and scaffolded shells, verify the opt-in pin, and preserve home installs.
- **`module-<name>`** — one devshell build per shipped capability module,
  generated from the `nix/modules/` registry (a module cannot ship without
  its check).

### Dev-shell ↔ image parity guard

Because both the dev-shell and the image are assembled from `devTools`, a single
test keeps them honest. `tests/test_flake_devshell.py` reads the binary names
straight from the flake (`nix eval .#devShellTools`, derived from each package's
`meta.mainProgram`) and runs `nix develop -c <bin> --version` for every tool,
asserting it exits 0. The test list is generated *from* the SSoT, so it can never
drift from the tool list it guards. It is skipped automatically when `nix` is not
on `PATH` (e.g. the podman image CI lane).

## Capability modules (`mkProjectShell` `modules`)

`mkProjectShell` composes opt-in **capability modules**
([#884](https://github.com/vig-os/devkit/issues/884); contract and
composition rules in
[ADR-capability-modules](rfcs/ADR-capability-modules.md)): a consumer
declares a capability by name instead of hand-picking packages:

```nix
devShells.default = vigos.lib.mkProjectShell {
  inherit pkgs;
  modules = [ "native" ]; # opt-in capability modules
  extraPackages = [ pkgs.my-extra ]; # per-repo escape hatch, unchanged
};
```

- A module (defined in `nix/modules/`) contributes **packages, env vars, and
  shellHook fragments only** (v1 contract). `extraPackages` wins PATH lookup
  over module packages; the consumer `shellHook` runs last.
- **Zero cost when unused:** `modules = [ ]` (the default) produces a shell
  byte-identical to the pre-module builder — pure-Python consumers are
  untouched, and the **published image stays base-only** (modules are a
  direnv-mode/devshell feature).
- **Shipped:**
  - `native` — `stdenv.cc`, `cmake`, `gnumake`, `pkg-config` plus generic
    `CC=cc`/`CXX=c++` exports; the curated form of the
    [native-build contract](./MIGRATION.md#the-native-build-contract)'s
    preferred tier.
  - `node` ([#1027](https://github.com/vig-os/devkit/issues/1027)) — the
    Node/TypeScript capability: `nodejs` (which bundles `npm`) in the shell,
    for consumers who previously hand-wired `extraPackages = [ pkgs.nodejs ]`.
  - `docs` ([#1178](https://github.com/vig-os/devkit/issues/1178)) — the
    document-edition capability: `typst` (the document compiler), `typstyle`
    (its formatter), `tinymist` (the Typst language server with editor
    diagnostics and preview), and `poppler-utils`
    ([#1573](https://github.com/vig-os/devkit/issues/1573)) in the shell, for
    document-oriented consumers that previously pinned `typst` via PyPI.
    Opt in with:

    ```nix
    devShells.default = vigos.lib.mkProjectShell {
      inherit pkgs;
      modules = [ "docs" ];
    };
    ```

    **No version option in v1** — `typst`, `typstyle`, and `tinymist` come from
    the locked nixpkgs-unstable input via `fastMovers`, including consumers
    applying `overlays.default`. They share Typst minor 0.15 (currently 0.15.1,
    0.15.2, and 0.15.10 respectively). Pass the overlaid `pkgs` to
    `mkProjectShell`; direct module imports also use the supplied package set.

    ### Migrating to Typst 0.15

    This affects consumers of the `docs` module and `overlays.default`, plus
    anyone formatting with the image's typstyle: the 0.14.4 → 0.15.2 update
    can reformat `.typ` files. Rendered output changes too. Consumers comparing
    canonical PDF hashes against issued documents will see hash drift.
    Regenerate `generated/` deliberately in its own commit, review the output,
    and re-issue documents where your process requires it. Documents relying
    on Typst 0.14 behaviour may fail to compile; check the breaking changes in
    the [upstream Typst 0.15 changelog](https://typst.app/docs/changelog/0.15.0/).

    For stability, pin a devkit release tag and set
    `DEVKIT_FLAKE_PIN_ADVANCE=false` to hold it. Lockstep pins now advance
    with upgrades by default
    ([#1856](https://github.com/vig-os/devkit/issues/1856)); `devkit-upgrade`
    opens adoption PRs on a schedule. Typst tools now move with the weekly
    nixpkgs-unstable bump, so patch releases can change rendered output
    between devkit releases.

    **Language-server cost:** tinymist adds about 258 MB beyond the combined
    typst/typstyle closure on x86_64-linux (258,182,512 bytes at the current
    pin, measured with cache-only `nix path-info -S` and deduplicated runtime
    references). This cost applies to the opted-in docs shell; the image
    includes only typstyle.

    **PDF reading is part of the capability.** `poppler-utils` puts `pdftotext`
    and `pdftoppm` on the shell PATH: without them there is no CLI path from a
    PDF to text, and an agent's file reader — which shells out to `pdftoppm` to
    render a page — cannot open a PDF at all. Document-oriented consumers
    handle PDFs, and the ~140 MB closure is the small generic native CLI this
    module exists to carry. **Deliberate v1 exclusions:** pandoc/LaTeX
    (ask-gated until a consumer needs them), headless drawio/excalidraw export
    (electron-shaped, stays repo-owned), Python doc-processing libraries
    (`pymupdf4llm`, `openpyxl`) which belong in the consumer's own
    `pyproject.toml` via uv, and **OCR** — `tesseract` (1.11 GB) and `ocrmypdf`
    (1.68 GB) would charge every `docs` consumer an order of magnitude more than
    `poppler-utils` for a capability most never use, so it stays repo-local
    until a dedicated `ocr` module is justified.
  - **Candidates (ask-gated, not shipped):** `geant4`, `rust`, `fortran`/`f2py`,
    `root`.
- **Per-module options (the `node` version).** A `modules` entry is either a
  plain name string or an attrset `{ name = "<name>"; <options> }` — additive,
  the string form is unchanged. `node` takes one option, `version` (a Node
  major), selecting `pkgs.nodejs_<major>`; omitted, it uses the nixpkgs default:

  ```nix
  modules = [ { name = "node"; version = 22; } ]; # pin Node 22; plain "node" = default
  ```

  Unknown option keys and unavailable majors throw at eval time. Note the
  toolchain SSoT (`nix/devtools.nix`) already ships `nodejs` for the
  `@devcontainers/cli`, and the composition orders devTools before module
  packages — so a pinned `version` is prepended in the module's shellHook to
  actually win `node`/`npm` on PATH. An **EOL major** nixpkgs marks insecure
  (e.g. `nodejs_20`) throws unless the consumer opts into
  `permittedInsecurePackages`; prefer a maintained LTS for local dev.
- **What `node` does NOT do (v1 contract):** it contributes shell packages
  only — no eslint/prettier pre-commit hooks (that is the #883 consumer-hooks
  seam), no `.gitignore`/`codeql` language (those are the language-aware
  scaffold, [#1024](https://github.com/vig-os/devkit/issues/1024)/[#1025](https://github.com/vig-os/devkit/issues/1025)).
  Separately, a repo whose `package.json` is detected at its **first** scaffold
  gets npm-mapped `justfile.project` recipes seeded (`sync` = `npm ci`, plus
  `lint`/`test`/`build`/`bundle`) instead of the uv template, so `just sync` /
  `just test` work under Node; an existing `justfile.project` is never touched.
- Each shipped module gets a `checks.<system>.module-<name>` devshell build
  and a `tests/test_flake_modules.py` smoke test (for `native`, the uv
  C-extension sdist; for `node`, that `node`/`npm` resolve and the versioned
  form pins the major).

### Docs module: Typst guards and reproducible recipes

Enable `modules = [ "docs" ]` in `mkProjectShell` for the document toolchain.
Committed-config consumers receive hooks through scaffold reconciliation alone.
To request generated hooks explicitly, also set `hooks = { };`. Scaffolded
projects declare `DEVKIT_MODULES="docs"` in `.vig-os` and rerun the installer;
the default scaffold flake forwards docs activation. Other flakes, including
preserved and language-pack flakes, must also enable the module themselves. Enter the project toolchain before installing or upgrading:
reconciling a committed config requires its `reconcile-preserved-hooks` command on PATH.

`nix/hooks.nix` defines the four guards once. Its `portable.docs` render is committed
as `assets/docs-hooks.json`; CI checks that asset for drift. The installer adds an
owned block to committed hook configs and leaves generated store symlinks to the
flake. This keeps the module contract at packages/env/shellHook and supports both
config paths without teaching capability modules to overwrite consumer files.
Removing `docs` and rerunning the installer removes its block and recipes, restoring
consumer whitespace exclusions. `justfile.devkit-docs` is created with a managed header;
an existing file is overwritten or deleted only with that header. Consumer-owned
files (including symlinks) at that reserved name are retained with a notice in either module state.
The import is emitted only with docs ON and a devkit-managed recipe file. The
separate devkit name avoids collisions: consumer-owned `justfile.docs` files are
never touched or imported.
Comments and other hooks are preserved. Whitespace
configs must use block-style repositories and hook mappings without YAML aliases.
Mixed or legacy line endings are rejected without rewriting; uniform LF and CRLF
are preserved.
The docs module extends the existing preserved-hook range/splice engine (#1654),
using the same exact feature markers and insert/fold/drift report channels.
It extends an existing local hook sequence when available; otherwise it adds a
local repository block. This avoids repeating existing sequence lint findings.
Reversible exclusion records use repository and hook IDs, so hook insertion and
reordering are safe. Parsed values allow formatter re-quoting. Managed-block edits, including comments,
are detected before replacement; the installer warns with manual advice and
continues, retaining the original config. Pre-release blocks with the old state
format require manual removal of their block and generated exclusions first.
If a fixer hook is deleted or its repository URL changes (including adding
`.git`), restore that hook and URL, switch docs OFF, then reapply the edit and
switch ON. If `exclude` was moved before `id`, move it after `id` and retry.
Added inline comments on an injected exclude line require moving the comment to
its own line before retrying; reconciliation refuses them without dropping text.
If a restored fixer is missing its managed `exclude`, restore that value before
switching docs OFF. Keep the local repository containing the docs block until
after switching docs OFF. If that repository is deleted, generated exclusions
without a docs block trigger a warning when docs is enabled, and reconciliation
retains the config. With docs OFF, only devkit markers or recorded state trigger
reconciliation; consumer-owned generated exclusions and YAML anchors are left alone.
Restore the deleted repository/block and switch docs OFF before deleting it again.
Without the block's recovery records, exclusions cannot be safely undone.
Consumer-owned exclusions identical to the generated pattern are indistinguishable;
remove those exclusions by hand before retrying reconciliation.
The owned markers and state comments should be left intact. Both
staged and installed output pass `prek validate-config`; failures retain the original
bytes and print recovery instructions. Writes preserve the existing inode.
Rollback also writes in place: a second interrupt or I/O error during rollback
can prevent complete restoration. Restore the config from version control
before retrying in that case. Reconciliation preserves
consumer indentation, line endings, and final-newline presence. Enabling docs adds
no strict scaffold yamllint findings to configurations that were clean. Configurations
with existing findings (such as wide dash spacing or indentless hook lists) may
gain findings; review the result with your lint configuration. Existing `typst-compile` or
`typstyle` hooks are retained with a notice rather than duplicated.
Non-docs upgrades add empty `DEVKIT_TYPST_SKIP` and `DEVKIT_TYPST_FONT_PATHS`
keys, without additional hooks or a document-recipe import.

The guards are `typstyle-check` (`typstyle --check`), `typst-compile` (all declared
entries plus template smoke tests), `typst-preview-pins` (exact `@preview` versions),
and `forbid-generated-pdf` (PDFs under any `generated/` in the Git index, case-insensitively). Generic
whitespace, line-ending, and EOF fixers exclude `generated/` only with this module.
The compile and PDF guards run on every commit, including changes to dependencies.

Declare an entry with a standalone marker matching
`(?m)^[ \t]*//[ \t]*devkit:[ \t]*entry[ \t]*$`: `//devkit: entry`,
`// devkit: entry`, and trailing spaces or tabs are accepted. Suspicious unmarked
files (page settings, show rules, or headings) and zero declared entries produce
warnings when Typst files are present. Unmarked files are
libraries, including files used only through includes/imports. Files under `parts/`,
`generated/`, hidden directories, and `node_modules/` are excluded. Files under any
`templates/` directory compile independently to `/dev/null`. This explicit rule
avoids guessing entry points from Typst's dynamic imports. Add comma-separated,
repository-relative skip globs in `.vig-os`, for example
`DEVKIT_TYPST_SKIP="drafts/**,templates/experimental/**"`. Matching uses Python
fnmatch (including `/`); skips apply to entries and template smoke tests.

With docs enabled, the installer manages `justfile.devkit-docs`, loaded as
`mod devkit-docs 'justfile.devkit-docs'`. Document recipes live in the `devkit-docs` namespace,
so consumer recipes named `typst`, `typst-canonical`, or `typst-probe` remain usable.
Upgrades replace the former flat import or `docs` module; use the namespaced commands below.
If a consumer recipe, alias or module in `justfile`, `justfile.project` or
`justfile.local` already uses `devkit-docs`, the installer skips loading the
module and prints one notice. Rename that consumer declaration and rerun the
installer to enable document commands. Consumer `docs` declarations coexist.
Consumer-owned recipe files are retained and never loaded automatically:


- `just devkit-docs::typst [--deps]` builds sibling `generated/<stem>.pdf` files with
  `--input rev=<sha8>[-dirty]`; Git status determines the dirty suffix.
- `just devkit-docs::typst-canonical [--deps]` omits the revision input for hash comparisons.
- `just devkit-docs::typst-probe` prints JSON objects for Typst, typstyle, and tinymist, each
  containing a resolved binary `path`, single-line `version`, and `version_source`.
  Versions are parsed from each tool's own output. The pinned tinymist build omits
  its own version there, so its resolved Nix store version is reported explicitly
  with `version_source: "store-path"`; its embedded Typst version is never substituted.

Every compile uses `--root . --ignore-system-fonts`, clears `TYPST_FONT_PATHS`,
sets `SOURCE_DATE_EPOCH=0` and `TZ=UTC`, and rejects warnings. Fonts come from the
compiler's built-ins (Libertinus Serif, New Computer Modern, DejaVu Sans Mono).
For branding, set `DEVKIT_TYPST_FONT_PATHS="fonts:assets/fonts"` in `.vig-os`. Each
colon-separated directory must exist within the repository and is passed as
`--font-path` by hooks and both build recipes. Commit those fonts for reproducible
canonical output. System fonts remain ignored even with project fonts enabled.
Optional dependency lists are sibling `<stem>.deps.json` files. Ignore generated
outputs in your project's `.gitignore` so they do not dirty subsequent stamped
builds. Canonical hashes require identical source, packages, and pinned toolchains;
documents must tolerate an absent `sys.inputs.rev`. The house-style diagram dependency closure is vendored. Other preview packages
may need network access on first use. The pin guard conservatively
checks preview references in source, including comments. Typstyle 0.15.2 exposes
CLI formatting options with an 80-column default and no config-file option, so no
`typstyle.toml` is scaffolded. The real-tool canary is `checks.<system>.typst-canary`.


#### House-style package

The `docs` shell exposes an immutable registry through its Typst and Tinymist
wrappers; `DEVKIT_TYPST_PACKAGE_PATH` identifies that registry. Import
`@local/devkit-docs:0.2.0`. Its own SemVer is independent of devkit releases.
Shipped versions remain available after an upgrade, and a content-hash lock
checks their integrity. See the [version policy and registry layout](../assets/typst/README.md#local-package-versions).
A package upgrade is explicit: read its changes and update imports together.
If Typst reports `package not found`, enter the docs shell and check the version
in your import. Other packages remain consumer-owned.

Direct compiler calls, Tinymist, compile hooks and recipes search the consumer's
`TYPST_PACKAGE_PATH` path list first, then the devkit registry, then standard
Typst data-dir packages (`$XDG_DATA_HOME/typst/packages`, defaulting to
`~/.local/share/typst/packages` on Linux; `~/Library/Application Support/typst/packages`
on macOS). Typst 0.15 natively uses one path and skips the data directory when
that path is set; the wrappers compose these registries temporarily and clean
up after the process exits. First namespace/name/version wins. JSON dependency
inputs point to stable source files, including when `--deps` is used directly.
Both spaced and equals forms of `--deps` and `--deps-format` work. JSON, Make
and `zero` outputs are rewritten in files or on stdout (`--deps -`). See the
[registry guide](../assets/typst/README.md) for exact escaping limits and
artifact I/O behavior. SIGHUP/SIGTERM/SIGINT reach the child compiler, and
temporary registries are removed after it exits. Produced dependencies are
stabilized even after a failed compile or signal termination, without changing
the child exit status. Symlinked dependency paths retain the link and update
the resolved target.
Explicit CLI `--package-path` overrides this composition. Compilation errors,
including invalid registry directories, propagate to the caller.

A minimal entry document:

```typst
// devkit: entry
#import "@local/devkit-docs:0.2.0": *
#show: devkit-document.with(title: "Example report", authors: ("Example Author",))

= Results
#table(columns: 2, table.header([Item], [Value]), [Sample], number(12.3))
#fig(rect(width: 20mm, height: 10mm), caption: [Example figure])
```

Use the `#show: devkit-document.with(...)` namespace form. Calling the namespace directly is a type error; passing
body content to `.with(...)` gives an explicit show-rule usage error. Glob imports preserve the built-in `document` and `scale` functions. The defaults are A4, 2.5 cm margins, Libertinus Serif body text at 11 pt,
9 pt small text and captions, numbered headings at 20/16/13/11 pt, and a running
title and page `n / N`. Stamped builds also show `rev`; canonical builds omit
it. Monospaced text uses DejaVu Sans Mono and math uses Typst's built-in
New Computer Modern. `type-scale` exports these sizes, including `figure-min: 7pt`.
Authors must keep figure lettering at least 7 pt at the final placed size;
The plot helper enforces this minimum; checking external SVGs belongs to the later content guards.

All metadata is optional: `title`, `short-title` (running header/footer text),
`subtitle`, `authors` (a string or tuple of names),
`date` (display content), `version`, `status`, and `doc-id`. A title block
appears only for supplied values. Its first-page header is suppressed; the
footer still shows the short title (or title), page total, and optional revision. Branding parameters are `accent` (a color),
`logo` (a resolved Typst path), and `labels`
(a dictionary with optional `doc-id`, `version`, `status`, and `date` labels).
For project images use `logo: path("logo.svg")`; the `path` constructor resolves
the resource in your document before passing it to the package. See the
[Typst path reference](https://typst.app/docs/reference/foundations/path/).
There is no default branding.
The docs shell sets `TYPST_IGNORE_SYSTEM_FONTS=true`, including direct compiler
calls. Tinymist 0.15 does not read this variable; the module bridges the policy
to `--ignore-system-fonts` for its compile, preview, and LSP commands.

Plain `table(...)` uses booktabs: top and bottom rules, a rule below a bold,
repeating header, and no vertical rules. Declare headers with `table.header(...)`
(including multiple rows). Without an explicit header, body cells remain in their
original grid positions; no header is synthesized. Header `repeat` and `level`
settings are preserved. User `hline` and `vline` decorations are replaced by the
house rules, including lines inside or before a header. Table figures are
breakable and repeat their headers across pages by default.
Use `plain-table(...)` to opt out for one table: it accepts native table arguments
and preserves explicit or contextual `stroke`, `inset`, and line decorations.
A non-default `stroke` on an ordinary table also preserves native rendering.
Explicit arguments, `set table(...)`, and `show table: set table(...)` are
honored where Typst exposes their resolved values. A custom inset retains
booktabs when the stroke remains at its native default. Use
`booktabs-table(inset: 5pt, ...)` to request booktabs with any inset, including
Typst's native 5 pt. Typst exposes resolved values, not whether a default value
was explicitly supplied: an ordinary table with explicit `stroke: stroke()`
or `inset: 5pt` is indistinguishable from an omitted argument. Use `plain-table`
for exact native defaults, or `booktabs-table` for an explicit booktabs inset.
User labels and references work on both helpers. A nested plain-table only
opts out its own table; an enclosing ordinary table keeps booktabs.
Table column widths and alignment are retained. `number(value)`
right-aligns a numeric cell with tabular lining digits;
`align: numeric-columns(1, 2)` right-aligns zero-based numeric columns.
These helpers do not parse or round values or align decimal separators.

`fig(body, caption: [...], ..options)` forwards figure options and fails when
its caption is absent, empty, whitespace only, or solely hidden/zero-width
content. References, citations, styled text, context, images, math and unknown
content elements are accepted. Captions use 9 pt text in a
centered block at 85% of the available width. Table captions appear above;
other captions appear below. Direct `figure(...)` receives the style too;
requiring captions on every direct figure is part of later content guards.

`note(body, label: [Note], accent: ...)` and
`warning(body, label: [Warning], accent: ...)` render callouts. Override their
labels and colors explicitly for branding or translation.
`revision-history((version: "1", date: "2026-11-03", description: "Initial"), ...)`
accepts revision dictionaries; override its `labels` dictionary to translate
`version`, `date`, and `description` column labels.
`doc-ref(id, title: none, target: none)` prints an identifier and optional title;
`target` adds a Typst link (URL or label). It does not resolve document registers.

`fletcher` and `cetz` re-export the pinned upstream modules. Their complete
transitive dependency closure is vendored, with licenses and update instructions
in [the registry guide](../assets/typst/README.md).
`checks.<system>.typst-house-style` compiles real fixtures through guards and
recipes in a network-free Nix sandbox, checks PDF text and table rules, tests
caption failures and offline imports, and compares canonical hashes.

`plot(x, y, xlabel: [...], ylabel: [...], width: 9cm, height: 5cm)` renders a
native line plot using vendored lilaq 0.5.0. The coordinate arrays must satisfy
lilaq's data requirements. Both axis labels must contain visible content;
missing or blank labels panic. Tick and label text inherits `type-scale.small`
(9 pt); explicit label or math text below 7 pt panics. Synthesized `super`
and `sub` text uses 7 pt. Attached math scripts use a 14 pt base so New Computer
Modern's smallest script style (50%) stays at least 7 pt; ordinary math ticks
remain 9 pt. Dimensions change the data area,
without shrinking lettering. Wrap the result in `fig` with a caption:

```typst
#fig(
  plot((0, 1, 2), (1, 3, 2), xlabel: [Time (s)], ylabel: [Distance (m)]),
  caption: [Measured trajectory],
)
```

Do not shrink plots or label content with `scale`, `resize`, or transforms:
those can change final lettering size after the helper checks it. Arbitrary
user math (fractions, custom functions, contextual content, or manual math-size
styles) cannot be checked generically; authors must verify its final PDF text.
In particular, `$x^#text(size: 8pt)[k]$` can render the explicit text at 5.6 pt:
the explicit 8 pt style overrides the helper's script base before math shrinking.
Use ordinary attachments without explicit text sizes, or verify the final PDF.
The helper checks explicit text styles and sizes ordinary attached scripts. Prefer SVG
or native plots for charts; raster chart lettering cannot be checked.
The helper intentionally exposes a single line series and dimensions. For other
plot types use an explicitly pinned lilaq import; its upstream API does not
provide the helper's label and size checks. All transitive packages, including
optional computational plugins, are vendored and content locked.

`term("id")` reads the canonical term from the consumer register. Unknown or
duplicate IDs fail compilation. For an `acronym`, the first occurrence prints
`definition (term)`; later occurrences print the canonical term. Supply the
expanded name as the definition for acronym entries. `glossary()` renders only
used entries, sorted by canonical term, with definitions. Place it at the end
of the document as an appendix; `glossary(title: [Terminology])` changes its title.
An empty used-term set produces no heading. Usage and first-use state are local
to each compiled document, including terms in included files.

```typst
The #term("sample") was examined.
#glossary()
```

Load the register explicitly from the entry document's filesystem scope:

```typst
#show: glossary-setup.with(yaml("/glossary.yaml"))
```

Place this after the package import and before any terms, including outlines.
For a custom `DEVKIT_GLOSSARY`, pass that same file to `yaml` instead.
Hooks and recipes pass no glossary input arguments: large registers, plain
`typst compile --root . --ignore-system-fonts main.typ main.pdf`, and editor
previews all use this API and track file changes natively. `glossary-schema`
validates the configured register independently. Calling `term` without setup
reports “no glossary loaded”; setup rejects duplicate IDs. Outline and figure
outline copies use short forms and never consume the first body expansion.
Place custom `show outline.entry` rules **before** `glossary-setup`: rules added
after setup can replace its copy tracking and consume expansion in the TOC.
First usage includes footnotes: if the first `term` call is in a footnote, its
expansion appears in that footnote, and subsequent body calls use the short form.
Both `term` and `glossary` require setup; an empty YAML file or empty register
is an error. The glossary schema likewise requires at least one entry.

PDF bookmarks cannot evaluate the legacy state-based `term` function. For
headings with terms, bind the register before layout so bookmarks retain the
canonical spelling:

```typst
#let g = glossary-tools(yaml("/glossary.yaml"))
#let term = g.term
#show: g.setup

#outline()
= Using #term("cpu")
#glossary()
```

`glossary-tools` returns `term` and `setup` functions. Its setup validates the
register and installs the same outline-copy tracking; place custom outline
show rules before `#show: g.setup`. Keep the bound `term` in scope in each
included source (or export it from a consumer-owned shared module). The original
`glossary-setup` API remains supported, but its contextual terms have no PDF
bookmark text. Bound terms keep static canonical text in bookmarks while
retaining contextual first-use expansion in the body.

For presentations, use the same import with `#show: slides.with(...)`:

```typst
#show: slides.with(title: [Example deck], authors: ("Example Author",))
#section-slide[Results]
#slide(title: [Measurements])[
  #table(columns: 2, table.header([Item], [Value]), [Sample], number(12.3))
  #fig(rect(width: 20mm, height: 10mm), caption: [Example figure])
]
```

The layout is 256 × 144 mm (16:9), with 12 mm margins. A title slide is emitted
when metadata is provided. `section-slide` centers its title; `slide` starts a
content page with an optional heading. The same type scale, booktabs rules,
figure captions, branding (`accent`, `logo`, `labels`), metadata, `short-title`,
page totals and revision footer apply. Footer titles preserve emphasis, colour,
smallcaps, links, math, scripts, boxes, and images. Truncation prefers whole
words and re-wraps each prefix in its original styles; an oversized word falls
back to character prefixes. An ellipsis marks omitted content. A 2 mm column
gap separates the title from the page counter.

The footer occupies exactly one measured line (font ascender to descender).
Explicit line and paragraph breaks become spaces. Inline images and boxes
higher than the footer font size scale uniformly to that height, including
text inside a box; keep such boxes concise to avoid small lettering. The final
line also fits its vertical extent without clipping or distorting content.
Sizes remain in points: choose slide
content for the intended viewing distance. Content must fit a slide; there is
no automatic shrinking or overflow clipping. Canonical builds omit the stamp.

The network-free `typst-house-style` check also exercises these helpers with
an empty package cache and inspects rendered PDF font sizes. Content guards
(captions, table headers, style bypass and external SVG lettering) remain the
next part of [#1994](https://github.com/vig-os/devkit/issues/1994).

#### Terminology register

The docs module also installs `glossary-schema` and `glossary-terms` hooks.
Both validate the register; terms scans all selected sources on every run, so
register edits also check existing documents. Without `glossary.yaml` they do
nothing. Set `DEVKIT_GLOSSARY="docs/terms.yaml"` in `.vig-os` to select another
repository-relative register (an explicitly configured missing file fails).
The packaged `vig_utils/glossary.schema.json` defines a YAML list:

```yaml
- id: feed-pump
  term: Feed Pump
  definition: Moves fluid into the circuit.
  kind: part
  aliases: [Supply Pump]
  forbidden:
    - term: Input Pump
      use: Feed Pump
  part-number: FP-100
  pattern: 'FP-\d+'
  status: active
```

`id`, `term`, `definition`, and `kind` are required; IDs must be unique.
Kinds are `term`, `part`, `component`, `acronym`, and `role`; optional status is
`active` or `deprecated`. Duplicate YAML keys, names shared across entries
(casefolded), aliases forbidden by another entry (same spelling), and `use`
replacements absent from registered terms/aliases are rejected. Aliases must
be unique within each entry. Deprecation status alone does not reject a name.

Forbidden phrases normally match case-insensitively using Unicode casefolding.
When a forbidden spelling casefolds to a registered term or alias, it matches
case-sensitively: `Github` can suggest `GitHub`, and `us` can suggest `US`,
without rejecting the correct spellings. Registered term and alias occurrences
are protected, so a forbidden `pump` does not reject `Feed Pump` or `Supply Pump`.
Protection is case-insensitive except for names with casing corrections.
Underscores count as prose boundaries (`_emph_` and `__strong__`). Spaces, tabs,
NBSP, and newlines are interchangeable within phrases, including hard wraps.
Hyphens are literal characters, not whitespace separators.

Part patterns are Python regular expressions with inline flags, compiled
case-insensitively by default. Invalid flags, patterns matching empty text,
and a part number not fully matching its own pattern fail schema validation,
with the entry ID in the diagnostic. Known part numbers belong only to entries
sharing the **identical pattern string**; repeat that pattern on each part in
its family. A part with no pattern does not populate another family's known
set. Each unknown token occurrence is reported once, even for overlapping
families. Numbers inside scheme URLs (`https://...`), `mailto:`, and `www.`
URLs are skipped.

Only Git-tracked `.typ` and `.md` sources are scanned. Set comma-separated
`DEVKIT_GLOSSARY_SOURCES="docs/**,manual/*.{md,typ}"` to select Git pathspecs relative
to the repository root (`git ls-files` semantics after expanding brace
alternatives; nested braces are unsupported). Untracked/ignored files,
hidden directories, and `generated/` are excluded. There is **no non-Git
fallback**: terms mode with a nonempty register requires a Git working tree.
An undecodable source produces a file-specific UTF-8 error while other sources
are still checked. Schema mode validates only the register and never scans.

Append `// glossary: ignore` at the **end of a `.typ` line**, or
`<!-- glossary: ignore -->` at the **end of a `.md` line**. Trailing spaces are
allowed; trailing text and markers in the other file type do not suppress.
The marker suppresses that line; hard-wrapped matches cannot cross it.
Typst `/* glossary: ignore */` is not supported. Inline code and fenced code
are scanned as ordinary source text; use the same per-line marker for examples
that intentionally contain forbidden text. URLs and paths are also ordinary
text for forbidden phrases (only part-number detection excludes URLs).
Simple Markdown emphasis (`*`, `**`, `_`, `__`), code delimiters and Typst
`#strong[...]` / `#emph[...]` are transparent; nested markup, links and arbitrary
Typst expressions are not parsed. Emphasis is limited to a single line and
1,024 content characters; longer spans retain their delimiters. Inline markup
is unwrapped only at word boundaries so adjacent prefixes/plurals stay visible. Backticks become spaces, preserving code
boundaries and offsets (for example, a plural after a code span cannot hide a
forbidden term). Registered terms/aliases protect their exact spelling plus sentence-case
and title-case forms, unless a derived form is explicitly forbidden by any
entry. Literal registered names remain protected. ALLCAPS forms are not protected; use the per-line
suppression marker above for intentional ALLCAPS headings. Other case variants
remain unprotected; incidental lowercase matches such as `valve a little` do not.
A registered span suppresses a forbidden hit only if it contains the hit or crosses one of its edges. This protects
`the feed` in `the Feed Pump` and `pump station` in `Feed Pump station`. A
registered name contained inside the forbidden hit never suppresses it: with
`Valve` registered, `regulating valve` is still forbidden.
Overlapping forbidden hits are reported once, keeping the longest rule (ties
prefer the earliest position). Exact forbidden spellings equal to any registered
term or alias are rejected as dead rules; casing corrections remain valid.
Unsupported suffixes in source pathspecs warn on stderr. Run `glossary-guard schema` or `glossary-guard terms`
manually from the repository root.

Run `glossary-candidates` (or `just devkit-docs::glossary-candidates` with the docs module)
from the repository root for advisory candidate discovery. It uses the same
tracked source selection as terms mode, even without a register, and never
installs a blocking hook. Invalid registers fail before scanning. Unreadable or
non-UTF-8 sources are reported and skipped, remaining files are scanned, and
the command exits 1. Findings alone exit 0; diagnostics name the invoked tool.
Each JSON line contains `file`, first-occurrence `line`, `candidate`, per-file
`count`, `nearest` canonical term (or null), `score` (0–1 difflib similarity,
not confidence), and a short `context` snippet from the original source,
including its markup and line breaks. Aliases and registered part
numbers are subtracted case-insensitively. Output is ordered by file and name.

An agent or reviewer goes through **each candidate** in the PR and answers:

- **Synonym of X → use the canonical term.** Replace the invented name.
- **New term → add it to `glossary.yaml` in this PR.** Supply its definition,
  kind and any accepted aliases, then rerun both commands.

Extraction recognizes consecutive title-case words (also across a single line
break, never a blank line), CamelCase, letter/digit part numbers and ALLCAPS
acronyms. Leading and trailing stopwords are removed; coordinating conjunctions
split phrases while retaining the joined phrase as a candidate, and single
title-case words are ignored. `--allow And` disables splitting at And, preserving
names such as Research And Development. Joining stops at blank
lines, list items, headings and standalone two/three-word title-case name lines.
Prepared/reviewed/approved/signed/author labels followed by names are filtered.
This conservative name-line boundary can also separate a wrapped domain name.
Sentence-start connectives However, When, After, Before, Then, Also, Therefore,
Meanwhile, Finally, Thus and Next are default stopwords. Common words/acronyms such as TODO, NOTE, JSON, MIT, PR, CI, AM and PM are skipped;
add project-specific names with `glossary-candidates --stopwords NASA,FlowController`
(case-insensitive, comma-separated, additive to the built-in list in
`vig_utils.glossary.STOPWORDS`). The same option works with
`glossary-guard candidates --stopwords ...`. Remove built-ins or additional
stopwords with `--allow CD,EN` (case-insensitive; allow takes precedence).
Allowing a standards prefix also reports its numbers, such as `EN-123`; other
structural/code filters still apply. Both commands support these controls.

Discovery filters YAML frontmatter, Markdown/Typst headings, Markdown pipe-table
header rows, Markdown inline/reference links (including their text), URLs,
backtick code spans/fences, underscore identifiers, citations (`[@key]`, `@key`),
and Typst string literals and simple `#link(...)[text]` labels. Table body
prose and simple emphasized prose remain eligible. UTF, SHA, ISO, ANSI, RFC, IEEE, IEC, DIN and EN numeric standards are
filtered as standards rather than proposed parts. Deterministic terms mode
continues scanning code, links and paths as described above.

This is a lexical heuristic, not a grammatical noun parser or full markup
parser. Lowercase/single-word title-case names, nested markup, complex links,
non-pipe tables and unusual identifier/part/standard formats can be missed or
need reviewer judgment. An actual new name appearing only in a filtered region
is intentionally missed; register it during review. Ignore markers apply only
to deterministic checks.

The realistic Markdown/Typst fixtures in
`packages/vig-utils/tests/fixtures/glossary/` contain headings, tables, links,
URLs, code, citations, frontmatter, sentence-initial prose and Typst markup.
They contain five distinct expected names: **precision 100% (5/5), recall 100%
(5/5)**. Assertions also check repeated names, wrapped phrases, original-source
context, sorted output and the closest choice among multiple registered terms.
A second corpus in `fixtures/glossary/review/` models a README, commissioning
report and Typst note with tables, citations, code and links. Measured distinct-name
**precision is 100% (10/10), recall 90.9% (10/11)**; tests require ≥75% each.
The lowercase `service manifold` is missed, reflecting the documented lexical
limit rather than removing it from the expected set. These are fixture results,
not an accuracy claim for arbitrary documents.

Nearest-term comparisons are memoized per distinct candidate for each invocation.
Reproduce the synthetic workload with
`uv run python packages/vig-utils/tests/benchmark_glossary.py`: 300 tracked files,
15,000 lines, a 300-term register, eight distinct names and 2,400 output rows.
Single runs on the same shared host took **16.922 s before** (943a2f9b) and
**1.112 s after**, about 15.2× faster. Timings vary with host load; the permanent
cache regression asserts one comparison per term/name pair across files rather
than imposing a machine-dependent time threshold.
`uv run python packages/vig-utils/tests/benchmark_nearest.py` measures 2,000
distinct names × 300 terms: **12.645 s before** (21bd9717), **6.774 s after**
(about 1.9× faster, single shared-host runs). `real_quick_ratio` and `quick_ratio`
upper bounds skip full comparisons only when strictly below the best score;
equal-score ties retain the lexicographically greatest canonical spelling.
Before/after result hashes match, including every score and term choice.

For YAML language-server editor validation, put this header in the register,
replacing `RELEASE_TAG` with an installed devkit release tag that includes the
terminology register (for example, the tag recorded in your adoption PR):

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/vig-os/devkit/RELEASE_TAG/packages/vig-utils/src/vig_utils/glossary.schema.json
```

Pin the URL to that release tag, rather than `dev`, so editor and hook schemas
stay aligned. The schema's `$id` is its canonical development-source identity;
validation needs no network access because vig-utils packages the schema.
`jsonschema` and its runtime dependencies are available in every devkit image
and toolchain through vig-utils, even without the docs module. This shared
package uses the standard validator so the shipped JSON Schema is the single
structural-validation contract for both editors and hooks; hook activation
and source scanning remain opt-in.

### `packages.<system>.guardrails` — the gates without a `mkProjectShell` migration

The `guardrails` capability module (#1488, `nix/modules/guardrails.nix`) wraps
the org's vendored semantic gates and is normally reached through
`modules = [ "guardrails" ]`. `packages.<system>.guardrails`
([#1572](https://github.com/vig-os/devkit/issues/1572)) surfaces that same
derivation directly, for a consumer that already owns its own dev shell and a
committed pre-commit/prek config and only wants the gate binaries resolved
from the Nix store — not a `mkProjectShell` migration:

```nix
# flake.nix of a consumer that owns its own shell/hooks
devShells.default = pkgs.mkShell {
  packages = [ vigos.packages.${system}.guardrails ];
};
```

This composes with, rather than reopens,
[#1492](https://github.com/vig-os/devkit/issues/1492): the consumer's
`.pre-commit-config.yaml`/prek config stays consumer-owned — only the gate
binaries' provenance changes from PATH to the Nix store.

**Execution proof.** `$out/share/guardrails/gates/test-gates.sh` (already
shipped inside the package) is the supported way for a consumer to assert gate
execution in its own flake — the same script devkit's own
`checks.guardrails-canary` runs, feeding every gate a known-bad fixture and
asserting it is rejected:

```nix
checks.guardrails-canary =
  let
    guardrails = vigos.packages.${system}.guardrails;
  in
  pkgs.runCommand "guardrails-canary"
    { nativeBuildInputs = [ guardrails ] ++ guardrails.runtimeInputs; }
    ''
      bash ${guardrails}/share/guardrails/gates/test-gates.sh
      touch "$out"
    '';
```

## Home-manager modules — versioning & release policy

The `vigos.*` home-manager modules ([ADR](rfcs/ADR-home-environment-modules.md),
epic #814) are a **second product** of this flake with a consumer-facing API
(their options). Policy:

- **One release train.** Modules ship with the repo's existing tagged releases —
  there is no separate module release cycle. Consumers pin a tag:
  `vigos.url = "github:vig-os/devcontainer?ref=<tag>";` and bump deliberately
  (`nix flake update vigos`). Tracking `main`/`dev` is not a documented
  consumption mode.
- **Scaffold exception.** The workspace scaffold (`assets/workspace/flake.nix`)
  deliberately floats on the default branch so freshly scaffolded projects work
  before their first pin; the comment there points consumers at this policy for
  pinning once they depend on module stability.
- **Dogfood-canary exception.** The maintainer's personal configuration tracks
  `dev` during a module wave's dogfood phase (pre-release canary); the pin-tags
  policy applies to everyone else, and to it once the first module-bearing tag
  ships.
- **Deprecation.** Option renames keep a `lib.mkRenamedOptionModule` shim for
  one release and get a changelog entry. Removals are announced one release
  ahead.
- **Changelog.** Module-facing changes are grouped under a `#### Modules`
  sub-heading inside the relevant Keep-a-Changelog category of `## Unreleased`,
  so consumers can scan API changes without reading image/CI noise.

## Local dev services (`mkProjectServices`)

[ADR-nix-devenv-strategy](rfcs/ADR-nix-devenv-strategy.md) (#794) rejects
`cachix/devenv` as the shared shell builder but adopts the one capability it
bundled that plain `mkShell` lacks: `devenv up`-style orchestration of local
dev services. `mkProjectServices` (#795) is that replacement —
[`process-compose`](https://github.com/F1bonacc1/process-compose) (a single Go
binary: no daemon, no root) driving service definitions from
[`services-flake`](https://github.com/juspay/services-flake) (postgres,
seaweedfs, redis, mysql, grafana, kafka, …).

A consuming repo needs **no extra flake inputs** — both service flakes resolve
from this flake's lock — and wires it exactly like `mkProjectShell`:

```nix
packages.services = vigos.lib.mkProjectServices {
  inherit pkgs;
  modules = [ { services.postgres."db".enable = true; } ];
};
```

Then `nix run .#services` boots the stack (add `--tui=false` for headless use;
Ctrl-C tears everything down). The scaffolded `justfile.project` carries a
commented opt-in `services` recipe wrapping exactly that. Properties worth
knowing:

- **No container daemon.** Services run as native processes; the light
  direnv-mode promise ("no Docker on the host") is preserved.
- **Versions from the pinned `nixpkgs`.** Service binaries come from the
  caller's `pkgs` — the same lock, Renovate flow, and vulnix scanning as the
  toolchain; there are no out-of-lock image tags.
- **State lands in `./data/<name>`** relative to the invocation cwd — add
  `data/` to the repo's `.gitignore` (the scaffold ships this).
- **GC-rooted with the flake** (via direnv's GC root, like the dev-shell) and
  **zero import-from-derivation** — none of devenv's ~165 s cold-eval tax.
- **macOS:** evaluation is cross-platform (guarded by
  `tests/test_flake_services.py` against the darwin eval), but booting is only
  CI-exercised on Linux.

This repo's own flake carries the validating PoC: `nix run .#services` boots
**SeaweedFS (S3 gateway on `:8333`) + Postgres (`:5433`)**, asserted end-to-end
by `tests/test_flake_services.py` with no podman/docker anywhere in the test.

### Decision: standalone `evalModules`, not flake-parts

`services-flake` is idiomatically consumed via `flake-parts`, while this flake
(and the consumer stub) are `flake-utils`/`eachDefaultSystem`. The ADR left the
adopt-vs-manual question to #795; the resolution: **neither** — services-flake
documents a first-class no-flake-parts path
([`example/without-flake-parts`](https://github.com/juspay/services-flake/tree/main/example/without-flake-parts)),
where `process-compose-flake`'s `lib.evalModules` evaluates the same modules
standalone. `mkProjectServices` wraps that, so the flake structure is untouched
and consumers see a plain derivation. Both new inputs are dependency-free leaf
flakes: `flake.lock` gained exactly two entries and nothing to `follows`.

Measured cost (x86_64-linux, warm store): flake eval of the services app
~0.8 s, PoC closure build/substitute ~3 s, `process-compose` boot-to-healthy
(both services) ~3 s. For comparison, the devenv path this replaces paid ~165 s
of IFD on a cold eval.

### PoC S3 service: SeaweedFS, not MinIO

Issue #795 originally named MinIO, but `nixpkgs` marks `minio` **abandoned
upstream** with six unfixed CVEs (`meta.knownVulnerabilities`, both channels) —
building it requires a `permittedInsecurePackages` exception, the wrong default
for the org's blessed PoC. The PoC therefore ships the maintained,
S3-compatible **SeaweedFS** (`services.seaweedfs` with `filer.enable` +
`s3.enable`). A repo that truly needs MinIO for prod parity can still declare
`services.minio` and scope the insecure-package exception into the `pkgs` it
passes — consciously, per repo, never in the shared helper.

## Stable / unstable channel split and the fast-mover overlay

The flake pins two inputs:

- **`nixpkgs`** → `github:NixOS/nixpkgs/nixos-26.05` — the controlled, pinned
  stable channel (the "version document", anchored by `flake.lock`). Everything
  comes from here unless explicitly overridden.
- **`nixpkgs-unstable`** → `github:NixOS/nixpkgs/nixpkgs-unstable` — overlaid
  **only** for a small set of fast-moving tools.

The `overlay` (also exported as `overlays.default`) replaces just the `fastMovers`
list — `uv`, `gh`, and `claude-code` — with their `nixpkgs-unstable` builds.
These ship frequently; `claude-code` ships in machine profiles and the image,
and only in project shells that opt in;
everything else stays on the pinned stable channel for reproducibility.

### uv and the project interpreter

The dev-shell carries no Python on `PATH` (the project venv is uv-managed), so
`uv sync` must be told which interpreter to build the venv from. `mkProjectShell`
pins a Nix store CPython via `UV_PYTHON` and forbids downloads with
`UV_PYTHON_DOWNLOADS=never`. This avoids letting the nixpkgs `uv` fetch a managed
CPython: that download is a generic, dynamically-linked ELF a NixOS host cannot
execute out of the box (no FHS `ld-linux`), so `uv sync` (`just init`) aborted
there (#683). A store interpreter is patched to the store loader and runs in the
dev-shell on both NixOS and FHS hosts. The **image** path uses the same two
variables, baking the interpreter and toolchain from nixpkgs.

**CI is the exception.** The `setup-env` CI jobs (#632, #720) run *outside*
`nix develop` — they only prepend the dev-shell's tool `PATH` — on an FHS runner,
where a Nix store interpreter cannot load pre-commit's manylinux-wheel C
extensions (`libstdc++.so.6`). So the dev-shell also keeps
`UV_PYTHON_DOWNLOADS_JSON_URL` set (pinned to the provisioned `uv` release), and
the `setup-env` action forwards **that URL only** — not `UV_PYTHON` — so the
runner's stripped nixpkgs `uv` downloads a managed CPython instead. Locally the
pin wins and no download happens; the URL matters only on the CI runner.

## The Nix-built image

`packages.devcontainerImage` is assembled entirely by Nix via
**`dockerTools.buildLayeredImage`** — not a Dockerfile `FROM`. Key properties:

- **Bit-reproducible.** Every build from the same commit and `flake.lock`
  produces a byte-identical image closure (the epic's "identical image digest on
  rebuild" criterion). A deterministic `created = "1970-01-01T00:00:00Z"` epoch
  keeps the digest stable; there is no non-deterministic upgrade step.
- **Multi-arch.** The image builds natively on an amd64 + arm64 matrix (no QEMU,
  no cross-compilation); per-arch discovery tags are assembled into a multi-arch
  index.
- **Contents = `imageTools`.** That is `devTools` plus the runtime substrate a
  bare layered image lacks (an FHS base distro would otherwise supply it): the
  Nix evaluator (`nix`, `direnv`, `nix-direnv`), `glibcLocales` for locale
  support, the project Python env (`vig-utils` + `pip-licenses` baked via
  `python314.withPackages`), the `prek` hook runner (via `devTools`),
  Rust/just tooling
  (`cargo-binstall`, `just-lsp`, and the unstable Typst formatter `typstyle`),
  core GNU utilities, `cacert`,
  `openssh`, and `dockerTools.fakeNss` (a root uid-0 user database, without which
  `ssh`/`tmux`/`git` fail with "No user exists for uid 0").

A `bootstrap` layer bakes the workspace assets, the prek cache dir, the
template `.venv` scaffold, a sticky `/tmp`, and the `precommit`/`cc`/`cld`
aliases. The image's interpreter is pinned via `UV_PYTHON=<nix python3.14>` and
`UV_PYTHON_DOWNLOADS=never`.

### Building and iterating the image locally

Most contributors never build the image. `nix develop`/direnv gives the dev-shell
fast path for day-to-day work, and CI publishes the image to GHCR — so `just test`
pulls the published `dev` tag rather than building. Build locally only when you
are changing the **image itself** (its `imageTools`/`bootstrap` contents, baked
workspace assets, or the `flake.nix` image wiring) and want to test before pushing:

```bash
just build          # nix build .#devcontainerImage → podman load → tag <repo>:dev
just test-image     # run tests/test_image.py against the freshly loaded dev tag
```

`just build` tags the loaded image `<repo>:dev`; `just test-image`, `just
test-integration`, and `just test` all default to that `dev` tag (and
auto-`just build` it if it is missing). The iterate loop for image changes is
therefore: edit `flake.nix` → `just build` → `just test-image` → repeat. `nix
build` is content-addressed, so an unchanged closure rebuilds instantly and the
`no_cache` argument is a no-op.

### Host container runtime (`policy.json`)

`just build` ends in `podman load -i result`, and podman's containers/image
library refuses to load any image unless a signature-verification `policy.json`
exists at `~/.config/containers/policy.json` or `/etc/containers/policy.json`
(this podman build has no `--signature-policy` flag and no env override). The
flake dev-shell ships the **podman CLI** but not that host file: on NixOS the
`virtualisation.containers` module normally installs `/etc/containers/policy.json`,
so a host that gets podman purely from the dev-shell never receives one and
`podman load` fails — even though `podman info` (the `just init` advisory check)
is green.

`just init` closes this gap: if neither lookup path has a policy, it writes the
user-level default `~/.config/containers/policy.json` with the standard permissive
content (the same `{ "default": [ { "type": "insecureAcceptAnything" } ] }` that
`containers-common` / the NixOS module ship). The write is idempotent and never
overwrites a system or user policy. To do it by hand:

```bash
mkdir -p ~/.config/containers
printf '{ "default": [ { "type": "insecureAcceptAnything" } ] }\n' > ~/.config/containers/policy.json
```

## Evaluator and pre-commit decisions

These are decided inline in `flake.nix`; summarized here.

- **CppNix vs Lix (#634).** The image ships upstream **CppNix** (`pkgs.nix`) as
  the in-container evaluator. It is the channel default, needs no overlay, and the
  flake is installer-agnostic, so swapping to `pkgs.lix` later is a one-line
  change. `pkgs.lix` is left out for now to keep the closure smaller.
- **`pre-commit` → `prek` (#778, closes #40).** The git-hook runner is now the
  Rust **`prek`** (a drop-in for the Python `pre-commit`, faster and one fewer
  manylinux/FHS consumer). `prek` lives in the `devTools` SSoT, so it ships in
  both the dev-shell and the image; the standalone Python `pre-commit` is dropped
  from both. The `.githooks` shims (wired via `core.hooksPath`) call `prek run`,
  `just precommit` runs `prek run --all-files`, and the baked hook cache is
  `PREK_HOME=/opt/prek-cache`.

  **One hook definition, three renders (#883; supersedes the former
  "two hook artifacts" model).** `nix/hooks.nix` defines every pre-commit hook
  exactly once, and the flake renders it three ways:

  1. The flake's **`checks.pre-commit`** (built by `git-hooks.nix` with
     `package = pkgs.prek`) evaluates the definition's **sandbox-pure
     profile** under `nix flake check` — no network, no project venv. It
     reuses `treefmtEval` for the single formatting hook (nixfmt +
     ruff-format + taplo), the nix-provided pure linters (ruff, shellcheck,
     yamllint, typos, `taplo lint`), the `just --fmt --check`
     justfile-format check (the runner hook mirrored in check mode since the
     sandbox is read-only), the `pre-commit-hooks` meta hooks, and the
     `vig-utils`/`bandit` hooks wired to hermetic Nix binaries
     (`${vigUtils}/bin/…`, `${pkgs.bandit}/bin/bandit`).
  2. The committed **`.pre-commit-config.yaml`** (and its scaffold copy in
     `assets/workspace/`) is the definition's **PATH-portable render** — the
     runner config `prek` executes locally, in the image, and in the
     downstream scaffold. It stays a committed file rather than a gitignored
     store artifact so it is portable and does not churn on nixpkgs bumps,
     but it is no longer hand-maintained in parallel:
     `tests/test_flake_hooks.py` diffs the render
     (`nix eval .#lib.hooksPortable`) against both committed files
     (normalized, every hook id/args/files/excludes/stages) and fails CI on
     any drift. The former `sync-manifest` transform chain for the scaffold
     copy is retired — the fidelity test is the single agreement mechanism.
  3. The **consumer generation surface**: `mkProjectShell`'s opt-in
     `hooks`/`hooksExcludes` arguments compose the definition's consumer
     profile with per-repo overrides, and git-hooks.nix's installation
     script (in the `shellHook`) installs the rendered
     `.pre-commit-config.yaml` — gitignored and regenerated on shell entry,
     upstream's recommended model. See `docs/MIGRATION.md` ("Customizing
     pre-commit hooks from the project flake") for the consumer contract,
     including the guarantee that a preserved hand-edited YAML is never
     overwritten (#878) and the planned `.vig-os` manifest opt-out flag
     (#885).

### Opt-in `gitleaks` secret scanning (#1172)

`gitleaks` ships in the toolchain (`nix/devtools.nix` → dev-shell, image, and
`vigos.packages`) and is defined as a `language: system` hook, but it is
**default-disabled** and lives only on the consumer generation surface — it is
absent from devkit's own committed `.pre-commit-config.yaml`, the scaffold copy,
and the sandbox `checks.pre-commit` gate, so no devkit lane runs it. A
secret-bearing consumer opts in from its project flake:

```nix
devShells.default = vigos.lib.mkProjectShell {
  inherit pkgs;
  hooks = { gitleaks.enable = true; };
};
```

The hook runs `gitleaks git --pre-commit --staged --redact --verbose` (the
v8.19+ invocation) resolved from the pinned nixpkgs binary — no upstream
pre-commit repo clone, and it works offline. A repo-root `.gitleaks.toml` is
picked up by gitleaks automatically; no extra plumbing is needed to tune
allowlists. It is off by default deliberately: false-positive tuning is
repo-specific, and a red first `just precommit` on every existing consumer would
be a poor upgrade experience — so devkit ships no `.gitleaks.toml` and never
enables it for itself.

  Hooks that cannot run in the sandbox stay **runner-only** in the committed
  render and carry no gate profile in `nix/hooks.nix`: the generators
  `generate-docs`/`sync-manifest`, `pip-licenses` (reads `uv.lock`),
  `check-unreleased-typos` (a repo script over this repo's own `CHANGELOG.md`,
  #1534), `validate-branch-name` and `destroyed-symlinks`
  (git-state-dependent), `check-agent-identity` (inspects the commit
  author/committer), and the `commit-msg`/`prepare-commit-msg`-stage hooks (never
  run by `--all-files`). `checks.pre-commit` is thus a Nix-verified guarantee that
  the pure hooks stay correct; the impure ones remain
  covered by CI's `prek run --all-files`. One fidelity note: the meta
  `debug-statements` hook parses the file's Python AST, so its `git-hooks.nix`
  package is pinned to the 3.14 `pre-commit-hooks` build to match the runner
  interpreter (PEP 758 parenthesis-free `except A, B:`), and `check-yaml` runs
  with `--allow-multiple-documents` in **both** the Nix check (git-hooks.nix'
  built-in hardcodes `--multi`) and the committed runner, so the two agree on
  multi-document YAML instead of the gate being more lenient than the runner.

### `libstdc++` for C-extension pre-commit hooks (#698)

Historically some pre-commit hooks ran from pre-commit's **own** manylinux-wheel
Python env (not the project venv) and shipped a C extension. The `pymarkdown`
hook was the case in point: its dependency `pyjson5` is a C extension linked
against `libstdc++.so.6`, which a NixOS host does not put on the loader path
outside an FHS environment — so the hook aborted with
`ImportError: libstdc++.so.6: cannot open shared object file` and forced
`--no-verify`. That residual is now retired: `pymarkdownlnt` is packaged in the
flake (`nix/pymarkdown.nix`) and `pymarkdown` is a `language: system` hook
resolved from `devTools` like `ruff`/`typos`/`shellcheck` — the exact #697 recipe
that seemed not to apply while it was missing from nixpkgs (#1170). The gate and
the consumer generation surface now carry it too, so the hook set has no
runner-only lint residual left.

`mkProjectShell` still **appends** `${pkgs.stdenv.cc.cc.lib}/lib` to
`LD_LIBRARY_PATH` in the dev-shell, so any *runtime-installed* manylinux wheel
(e.g. a `uvx` tool, or a consumer's own C-extension hook) resolves the Nix C++
runtime. That is the same `libstdc++` the Nix toolchain itself links, so the
other dev-shell binaries keep working (no version clash), and the existing
mkShell-injected `LD_LIBRARY_PATH` is appended to rather than clobbered. It
remains a general safety net for any future C-extension Python hook. A `nix-ld`
host config (`programs.nix-ld.enable` + `libraries = [ pkgs.stdenv.cc.cc ]`)
would also work but is per-contributor system config the repo cannot enforce, so
it is at most a fallback, not the fix.

That `LD_LIBRARY_PATH` safety net only exists **inside** the dev-shell. In
`direnv`-mode CI the preamble forwards the dev-shell `PATH` but not its exported
environment, so a `uvx`-run tool on a non-Python repo (where the manylinux
exclusion of [#1028](https://github.com/vig-os/devkit/issues/1028) does not
apply and the Nix CPython stays on `PATH`) loads its native wheel with no
`libstdc++` on the loader path and aborts with
`libstdc++.so.6: cannot open shared object file`
([#1181](https://github.com/vig-os/devkit/issues/1181), otterdog's `rjsonnet` in
org-config#40). For that case the root `justfile` ships a base
`with-native-libs` recipe (all delivery modes — it is **not** in the
devcontainer-only `justfile.devc`) that wraps a single command with a
command-scoped `LD_LIBRARY_PATH`, sourced from `$VIGOS_STDCPP_LIB` (a dev-shell
`shellHook` export, when present) or otherwise derived from the on-`PATH` `cc`
wrapper via `cc -print-file-name=libstdc++.so.6`. A `justfile.project` recipe
that runs a `uvx` tool with a native extension prefixes it:

```just
validate:
    just with-native-libs uvx --from otterdog@1.2.3 otterdog validate --local
```

Scoping the variable to the one command keeps the Nix `libstdc++` out of every
other tool's process; when neither `$VIGOS_STDCPP_LIB` nor `cc` resolves the
library the command runs with the environment untouched — the recipe never
composes an empty prefix, because an empty `LD_LIBRARY_PATH` entry (a leading
colon or a bare `""`) means "current working directory" to the dynamic loader.
Only reach for it on a repo that runs `uvx`/`uv tool` tools with compiled
extensions under the Nix CPython; pure-Python tools need nothing.

## Cachix and the `direnv allow` onboarding flow

The dev-shell closure is published to the public **`vig-os`** Cachix binary
cache, so the first `direnv allow` is a binary fetch (seconds) rather than a
from-source build. To use it, enable flakes and add the substituter to your Nix
config (`~/.config/nix/nix.conf` or `/etc/nix/nix.conf`):

```conf
experimental-features = nix-command flakes
substituters = https://cache.nixos.org https://vig-os.cachix.org
trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= vig-os.cachix.org-1:yoOYRi3bvnM6ThxO0joLt7vtzhTfkq3r6jykeUMg7Bk=
```

Pulling from the public `vig-os` cache needs no token (`cachix use vig-os` writes
the same lines). Then:

```bash
git clone git@github.com:vig-os/devkit.git
cd devcontainer
direnv allow        # first allow fetches the closure from Cachix
```

The committed `.envrc` uses [nix-direnv](https://github.com/nix-community/nix-direnv):
the dev-shell evaluation is cached and GC-rooted under `.direnv/` (gitignored), so
re-entry is instant and the closure is never garbage-collected. nix-direnv
self-bootstraps the pinned library on first allow, or uses your
`~/.config/direnv/direnvrc` installation if you already source it; it falls back
to bare `use flake` when unavailable. The full fast path lives in
[`CONTRIBUTING.md`](../CONTRIBUTING.md).

### Image closures are cache-backed too (blocking push)

The cache is not just for the dev-shell. On the trusted paths the **image**
closure is pushed to `vig-os` Cachix as a **first-class, blocking** step (#776),
so published images are guaranteed cache-backed and consumers substitute the
closure instead of rebuilding it from source:

- `.github/actions/build-image` pushes the built `devcontainerImage` closure when
  its `push-image-closure` input is `true` (`nix path-info --recursive ./result |
  cachix push`). The release workflow (`build-and-test`) opts in, so every
  released image is cache-backed. The push is **blocking** (no
  `continue-on-error`) and guarded on a non-empty auth token, so per-PR CI stays
  **pull-only** and fork PRs (which lack the secret) never fail.
- The `Nix Image (discovery)` workflow pushes each per-arch image closure on
  `dev` as the same blocking step (distinct from the non-blocking GHCR discovery
  *tag* push).
- The release CVE gate also pushes the `devcontainerImageEnv` scan-target closure,
  so the vulnix scan surface is cache-backed as well.

## How `nixpkgs` bumps flow (Renovate + vulnix)

The pinned `nixpkgs` revision in `flake.lock` defines the image's entire CVE
surface, so advancing the pin is the **primary CVE-remediation lever** (see
[`docs/CONTAINER_SECURITY.md`](CONTAINER_SECURITY.md) for the full strategy).
Renovate keeps the pin current through `renovate.json`:

- The **`nix` manager** detects flake inputs and proposes pinned-input updates
  (committed as `build(nix): …`).
- **`lockFileMaintenance`** (enabled, scheduled weekly) refreshes the locked
  revisions of all inputs so upstream security fixes land through the normal
  PR/CI gate rather than a manual `nix flake update`.

**vulnix before/after requirement.** A `nixpkgs`-rev bump does not declare *which*
CVE it fixes — the `nix` manager reports only the old → new revision. To preserve
the audit trail, each `flake.lock` / `nixpkgs`-bump PR should include a `vulnix`
scan diff taken **before and after** the bump, showing which advisories the new
revision clears (or introduces). The nightly `vulnix` scan runs against the
`devcontainerImageEnv` closure; HIGH/CRITICAL findings are gated by `vulnix-gate`
against the `.vulnixignore` exception register.

### Brotli security fix in 1.18.1

The stable pin `08d3a97586f6b6343b3b5e799980773629432610` ships Google Brotli
1.2.1, fixing the decoder vulnerability
[CVE-2026-111497](https://github.com/advisories/GHSA-9v8h-qqgm-4m35).
Its advance includes 392 upstream commits affecting curl, Node.js, glibc, Go,
OpenSSH, and graphics libraries. The shipped runtime Brotli comes from stable;
no unstable overlay is needed. Derivation dependencies also include build tools
and must not be mistaken for the shipped runtime closure.

Vulnix 1.12.4 ignores the CPE vendor and incorrectly matches Google's 1.2.1
against the same-named Go port's affected range (below 1.2.7). The evidence is
registered in `.vulnixignore` as `CVE-2026-111497@brotli@1.2.1`, expiring
2026-12-02 with review on 2026-11-25. The exact exception leaves 1.2.0 blocking.
The release gate must still scan the rebuilt image's full runtime closure.

## Publish cutover

The build pipeline is Nix-only (the Debian path was decommissioned in #642), and
the nightly `vulnix` gate is **blocking** — any unexcepted HIGH/CRITICAL finding
fails the scan. The remaining step is the deliberate Nix release that flips the
versioned/`:latest` publish, tracked in **issue #639**; the nightly `vulnix` gate
is the go/no-go signal for it.

## See also

- [`docs/rfcs/ADR-nix-devenv-strategy.md`](rfcs/ADR-nix-devenv-strategy.md) — why
  the org uses `pkgs.mkShell` + `nix-direnv` (not `devenv`/`devshell`), the
  three-axis framing (activation / shell definition / local services), and the
  `process-compose` + `services-flake` decision for local dev services.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — onboarding fast path (clone → `direnv allow`).
- [`docs/NIX2CONTAINER.md`](NIX2CONTAINER.md) — the downstream production-image
  pattern with `nix2container` (distinct from this image's `buildLayeredImage`).
- [`docs/CONTAINER_SECURITY.md`](CONTAINER_SECURITY.md) — the full CVE-patching
  strategy (pinned `nixpkgs`, `vulnix`, SBOM/Trivy, exception registers).
- [`flake.nix`](../flake.nix) — the authoritative source for all of the above.
