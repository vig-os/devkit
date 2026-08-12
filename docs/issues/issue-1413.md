---
type: issue
state: closed
created: 2026-08-11T07:55:46Z
updated: 2026-08-11T08:45:21Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1413
comments: 1
labels: refactor, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:08.140Z
---

# [Issue 1413]: [[REFACTOR] Prune and simplify the test suite: remove cannot-fail and duplicate tests, consolidate accreted clusters](https://github.com/vig-os/devkit/issues/1413)


## Description

**Situation.** The test suite (~30,500 lines across `tests/`, `tests/bats/`, and `packages/vig-utils/tests/`) has grown by accretion: incident-driven tests were added next to existing ones without pruning what they superseded, features were tested again at each new layer, and structural grep-tests survived after behavioral e2e siblings made them obsolete. The incident-pinned e2e tests themselves are in excellent shape and are not touched here. The dead weight falls into four classes:

1. **Tests that cannot fail** — inline re-implementations of the logic under test asserted instead of the real code (some have silently drifted from the implementation, so they would stay green through a real regression); `pytest.skip` in the failure branch; disjunction asserts with a trivially-true arm (`… or result.returncode == 0`); whole-file substring asserts any comment satisfies; asserts guarded by conditions that make absence a silent pass; constants compared to their own literals; two tests that pass only via cross-test mutation of a session-scoped workspace while asserting a behavior the product does not have.
2. **Duplicate coverage** — the same case tested at up to four layers (unit → print-only handler → argv-patched `main()` → subprocess); exact-duplicate scenarios under different names; structural greps fully shadowed by a behavioral sibling; presence-only checks subsumed by version/behavior checks; the same property asserted in 2–3 files, each paying a full scaffold-subprocess run.
3. **Copy-paste accretion** — clusters of near-identical tests differing only in data; 14 private copies of the same YAML loader; ~30 inlined `devcontainer exec` argv blocks; ~32 manual `sys.argv` save/restore blocks; duplicate fixture definitions with divergent semantics.
4. **Wiring gaps** — test files no CI job runs, a broken `just` recipe, two hardcoded action-pin SHAs that legitimate Renovate bumps will break, one malformed assertion pattern, and stale test docs.

Net: **~4,500–5,500 lines and ~250–300 test functions removable or foldable with zero loss of distinct failure-mode coverage** — coverage improves where cannot-fail tests become real ones and silent skips become failures. Runtime drops materially: ~30 fewer full `init-workspace.sh` scaffold runs, ~80 fewer `nix`/bash subprocess launches.

**Proposed solution** — five work packages, each landing as separately reviewable commits (deletions apart from consolidations), suite green after each.

### WP1 — wiring & correctness

