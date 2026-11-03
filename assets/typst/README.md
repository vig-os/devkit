# Offline Typst registry

The `docs` module sets `TYPST_PACKAGE_PATH` to the immutable registry built by
[nix/typst-packages.nix](../../nix/typst-packages.nix). The local package has its own version in
`devkit-docs/typst.toml` (currently 0.1.0), independent of devkit release bumps.
The flake input pins both the package and compiler. Generated Nix hook wrappers export the
same registry; scaffolded hooks and recipes inherit it from the docs shell.

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
