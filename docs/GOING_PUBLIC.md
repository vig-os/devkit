# Going public

Complete this checklist before changing a private repository's visibility.
A clean current tree does not prove its history or existing clones are clean.

1. **Scan all history and refs**, first with default secret rules, then with
   the owner's self-contained private site rules. Keep patterns outside git;
   use an absolute `DEVKIT_LEAK_PATTERNS` path for these commands:

   ```bash
   gitleaks git --redact --log-opts="--all" .
   gitleaks git --redact --log-opts="--all" --config "$DEVKIT_LEAK_PATTERNS" .
   ```

   Review findings locally; do not paste private patterns or matched values
   into issues, PRs or public logs. The second scan is essential for site names,
   hosts and labels that default secret rules do not recognize.
2. **Scan the current tree** for hard-coded endpoints and site patterns:

   ```bash
   git ls-files -z | xargs -0 check-hardcoded-endpoints
   site-leak-check --all-files
   ```

   Project code must read endpoints and credentials from the environment and
   data locations from the active site file. See [endpoint lint](MIGRATION.md#env-only-endpoint-lint)
   and [the leak-check hook](MIGRATION.md#site-leak-check-hook). `site-leak-check`
   uses `DEVKIT_LEAK_PATTERNS`, else `.site/leak-patterns.toml`; absent patterns
   mean silent success, not evidence that a site-specific scan ran. Patterns
   must be untracked and outside the worktree or inside ignored `.site/`.
   `--all-files` scans nonignored working-tree files, not history.
3. **Confirm local bindings were never committed**:

   ```bash
   git log --all -- .site .aws
   ```

   The output must be empty. Keep `.site/` and `.aws/` ignored and credentials
   in the environment or the tool's credential store. See
   [per-clone bindings](SOLO_ADOPTION.md#per-clone-site-bindings).
4. **Review every workflow.** Adopt the managed runner selection shipped in
   release N or later; check repo-owned workflows for literal self-hosted labels
   and missing fork predicates. Confirm no `workflow_run` or `merge_group` trigger
   bypasses the documented design. Check `pull_request_target` workflows for
   execution of untrusted code with base credentials. See
   [runner selection and fork security](WORKFLOW_SECURITY.md#runner-selection-and-fork-security).
5. **Configure the actual self-hosted security controls.** The runner operator
   must set a job-start hook (for example `ACTIONS_RUNNER_HOOK_JOB_STARTED`)
   that reads the event payload and rejects PR jobs whose `head.repo` differs
   from `base.repo`. Set the org's **"Require approval for fork pull request
   workflows"** to **all external contributors**. Runner-group visibility
   restricted to private repositories is an optional extra layer. A fork controls
   its workflow and resolve action on `pull_request`; devkit's predicate prevents
   accidental routing and is not a security boundary.
6. **Review labels visible in public job logs.** Requested labels must reveal
   nothing private. Configure runner variables outside git; use generic labels
   such as `pool-s`. See [runner migration](MIGRATION.md#run-ci-on-self-hosted-runners).
7. **If anything is found, rotate credentials first.** Then remove exposed site
   details, rewrite affected history as needed, and repeat both history and tree
   scans. A rewrite cannot retract existing clones or cached copies.
