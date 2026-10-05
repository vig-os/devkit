# Rust pack starter

A crate for the vigOS Rust pack (`lib.mkRustProject`, #1496): a library with a
doctest and a unit test, a binary, an integration test, `[lints]` and a
stripped release profile. It passes the pack's whole check suite as shipped.

Start a new repo with it, then scaffold devkit on top:

```bash
mkdir my-crate && cd my-crate && git init
nix flake init -t github:vig-os/devkit#rust
curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh | bash -s -- --mode direnv .
```

Order matters: `install.sh` detects `Cargo.toml` and then seeds

- a `flake.nix` on `vigos.lib.mkRustProject` (dev shell, `nix flake check`
  suite and `packages`),
- a cargo `justfile.project` (`just lint` = rustfmt + clippy, `just test` =
  `cargo test --workspace`),
- base `rustfmt.toml`, `clippy.toml` and `deny.toml`.

The flake and `justfile.project` are only seeded on the first scaffold, so
running the template after `install.sh` leaves those two as they were.

`nix flake init -t` copies files verbatim (no placeholder substitution), so
rename `example` in four places:

1. `Cargo.toml` -> `[package] name`
2. `src/main.rs` -> `example::greet`
3. `src/lib.rs` -> the doctest's `example::greet`
4. `tests/cli.rs` -> `CARGO_BIN_EXE_example`

Then `cargo generate-lockfile` (or `just sync`), `git add -A`, and
`nix flake check`.
