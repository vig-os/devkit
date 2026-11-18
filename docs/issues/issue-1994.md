---
type: issue
state: closed
created: 2026-11-03T09:22:18Z
updated: 2026-11-04T03:48:28Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1994
comments: 3
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:33.384Z
---

# [Issue 1994]: [docs: opinionated Typst house style: template package, layout guards, reproducible build (design)](https://github.com/vig-os/devkit/issues/1994)

## Goal

Give document-oriented consumers an opinionated, opt-in Typst setup. It has three parts: a house style that makes good layout the default, guards that reject bad layout and usage, and a reproducible build. Today the `docs` module only puts the binaries on PATH (#1993 moves them to unstable). Every consumer rebuilds templates, recipes and CI on its own, and nothing checks typstyle formatting or figure and table rules.

Everything here is opt-in and turns on with `modules = [ "docs" ]` or a sibling `docs-guards` knob. Nothing changes for non-document consumers.

## Design (proposal: review before building)

### 1. House-style package (good layout by default)

A neutral, unbranded Typst package that the `docs` module ships. It is exposed through `TYPST_PACKAGE_PATH` as `@local/devkit-docs:<ver>` and versioned with devkit. Branding comes in through parameters: colours, logo and labels.

- **Page and text:** a `#show: document.with(meta)` show rule. It must be a show rule, not a plain function call, so its `set` rules actually apply. It sets page, margins, a type scale, heading numbering, and a running header and footer with a commit stamp from `--input rev=`.
- **Tables, booktabs style:** a show rule on `table`. It draws rules above and below the table and under the header, and no vertical rules. The header row is bold and repeats on each page, and number columns align. Plain `#table(...)` gets this automatically.
- **Figures:** captions at a fixed size and width; table captions go above, other captions below. A `fig(...)` helper refuses to draw without a caption.
- **Diagrams:** fletcher (and cetz) pinned and vendored into the package path, so documents import a known version and nothing is fetched from the network at build time.
- **Plots:** a native-plot helper on lilaq or cetz-plot that takes its text sizes from the document's type scale and refuses to draw without axis labels. For matplotlib or other external figures, ship a style file whose font sizes match the scale, so text is readable when the figure is placed at column width.
- **Components:** callouts (note, warning), a revision history table, a title page, and a 16:9 slides layout.
- **Fonts:** bundled through `TYPST_FONT_PATHS`, and builds run with `--ignore-system-fonts`, so output never depends on the host's fonts.

### 2. Guards: opt-in prek hooks plus a CI job

| Guard | Mechanism | Fails on |
|---|---|---|
| format | `typstyle --check`, plus a `typstyle.toml` (line width) | unformatted `.typ` |
| compile | `typst compile --root . --ignore-system-fonts` on every entry document, with warnings as errors; templates compile to /dev/null | broken docs, missing imports, warnings |
| figure captions | `typst query <doc> "figure"` → JSON | any figure without a caption |
| table headers | `typst query` on `table` / `table.header` | tables without a header row |
| house-style bypass | a source scan of entry documents | direct `#set text(font: ...)` or `#set page(...)` outside the package |
| package pinning | an import scan | unpinned or non-vendored `@preview` imports |
| figure font size | parse SVG figures (smallest `font-size` × the placed scale) | text below the readability threshold. Raster charts can't be checked, so the guard requires SVG or native plots for charts. |
| built output | path check | committed `generated/*.pdf` |

Axis labels are enforced through the plot helper, which refuses to draw without them, because labels inside an arbitrary image can't be checked reliably.

### 3. Reproducible build: just recipes plus a CI pattern

- **`just typst`:** compile all entry documents to a sibling `generated/`. It runs with `--root .`, `--ignore-system-fonts`, a fixed `SOURCE_DATE_EPOCH`, `TZ=UTC` and a `rev` stamp, plus optional `--deps` output. The skip list is configurable.
- **`just typst-canonical`:** a build without the stamp, so outputs can be compared by hash.
- **`just typst-probe`:** prints the toolchain identity as JSON.
- **CI:** compiling is the required check. It uses the `--deps` data to pick which documents a PR affects and uploads the PDFs as an artifact. PR previews pushed to a throwaway ref are optional, and are a later phase.

### 4. Written rules

A `typst` skill or doc in the scaffold that explains the conventions above, so people and agents write documents the same way.

## Phasing

1. Guards that need no package: format, compile, generated-PDF, package pinning. Plus the recipes and fonts.
2. The house-style package: page, tables, figures, callouts, slides, and vendored fletcher/cetz.
3. Content guards: captions, headers, bypass and SVG font size. Plus the plot helper and the matplotlib style.
4. CI preview pipeline (optional).

## Out of scope

Controlled-document machinery: document registers, reviewer rosters, issuance and releases, provenance locks. It stays consumer-owned until a second consumer needs it.

## Open questions for the owner

- Fonts: which families? This is a licensing question too.
- Default paper size (A4?) and margins.
- Plot backend: lilaq vs cetz-plot.
- The figure font-size threshold: for example, at least 7 pt at final placed size.
- Is the slides layout in scope for phase 2?

---

# [Comment #1]() by [gerchowl]()

_Posted on November 3, 2026 at 09:22 AM_

## Addendum: a terminology register (glossary and part definitions) with a consistency check

**Problem:** across a document set, the same part, component or concept gets several names, and authors (agents especially) invent new names for things that already have one. Nothing catches this.

### Source of truth: one machine-readable register per repo
- Use `glossary.yaml` (or TOML). Typst reads YAML, TOML and JSON natively (`yaml()`), and people edit it easily. JSONL suits append-only logs better than a list someone curates.
- Each entry has:
  - `id`, the stable key;
  - `term`, the canonical spelling;
  - `definition`;
  - `kind` (term, part, component, acronym, role);
  - `aliases`, accepted variants;
  - `forbidden`, deprecated or wrong names, each with the replacement;
  - an optional `part-number` or pattern;
  - an optional `status` (active or deprecated).
- A JSON schema validates the file. The schema check is the first guard.

### Using it in documents (house-style package)
- `#term("id")` renders the canonical term. On first use it can also expand an acronym and link to the glossary entry.
- `#glossary()` renders the appendix from the register, listing only the terms the document actually uses. Build it on the glossarium package or something equivalent.
- An unknown id is a compile error, so a mistyped key fails at once.

### Checks
1. **Deterministic hook (the prek and CI gate):**
   - `#term()` ids must exist. The compile catches this, and so does a `typst query` on term metadata.
   - Each `forbidden` variant is rejected wherever it appears in source text, and the error names the replacement.
   - A part-number pattern that matches no registered part is rejected.
   - The same register can generate rules for Vale's substitution-style checks or for typos' allow-list, so Markdown docs get the same check.
2. **Agent check, for new or invented names:**
   - A script extracts candidate names from a document: capitalised noun phrases, identifiers, part-number-like tokens, and new acronyms.
   - It subtracts everything the register knows, including aliases.
   - An agent, or a reviewer, is asked about each leftover: is it a synonym of an existing entry (then use the canonical term), or a genuinely new thing (then add it to the register in the same PR)?
   - The script makes this cheap and repeatable. It gates as a "new terms must be registered" check, and its PR comment lists the unregistered names.
3. **Drift report:** terms that are registered but never used, and terms whose definitions disagree between documents.

### Phasing
This fits phase 3 (content guards). The register file, the schema and the forbidden-variant hook could ship earlier, because they don't need the Typst package.


---

# [Comment #2]() by [gerchowl]()

_Posted on November 3, 2026 at 09:56 AM_

Owner decisions (2026-11-03):
- **Fonts:** Typst's built-in fonts only (Libertinus Serif, New Computer Modern, DejaVu Sans Mono), with builds run under `--ignore-system-fonts`. Nothing bundled. A font-path hook stays available for branding.
- **Plot library:** lilaq.
- **Smallest figure text:** 7 pt at final placed size.
- **Defaults, no objection raised:** A4 paper, 2.5 cm margins, slides layout in scope (phase 2).
- **Glossary:** in scope (see the addendum above).

---

# [Comment #3]() by [gerchowl]()

_Posted on November 4, 2026 at 03:48 AM_

Delivered on dev for the next minor:
- **Phase 1 guards and recipes:** #2005, plus follow-ups #2012.
- **Glossary register and guards:** #2013 and #2014.
- **House-style package `@local/devkit-docs`:** core in #2015 (0.1.x); plots, glossary helpers and slides in #2017 (0.2.0).
- **Content guards and runtime bypass detection:** #2019 (0.2.1).
- **Typst toolchain on unstable:** #1995.

Open follow-ups: #2016 (devkit-docs module clash edges) and #2022 (content-guard edges).

