---
type: issue
state: open
created: 2026-10-14T15:14:50Z
updated: 2026-10-14T15:14:50Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1885
comments: 0
labels: feature, discussion, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-15T07:15:47.481Z
---

# [Issue 1885]: [[SPIKE] GUI archetype: Tauri v2 + Rust/wasm-WebGPU views vs GPUI — plus contract-first FE tests that let an agent drive a port](https://github.com/vig-os/devkit/issues/1885)

## Motivation

Several projects need a GUI, and each picks its stack ad hoc. Agents re-roll the choice every time. We need:
1. **One dated, definitive answer** for the "GUI app" archetype in the org stack matrix (#1523).
2. **First-class frontend tests** so a **port** (TS prototype → Rust, or one shell → another) is guarded well enough that an agent can drive it alone, iterating until green.

The first step is a measured comparison of GPUI against Tauri + Rust/wgpu views (a graph view with 1k–100k nodes: frame time, input latency, memory, IME, a11y). devkit should take the generic outcome and ship it as an opt-in pack.

## Decision / proposed approach (current best guess, to be refuted)

**The GUI modes considered:**

| mode | what | strengths | weaknesses |
|---|---|---|---|
| A | **GPUI / GPUI Kit** (native Rust, GPU) | fastest, native feel, AccessKit | no webview embedding; canvas-only wasm (weak IME/find/a11y on web); pre-1.0 churn; agents write it poorly |
| B | **Tauri v2 + web (TS/React)** | agents write it fluently; web ecosystem; same code in the browser | DOM limits on very large views |
| C | **Tauri v2 + Rust compiled to wasm drawing with WebGPU in a `<canvas>`**, embedded in B | Rust hot views that compose with the DOM and run unchanged in the browser | wasm/WebGPU overhead compared with native |
| D | **Tauri v2 + a native wgpu surface layered with the webview** | native speed for one view | focus, input and z-order compositing problems |
| E | pure-Rust retained/immediate GUIs (iced, Floem, egui) | simple, all Rust | small ecosystem; no web apps inside |

**Recommendation (pending the measured comparison): B + C as the default, with D only where a measured gap justifies it.** In short, "Rust where possible, the webview for apps and prototypes".
- Logic lives in Rust crates or the daemon.
- Hot views are Rust/wgpu → wasm canvas.
- Third-party and agent-written apps are sandboxed iframes.
- A is at most an optional native client on the same protocol.

## The port guard: contract-first frontend tests (the key deliverable)

A view or app is defined by its **contract**, not its implementation:
- **manifest:** capabilities and resource kinds;
- **bridge protocol:** typed messages in and out;
- **data schema.**

Any implementation (TS prototype, Rust/wasm, native) must pass the same suite.

1. **Contract fixtures:** recorded bridge message sequences (input → expected outputs/state).
   - Run headless against every implementation.
   - For Rust: `wasm-bindgen-test` in a headless browser, plus a native harness.
2. **DOM/a11y snapshots:** Playwright `ariaSnapshot()`/role queries for DOM implementations.
   - Canvas implementations must expose an equivalent a11y tree (AccessKit or a hidden-DOM mirror), checked by the same role queries.
3. **Visual tests from the wireframes:**
   - the existing wireframes / `.dc.html` artboards are the reference;
   - Playwright screenshot diffs with a tolerance per region;
   - plus a structural check (regions present, layout order).
4. **Interaction scripts:** Playwright flows (pan, zoom, select, type with IME, find, copy) shared across implementations. Tauri runs them through `tauri-driver` (WebDriver) or the dev webview in Chrome.
5. **Perf budgets as tests:** frame-time p99 and input→pixel latency, with thresholds per view, so a port cannot regress silently.
6. **One agent loop:** `just fe-test <view> --impl <ts|wasm|native>` gives a machine-readable report (failing fixture, diff image path, a11y delta). That lets an agent port a view iteratively: red → fix → green, with no human in the loop until review.

## Scope

**P0**
- [ ] Add the "GUI app" row to the stack matrix (#1523), dated, with the recommended mode and the conditions for each alternative.
- [ ] A contract-test harness: fixture format + runners for TS (Playwright) and Rust/wasm (wasm-bindgen-test headless), plus a JSON report.
- [ ] `just fe-test` recipe.

**P1**
- [ ] An opt-in `gui` pack (per #1519: not shipped to every Rust consumer):
  - a Tauri v2 scaffold, a Rust/wgpu wasm-canvas view template, and the iframe app-bridge template;
  - CI jobs for headless WebGPU (or a WebGL2 fallback, logged).
- [ ] A wireframe → visual-baseline importer (`.dc.html` / HTML artboards → Playwright baselines).
- [ ] An a11y parity check for canvas views (AccessKit / hidden-DOM mirror).

**P2**
- [ ] Perf-budget tests in CI on a GPU-capable runner (sage tart / vm-runner with a GPU?).
- [ ] An example port, end to end: a TS prototype view → Rust/wgpu, done by an agent against the harness, with the iteration count and tokens recorded.

## Traceability (fixture/report format)

Keep the harness generic and file-based, but give fixtures and reports:
- **stable IDs**;
- **requirement references** in the fixture metadata;
- **content hashes**.

With these, a graph-based project store can link requirement → wireframe → contract → fixtures → implementations. A port then swaps only implementation code, while the tests and requirements stay attached and can't be lost.

## Pitfalls

- **Headless WebGPU in CI:** availability differs by runner, OS and browser. A silent fallback to software rendering makes perf numbers meaningless, so log the adapter and fail perf jobs on software adapters.
- **Flaky visual tests:** font hinting, GPU and DPI differences. Pin fonts and the device scale factor, use a tolerance per region, and keep baselines per platform.
- **Wireframes are not specs:** wireframe diffs should check structure plus a loose visual match; pixel-exact only for components, never whole pages.
- **The canvas a11y gap:** a Rust canvas view passing visual tests but invisible to screen readers is a failed port. Make a11y parity a hard gate.
- **Contract drift:** fixtures must be versioned with the manifest. A changed contract is a semver event, not a test update.
- **Over-shipping:** keep it all in an opt-in pack (#1519).
- **Tauri WebDriver gaps on macOS** (WKWebView support via tauri-driver has been limited). Verify the current state at the pinned version. Fall back to running the frontend in Chrome for interaction tests and a smoke test in the real shell.

## Acceptance criteria

- [ ] A stack-matrix row merged, citing the benchmark numbers.
- [ ] One view has a fixture suite passing on two implementations (TS + Rust/wasm).
- [ ] An agent completes an example port using only `just fe-test` feedback.
- [ ] The opt-in pack is documented in `docs/`, with a scaffold smoke test in CI.

## References

- #1523 org stack matrix, #1519 smallest denominator
- https://gpui-kit.com/, https://v2.tauri.app/, Playwright aria snapshots, wasm-bindgen-test

