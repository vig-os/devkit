---
type: issue
state: closed
created: 2026-08-28T08:08:36Z
updated: 2026-08-31T06:32:55Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1573
comments: 2
labels: feature, priority:low, effort:small, semver:minor
assignees: none
milestone: 1.12.0
projects: none
parent: none
children: none
synced: 2026-08-31T07:17:38.004Z
---

# [Issue 1573]: [feat(nix): add poppler-utils to the docs capability module](https://github.com/vig-os/devkit/issues/1573)

## Context

The `docs` capability module (#1178) ships `typst` + `typstyle` for
document-oriented consumers. Working in `exo-pet/vault` surfaced a gap on the
*reading* side: there is no way to get text out of a PDF, because
`poppler-utils` is not on the dev-shell PATH.

Concretely, `pdftotext` and `pdftoppm` are both absent. `pdftoppm` in particular
is what Claude Code's file-reader shells out to in order to render a PDF page,
so **an agent working in a `docs` consumer cannot open a PDF at all** — it fails
with `pdftoppm is not installed`. In a repo whose stated purpose is being "a
primary knowledge source for LLM agents", where a large share of the corpus is
vendor PDFs, that is a sharp edge.

The workaround today is `uv run --with pymupdf`, which works but puts a Python
dependency in the path of something that should be a one-line CLI call, and does
nothing for the agent's built-in reader.

## Proposal

Add `poppler-utils` to `nix/modules/docs.nix`:

```nix
pkgs: _options: {
  packages = with pkgs; [
    typst
    typstyle
    poppler-utils
  ];
}
```

## Why this fits the module rather than `extraPackages`

The `docs` docstring names its consumers — "exo-pet/vault; qms and EXOMA
presentations/grants share the same profile". **All three handle PDFs**, unlike
the v1 exclusions, which were excluded because they serve narrower needs:
pandoc/LaTeX (ask-gated), drawio/excalidraw export (electron-shaped), and Python
doc-processing libs (belong in the consumer's `pyproject.toml` via uv).

`poppler-utils` is none of those: it is a small, generic, native CLI that every
document consumer benefits from, which is exactly the shape `docs` exists to
carry.

## Cost

**139 MB closure.** For comparison, the OCR stack a consumer might otherwise
reach for is an order of magnitude heavier:

| Package | Closure |
|---|---|
| `poppler-utils` | **139 MB** |
| `tesseract` | 1.11 GB |
| `ocrmypdf` | 1.68 GB |

Consumers on `modules = [ "docs" ]` pay the 139 MB; `modules = [ ]` consumers
are unaffected, per the zero-cost-when-unused property in `docs/NIX.md`.

## Explicitly out of scope

**OCR does not belong here.** At 1.68 GB it would make every `docs` consumer pay
for a capability that EXOMA grant decks will never use. `exo-pet/vault#70`
keeps OCR repo-local in a separate pinned dev-shell, and notes that it would
promote to a dedicated `ocr` capability module — alongside `docs` / `node` /
`native` / `rust` — only if a second consumer or a real volume of scanned
documents appears. Flagging so the two are not conflated.

## Tasks

- [ ] Add `poppler-utils` to `nix/modules/docs.nix`
- [ ] Update the `docs` module docstring and the `docs` bullet in `docs/NIX.md`
      (note the PDF-reading rationale, and that OCR stays out)
- [ ] Confirm no closure change for `modules = [ ]` consumers
- [ ] `CHANGELOG.md` — `semver:minor` (additive capability)

---

# [Comment #1]() by [c-vigo]()

_Posted on August 28, 2026 at 08:08 AM_

Origin and companion issue: [exo-pet/vault#70](https://github.com/exo-pet/vault/issues/70) — the vault keeps the OCR stack repo-local in a pinned `devShells.ocr`, and would only promote it to a shared `ocr` capability module if volume justifies it. This issue is the cheap half: PDF *reading* for all `docs` consumers.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 31, 2026 at 06:32 AM_

Merged to `dev` — shipping in 1.12.0.

