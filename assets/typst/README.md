# Offline Typst registry

The `docs` module wraps Typst and Tinymist with the immutable registry built by
[nix/typst-packages.nix](../../nix/typst-packages.nix). The compiler and language
server search the consumer's `TYPST_PACKAGE_PATH` (a path list), then this
registry, then the standard data-directory `typst/packages`. First match wins
per namespace/name/version. Hooks and recipes use the same composition.
Typst 0.15 itself accepts only one directory and replaces data-dir lookup when
`TYPST_PACKAGE_PATH` is supplied. Wrappers build a temporary symlink union and
remove it after the child exits. SIGTERM and SIGINT are forwarded to the child,
including watch commands. Dependency flags accept both `--opt value` and
`--opt=value`. JSON, Make and NUL-delimited (`zero`) dependencies are rewritten
to stable source paths before cleanup, in files and with `--deps -` on stdout.
Dependency stdout is buffered until the child exits; other tool stdout streams
normally. Make prefixes escape spaces, tabs, `#`, `$` and `:`. If a resolved package root
contains CR, LF or backslash, Make output is preserved verbatim because that
root cannot be encoded safely by this rewriter; its temporary paths can become
dangling. JSON and `zero` are preferred for those paths. Artifact I/O errors
are reported on stderr and leave the native file unchanged; they never turn a
successful compile into failure. File replacement is atomic. Explicit CLI `--package-path` takes precedence over the wrapper
environment, as it does in native Typst.

## Local package versions

The active source lives in `devkit-docs/`, with independent SemVer in
`devkit-docs/typst.toml`. The registry retains the initial 0.1.0 snapshot alongside 0.1.1.
`devkit-docs.lock.json` maps each `namespace/name/version` to its SHA-256 content
hash, covering the local package versions and every vendored preview package.
Hash sorted file paths relative to each version directory followed by NUL,
then file bytes followed by NUL. Exclude only the injected `LICENSE` at each
local devkit-docs package root, whose source is devkit's license. Nested LICENSE
files and all vendored licenses are hashed. The sandbox check verifies every locked version
and compiles every retained import; source changes without a new version and
lock entry fail the check.

When changing a shipped package, first copy its exact source to
`releases/devkit-docs/<old-version>/`, then edit the active source and bump its
manifest version. Keep the old lock entry unchanged and add the new version's
hash. Never modify or remove shipped version directories or lock entries.
`released-packages.json` is an independent, append-only ledger of historical
packages. Add versions when archiving a shipped package; never remove its
entries. The check rejects removing a version together with its hash entry.
The active 0.1.1 remains unpublished until this PR lands; its reviewed source
and hash are updated together during review.
The Nix registry includes retained directories alongside the active version;
patch upgrades therefore preserve older imports. Devkit-only release bumps
never change package versions. API-compatible changes use patch bumps;
incompatible changes bump the minor version before 1.0, the major thereafter.

## Vendored upstream packages

`vendor/preview/` contains unmodified archives from `https://packages.typst.org`:

| Package | Version | License | Archive SHA-256 |
| --- | --- | --- | --- |
| fletcher | 0.5.8 | MIT | `a61883a4af4ca923a37c597900e674f40dad3f7bde3f2a3d8fe8042e6ca8a66b` |
| cetz | 0.3.4 | LGPL-3.0-or-later | `4f4b5a8d311d519e749940a766fe50521e40c041129e1c91af0c42e61f307514` |
| oxifmt | 0.2.1 | MIT-0 | `16fac2923032c59727de01e84d42cac45e8790da28df56effca49f4de41b09d9` |

Each package includes its upstream `LICENSE`. Fletcher imports CeTZ, which
imports oxifmt. The complete dependency closure is present in the registry.
Public package re-exports retain their upstream APIs and licenses.

To update, download `https://packages.typst.org/preview/<name>-<version>.tar.gz`,
verify and record its SHA-256, inspect its manifest and all transitive imports,
and extract the entire archive into `vendor/preview/<name>/<version>/`. Change
imports in `devkit-docs/lib.typ` together with dependency directories. Remove
superseded directories. Use `git add -f assets/typst/vendor` because upstream
source directories may match repository-wide ignore rules. Do not run formatters
on upstream sources: the repository hook exclusion preserves archive bytes.
Run `nix build .#checks.x86_64-linux.typst-house-style --no-link -L` to prove
imports work without network or a populated cache, and review license changes.

See [the user guide](../../docs/NIX.md#house-style-package) for the public API.