- [ ] `justfile` `test-validate-commit-msg` recipe targets `tests/test_validate_commit_msg.py`, which no longer exists (tests live in vig-utils). Drop the recipe (`test-vig-utils` covers it) or repoint.
- [ ] `tests/test_flake_hooks.py` (759 ln, the hooks↔committed-YAML fidelity gate; its own docstring claims CI enforcement) and `tests/test_flake_services.py` run in **no CI job** — deny-listed from the `test-project` sweep with no targeted step existing. Add a targeted Project Checks step (nix is warm there; fixtures are module-scoped).
- [ ] `tests/test_flake_devshell.py`: CI runs 3 of ~16 tests via `-k`; the devTools parity anchor `test_each_tool_runs_in_devshell` never runs in CI. Widen the selection to the cheap fixture-driven tests and document which stay local-only.
- [ ] `.github/actions/test-project/action.yml:97` "Run utility tests" step is dead (`suite == 'utils'` is never passed by any workflow) — delete or note manual-dispatch use. Also reconcile the deny-list comment with `test_flake_version_guard.py` actually running 4 `nix develop`s inside the coverage sweep.
- [ ] Fix the malformed pattern in `test_workflow_private_repo_guard.py:155–157`: `…result }}}} = {tolerated}` unescapes without the closing quote, so the negative assertion matches nothing and cannot fail. While there, revisit the `"cancelled"` leg (contradicts the #1371 summary-gate doctrine).
- [ ] De-hardcode full action-pin SHAs: `test_workflow_sync_autoresolve.py:34` (`COMMIT_ACTION_PIN`) and `test_workflow_private_repo_guard.py:85–88` + its `# v5.0.0` comment assert — replace with the name + 40-hex-SHA shape check (pattern already in `test_workflow_client_id_credentials.py:62–75`); today every Renovate bump of these actions reds the tests.
- [ ] `test_shell_entrypoints.py:77` creates/removes `.claude/skills/bad:canary` inside the real working tree (parallel-unsafe, dirties the repo on crash); rejection already proven by the tmp_path tests. Delete.
- [ ] Regenerate `TESTING.md` (documents a 4-file layout incl. a deleted file) and rewrite `tests/README.md` (references `make build`/`make test`, a nonexistent `tests/test_registry.py`, and compose-based mechanics the tests don't use). Fix the stale `test_flake_checks.py` module docstring (claims nixfmt; asserts treefmt) and the `tests/conftest.py:33` scientific-extras comment.

### WP2 — tests that cannot fail (delete or rewrite as real tests)

`tests/test_utils.py` (doc-gen half — ~11 of 24 tests):
- [ ] The changelog-version/date tests (L84–258) re-implement the parsing inline and never call `docs/generate.py` — and the replicas have drifted (the real function requires a `\d{4}-\d{2}-\d{2}` match the replica lacks). Rewrite the ~5 distinct cases through the real functions via the existing `_point_generate_to_temp_changelog` pattern (L29).
- [ ] `test_returns_dev_when_no_versions` / `test_returns_first_version` (L119–143): monkeypatch the function under test to a local replica. Rewrite.
- [ ] `test_generate_docs_succeeds` (L264): builds its own jinja env; the three monkeypatches are dead code. Delete (real path covered by `test_generate_docs_actual`).
- [ ] `test_generate_docs_skips_missing_template` (L308): body byte-identical to `test_generate_docs_actual`; the skip branch is never exercised. Delete or actually patch the template list.
- [ ] `TestIncludeNarrative` (L317–377): asserts on a local copy of a closure inside `generate_docs`. Delete or test through rendered output.

`tests/test_integration.py`:
- [ ] `TestVersionCheckInitWorkspace` (L3338–3358): asserts `init-workspace.sh` creates `.devcontainer/.local/` and `version-check.conf` — it creates neither; the tests pass only because earlier tests mutated the session workspace. Delete (or rewrite against a virgin scaffold if the claim should become real).
- [ ] `TestHostGitSignatureSetup` (L24–217): 5 of 6 tests skip on exactly the failure they exist to catch, and one accepts any value via `pass`/`pass` branches; it tests the host machine, not the product. Demote to a diagnostic `just` recipe or delete.
- [ ] `TestPodmanSocketAccess` (L2430–2632): pull/run/build skip on failure then assert a disjunction ending `or returncode == 0`; version/info skip on failure. Keep the socket/env tests plus ONE hard-assert DooD build test; delete the rest.
- [ ] `test_ssh_github_authentication` (L1554): asserts only for rc 255/1; any other rc passes silently. Add `else: pytest.fail`.
- [ ] ~25 `"workspace may be from older template"` skip guards (L3009–3707): the workspace is always freshly scaffolded, so the only reachable trigger is a template regression — which then skips instead of failing. Convert to asserts (the correct pattern exists at L2673–2676).
- [ ] `test_local_directory_gitignored` (L3002): both failure modes skip. Replace skips with asserts.
- [ ] `TestVersionComparison` (L3029): whole body under `if compose_file.exists():`, and weaker than the exact-string check in `TestDevContainerDockerCompose`. Delete.
- [ ] Vacuous-loop pair `test_post_attach_uses_silent_mode` / `test_post_attach_graceful_failure` (L3427/3454): if no line matches, zero assertions run. Assert a match (merge with the presence test at L3376).
- [ ] Whole-file substring family: `test_just_check_command_exists`/`test_just_update_command_exists` (L3047/3060 — `"check" in content`), the notification-message trio (L3518–3543 — `"rebuild" in content.lower()` etc.), `test_devcontainer_upgrade_detects_container_environment`/`_checks_runtime_available`/`_calls_install_script` (L3590–3668 — trivially-satisfied or vacuously-guarded). Anchor to recipe/function bodies or fold into the WP4 rewrite.
- [ ] Weak asserts `test_check_when_disabled` (L2954 — empty output passes) and `test_check_when_muted` (L2981 — asserts only rc==0). Pin one behavior each.

`tests/bats/`:
- [ ] `init-workspace.bats:154–197` `prune_mode` cluster: the helper performs the `rm` inside the test and asserts the files are gone — it tests `rm`, not the script (e2e versions exist at L252–356). Delete tests + helper.
- [ ] `install.bats:441` (`grep 'info'` — matched by the `info()` helper) and `:417` (`grep 'pull'` — guaranteed by the `--skip-pull` help text). Delete.
- [ ] `worktree.bats:77–96`: builds a repo and runs the `git worktree list | grep` pattern itself; never invokes `just worktree-start`, so the recipe's guard could be deleted without failing it. Delete or rewrite to invoke the recipe.

Workflow tests — dead clauses (keep the tests):
- [ ] `test_release_core_sync_dispatch.py:55`: forever-true `"TIMEOUT=120" not in run`; make the positive assert a floor.
- [ ] `test_floating_tags.py:110` (pins a bash comment) and `:133` (40-char prose tombstone that will never be retyped): drop clauses; the behavioral negatives (`-X PATCH`, `-f ref=`) carry the tests.
- [ ] `test_workflow_model.py:205–231`: exact comment-prose pins ("a no-op on a main PR", "its base IS main", …) break on any rewording; keep the behavioral negative (`"Pull requests to dev" not in`), drop the prose.
- [ ] `test_workflow_prepare_extension.py:179`: the `pr_name != ext_name` half is structure-guaranteed (a `uses:` job has no steps text). Drop that half. Also scope the `sync_manifest.py` negative (L336) to `run:` blocks — it currently passes by a one-character accident of a comment.
- [ ] `test_workflow_client_id_credentials.py:78–81`: stale `COMMIT_APP_ID` tombstone subsumed by the with-block assert. Fold in.

`packages/vig-utils/tests/`:
- [ ] `test_prepare_changelog.py:326–338` `TestStandardSections` (constant vs own literal) and `:1643` (asserts output printed unconditionally). Delete.
- [ ] `test_check_action_pins.py:596`: docstring claims "only first captured" but asserts `len(errors) >= 1` — true either way. Assert `== 1` + names, or delete. `:469` verbose test: second disjunct arm is guaranteed by `exit_code == 0`; assert `"OK"` alone.
- [ ] `test_validate_commit_msg.py:1101` `test_rejects_claude_as_whole_word`: the message matches the `Co-authored-by` pattern first, so `\bclaude\b` is never reached — and is untested anywhere. **Replace** with a claude-only message (closes a real gap).
- [ ] `test_validate_commit_msg.py:836`: docstring claims a linked-ref scenario; the message is byte-identical to `test_invalid_refs_without_issue` (L149). Delete.
- [ ] `test_utils.py:80` (vig-utils): docstring says slash delimiter; body admits it uses pipe. Delete or write a real `s/a/b/` case.
- [ ] `test_retry.py:100` idempotency test: `retry_command` is stateless; nothing exists for idempotency to break. Delete.

### WP3 — duplicate coverage (each deletion names its surviving twin)

`tests/test_integration.py` / `test_image.py` / `conftest.py`:
- [ ] Version-check duplicates: `test_no_network_silent_failure` (≡ L2986), `test_just_check_enable_disable` (≡ L2787+2804), `test_just_check_mute_functionality` (L2821 is stronger), `test_just_check_calls_script` + `test_just_check_config_shows_configuration` (≡ L2907; neither invokes `just` despite their names — the `just` path is covered by L3199), `test_script_exists_and_executable` (≡ the fixture asserts). Deduplicate the 3× `version_check_script` / 2× `local_dir` fixtures into one assert-style module fixture.
- [ ] `TestDockerComposeProjectOverrides` (L2161–2313): readable+content test subsumes dir-exists/file-exists/ls. 4 → 1.
- [ ] `test_just_help` (L2019): assertion block is a verbatim copy of `test_just_default`'s; parametrize over `[[], ["help"]]`.
- [ ] Move the ~160-line home-copy tail (L1277–1438) out of the nano-fallback test into `test_files_copied_to_home`, and decide the if-present optionality once (it also duplicates the warn-only checks at L1085–1155).
- [ ] Presence tests subsumed by parse/behavior siblings: `test_devcontainer_json_exists`, `test_docker_compose_yml_exists`, `test_vig_os_exists`, `test_githooks_directory_exists`; negative-assert halves of `test_org_name_replaced`/`test_short_name_replaced` (whole-tree scan at L792 already covers absence).
- [ ] `test_image.py`: drop the 5 `_installed` halves of installed/version pairs (git/curl/gh/just/taplo), `test_vig_utils_installed` (L673, weaker than `_version`), `test_path_resolves_required_tools` (L850, subsumed by the run-tests; param id mislabels typstyle), and optionally `test_nix_conf_exists` (every sibling fails on absence).
- [ ] Delete dead `tests/conftest.py::get_compose_project_name` and `tests/docker-compose.test.yml` (zero call sites; conftest uses direct podman).

`tests/bats/` (surviving behavioral sibling verified for each):
- [ ] `init-workspace.bats`: 7 "X is in PRESERVE_FILES" greps (#640, #913, #1099 ×3, #1054, #1092) — each shadowed by its "upgrade preserves a customized X" sibling; `--mode` greps L199/204/216 (**keep L209**, sole coverage of the flag-less default); smoke greps L869 + L933; VIG_OS_VERSION greps L1086–1095 (shadowed by the env-override e2e at L1161); "sources parse-github-remote-lib" L1072 (lib abort surfaces through e2e at L2135); the positive half of the diff-preview grep L1711 (keep the refute-`diff`/`cmp` half — distinct pin).
- [ ] `install.bats`: 7 git-setup greps (L311–357; pytest twins in `test_install_script.py` — the file's own comment concedes it) + 2 trunk-gating greps (L368–377); `detect_runtime` trio (L189–202, proven by the stub-based fallback e2e); `SKIP_PULL` grep (L422, any stubbed `--skip-pull` run fails on an unknown flag); 4 output-helper greps; strict-mode/executable/shebang triplets repeated across 5 bats files — keep at most one per script.
- [ ] `init.bats`: log-helper pair (L193/198); the two `conftest.py` greps (L205/210 — bats grepping a pytest support file).
- [ ] `init-precommit.bats:13–21`: both greps shadowed by the arbitrary-mount e2e at L23.
- [ ] install.sh dry-run unit coverage exists twice (bats `install.bats:30–185` ↔ pytest `TestInstallScriptUnit`): consolidate into **one** harness — bats is the richer home; delete the pytest twins and relocate the two container-independent dry-run tests from `test_install_script.py` (L156–199) plus `TestHostScriptShebangPortability` (needs no image per its own docstring) into that single home.
- [ ] `test_install_script.py`: presence tests subsumed by content siblings (`…creates_devcontainer_directory`, `…creates_conf_directory`, `…creates_git_repository`); parametrize the 3 byte-identical placeholder rglob loops.

Workflow tests:
- [ ] Trunk sync-main-to-dev absence asserted 3× across `test_workflow_model.py:129/:135` and `test_workflow_sync_checkout.py:96`, each paying a scaffold run — keep sync_checkout's. Same for trunk prepare-release-base (model + prepare_extension) and trunk sync-issues default (model + sync_settings): keep one home each.
- [ ] Delete the 3 bare `is_file()` tests (`test_workflow_release_extension.py:66`, `prepare_extension.py:123`, `devkit_upgrade.py:96`) — every sibling `_load()` of the same file fails loudly on absence. Delete the in-file duplicate `exists()` clause in `test_scaffold_downstream_release_doc.py:47`, and fold that file's two lint-subsumed tests into `test_scaffold_lint` coverage, moving the unique SSoT-sync test to `test_transforms.py`.
- [ ] Collapse near-zero-plausibility tombstone clusters: the dead-inputs pair in `release_publish_lightweight_tag.py:91–109` → one test; `DEVKIT_UPGRADE_TOKEN` negative in `devkit_upgrade.py:136` (keep the `Refs:`/`Closes` negatives — reintroduction is plausible).

`packages/vig-utils/tests/`:
- [ ] `test_prepare_changelog.py`: one CLI layer instead of three — keep 1–2 subprocess smokes per subcommand (proves console-script wiring) + `TestCmdValidate` (the only handler with logic); delete the print-only `cmd_*` tests and the argv-patched `TestMainCLI` duplicates (~350 ln). Fold the 3 standalone invalid-semver tests into the existing param list (L773) and parametrize the finalize pair; delete `test_idempotent_when_already_finalized` (L1379 — the finalized-pattern is date-agnostic, L1398 is strictly stronger), `test_minimal_changelog` (≡ L561), `test_unreleased_with_only_headers` (≡ L576), `test_header_content` + `test_empty_old_sections` (assert unconditionally-appended literals, ≡ `test_basic_structure`), the 3 create-vs-prepare re-proofs, the multiline/nested 4→2, and the unused `changelog_with_tbd` / constant-alias fixtures.
- [ ] `test_validate_commit_msg.py`: delete exact dups `test_valid_linked_pr_url` (≡ L829), `test_require_scope_false_by_default` (≡ L410), `test_chore_minimal_subject_only` (≡ L178), `test_valid_body_multiple_lines_before_refs` (≡ L77), `test_perf_is_an_approved_type` (inside the all-types loop), `test_custom_types_single_type` (+ 1 more same-branch case); combined types+optional class 4 → 1 (no combined branch exists); main-layer 24 → ~8 (keep the split/strip/flag-wiring/exit-code tests that pin `main()`'s own logic; the 5 identified dupes of unit tests go); scopes cluster 19 → ~6 param tests; linked-refs 14 → ~5 (the regex treats URLs as opaque); invalid-refs trio → 1 parametrized.
- [ ] `test_check_action_pins.py`: delete `test_sha_as_string_not_number` (≡ L583), `test_valid_sha_all_lowercase` (≡ L21), `nested_steps`/`indentation_variations` (same branch as existing pins), the 2 main-layer duplicates (L530/555; merge `test_main_multiple_unpinned` into the found-test with 2 files — cross-file aggregation is main's own loop); tag/branch pair → parametrize; regex classes 12 → 2 parametrized (keep the 39/41-char/uppercase/non-hex boundary inputs — sole coverage).
- [ ] vig-utils `test_utils.py`: delete `TestRunPackagedShell` (mock tower; arg-forwarding/rc/stdin proven for real in `test_shell_entrypoints.py`), the argv-layer duplicates of the subprocess class, sed passthroughs (L53/62 merge, L100, one of the two FileNotFound tests), the triple-layer no-command test (keep parse_args-level).
- [ ] Small ones: `test_gh_issues.py` L508 subset-dup + 3 param clusters (prefix/type/closing-keyword, ~13 tests → 3); `test_validate_commit_range.py:162` (subsumed by the well-formed parametrize); `test_check_expirations.py:22` raw-regex test (subsumed by `TestParseEntries`); `test_shell_entrypoints.py` `shutil.which` pair (a missing entry point already raises); single-entry parametrize in `test_renovate_changelog_pr.py:233`.

### WP4 — consolidation (simple tests, same cases)

- [ ] **Rewrite `clean.bats`**: 41 tests, all structural greps transcribing the 77-line `scripts/clean.sh` line-by-line (incl. 2 exact-duplicate pairs), zero behavioral execution — a broken script passes while any cosmetic refactor fails. Replace with ~5–8 behavioral tests using a logging `podman` stub on PATH (pattern exists at `install.bats:1009–1028`): version default/strip, manifest→arch→main removal sequence, removal-failure warning, post-clean verification.
- [ ] **Collapse the version-check sprawl** in `test_integration.py` (8 classes, L2660–3783, ~45 tests): one class for script behavior + one for scaffold-content assertions; the grep-swarm classes collapse to one grouped test each (they read byte-identical `assets/` sources and need no workspace). ~1,120 → ~400 ln after WP2/WP3 removals.
- [ ] **`dc_exec()` conftest helper** for the ~30 inlined `devcontainer exec` argv blocks (−300–400 ln); extract the 4× copy-pasted pexpect stage-timeout report in `conftest.py` (also fixes the wrong "copying_files" hint on later stages).
- [ ] **Shared workflow-test helpers** in `tests/workflow_scaffold.py`: `load_workflow()`/`on_block()`/`steps_of_job()`/`step_by_id`, SHA-pin regex helpers, and the `_run_resolve`+`GITHUB_OUTPUT` parser currently duplicated verbatim in `test_ci_runner.py` and `test_scaffold_drift.py` — replaces 14 private `_load` copies and the cross-test-module import in `sync_autoresolve`. Then merge: the release-core pair into one file; the two lightweight-tag files parametrized over the two publish surfaces; `floating_tags`+`promote_mergeability` into a promote file; the 7-file "`.vig-os` declares key X" + 4-file "resolve-toolchain declares output X" triads into one parametrized manifest test. Net: ~31 files → ~21.
- [ ] Shared nix helpers: `_nix_env` (6 copies) and the `builtins.getFlake` expr preamble (~9 copies) into `tests/conftest.py`; session-scoped `current_system` (8+ launches → 1); one-eval-many-asserts for the ci-full config and homeManagerModules groups in `test_flake_checks.py`; template-exposure pair → parametrize; the fixture-bypass duplicate eval in `test_flake_hooks.py:672`.
- [ ] Table-drive bats copy-paste families in `init-workspace.bats`: `.vig-os` knob round-trips (~20 tests → 3 loops), preserve/diff-hint trios (~14 → 2 loops), #885 per-mode groups; `githooks.bats` 3-hooks×4-states → loop (12 → 4; the loop idiom exists in-suite); `worktree-claude-cli.bats` main/template pairs → loop (9 → 5); `just.bats` dispatch-ref quartet → table; `install.bats` distro greps → loop. Tighten the loose-but-load-bearing `devc-upgrade` greps in `just.bats:77–87` to the parser line.
- [ ] vig-utils: replace the ~32 `sys.argv` save/restore blocks with `monkeypatch`/a helper (`test_vulnix_gate.py`'s `_run` is the in-repo model); parametrize `test_ci_runner.py`'s two clusters (5+3 near-identical bodies).

### WP5 — runtime (optional; follow-up-friendly)

- [ ] Session-scoped cached `gitflow_tree`/`trunk_tree` in `tests/workflow_scaffold.py` for all read-only assertions (~30 of ~55 scaffold call-sites collapse to 2 runs; per-test scaffolds stay for mutating cases).
- [ ] `setup_file`-scoped scaffolds for the per-mode bats assertion groups (~20 → 4 runs).
- [ ] `test_flake_devshell.py`: one `nix develop` entry looping all devTools instead of one per tool (~30 launches → 1, identical failure attribution); merge the python3/console-script probes; fix the stale `_and_precommit` test name.
- [ ] `test_setup_toolchain_env.py`: one module-scoped run of the step script for the 31 byte-identical default invocations (params stay as assertions).
- [ ] `test_flake_hooks.py`: build the three consumer-config fixtures in one derivation set.

## Files / Modules in Scope

- `tests/*.py`, `tests/conftest.py`, `tests/workflow_scaffold.py`, `tests/docker-compose.test.yml`, `tests/README.md`
- `tests/bats/*.bats`, `tests/bats/test_helper.bash`
- `packages/vig-utils/tests/*.py`
- `justfile` (test recipes), `.github/workflows/ci.yml` + `.github/actions/test-project/action.yml` (test wiring only)
- `TESTING.md` via `docs/templates/TESTING.md.j2`

## Out of Scope

- Structural grep-tests that are the **only** coverage of their behavior stay: `just.bats` workflow-YAML pins (L106–308; incl. the ~15 smoke-test `repository-dispatch.yml` tests with no pytest twin), `init.bats` bootstrap-wiring greps (L121–162), `worktree-claude-cli.bats` recipe greps (declared static-only, functional rewrite tracked in #630), `setup-gh-repo.bats` greps. Splitting `just.bats`'s multi-clause grep chains / relocating them to a `workflows.bats` is a separate issue.
- New coverage for gaps surfaced here — `load_skills`/`group_skills` in `docs/generate.py`; locale/nvim/actionlint image tests; token ceilings of the scaffold core/publish jobs; a behavioral `devc-upgrade` test; `worktree.bats`' near-zero CI coverage (tmux tests skip under `CI=true`) — separate issues.
- No production code changes (scripts, workflows, nix modules, templates) beyond the WP1 test wiring.

## Invariants / Constraints

- Every distinct failure mode keeps at least one test; deletions are limited to tests that cannot fail, exact duplicates, and cases subsumed by a named surviving test.
- Suite green (`just test`, `just test-bats`, CI) after each work package; deletions land in commits separate from consolidations and rewrites.
- Deletions that would orphan a behavior get a replacement first (the `\bclaude\b` whole-word case; the hard-assert DooD build test; the `clean.bats` behavioral rewrite precedes removal of its greps).
- Intentional overlaps stay: `test_validate_commit_range.py`'s integration re-pins, the drift/refs-policy bats↔pytest splits, `test_downstream_flake.py` as the documented local-parity twin of the direct CI step, SHA boundary inputs in the regex tests.

## Acceptance Criteria

- [ ] WP1 landed: recipe fixed, flake hooks/services/devshell CI wiring decided and implemented, malformed pattern fixed, SHA pins shape-checked, docs regenerated.
- [ ] WP2: no test in the suite skips on its own failure mode, asserts a trivially-true disjunction, asserts on a re-implementation of the code under test, or depends on cross-test mutation.
- [ ] WP3: every listed duplicate removed or merged, with the surviving test named in the commit.
- [ ] WP4: `clean.bats` behavioral; version-check feature in ≤2 classes; shared helpers in place; workflow-shape tests consolidated (~31 → ~21 files).
- [ ] Net reduction ≥ ~4,000 lines / ~250 test functions; all lanes green.

## Changelog Category

No changelog needed

## Additional Context

The suite's incident-pinned e2e tests are the model to preserve: `test_setup_toolchain_env.py`, `test_sync_settings.py`'s hostile-input guards, `wait-for-rekor.bats`' simulated clock, `manifest-parsers.bats`' byte-identity checks, `init-workspace.bats`' sentinel-fixture upgrade tests, `test_validate_commit_range.py`'s live-git topology fixture, and the extracted-grep-pattern technique in `test_release_tombstone_detection.py`. The well-factored files to converge on for workflow shape tests: `test_workflow_client_id_credentials.py` (parametrized over both copies, version-floor pin regex) and `test_workflow_sync_autoresolve.py`'s cross-copy byte-identity test.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 11, 2026 at 08:45 AM_

Implemented in PR #1415 (merged to dev @3630542a): WP1–WP4 complete — CI wiring fixed (hooks/services/dev-shell contracts now run in Project Checks), all cannot-fail tests deleted or rewritten as real tests, duplicates removed with named survivors, clean.bats rewritten behaviorally, version-check collapsed to two classes, workflow-shape tests consolidated onto shared helpers. Net −4,584 lines / ~300 test functions; all suites green locally and in PR CI. WP5 (runtime fixtures) deferred as marked optional; follow-up #1414 filed for the scaffold summary-gate cancelled-leg parity gap.

