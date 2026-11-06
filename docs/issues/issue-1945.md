---
type: issue
state: open
created: 2026-10-27T10:01:17Z
updated: 2026-10-27T10:55:36Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1945
comments: 1
labels: bug
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:12:57.625Z
---

# [Issue 1945]: [#1908 S1d follow-ups: legacy-key advice on fork runs, override over-reporting, warning consistency, summary header test](https://github.com/vig-os/devkit/issues/1945)

Follow-ups from the review of #1944, which shipped the #1908 S1d runner diagnostics (#1926). The review executed the action's bash for every ADR case. All of these are wording or coverage refinements:

1. **Wrong advice on fork runs that carry a legacy key.** The legacy-key warning says "Unset required class: CI_RUNNER_SMALL; set it with gh variable set …", but variables are invisible to fork runs by design, so that advice is wrong there. On foreign runs, the legacy-key warning should say only that the key is ignored for forks, or not fire at all. Settle this against ADR §3; it may need a one-line ADR clarification.
2. **Over-reporting overrides.** With a legacy key, a `CI_RUNNER_LARGE` that is set but unused by the effective lane map is reported as "already overrides the key". Only name classes the lane map requires.
3. **Missing lane names.** The whitespace-only warning doesn't name the affected lanes; the opt-in warning does. Make them consistent.
4. **Untested header.** No test pins the step-summary table header row. Add one, so that removing it fails a test (it passes today).

Refs #1926

---

# [Comment #1]() by [gerchowl]()

_Posted on October 27, 2026 at 10:55 AM_

Test hygiene items from the review of #1947 (S2), to handle with the other runner test follow-ups here:
- In `tests/test_ci_runner.py` `test_release_train_jobs_route_via_runner_json`, `expected` is reset after the assert inside the loop. It works, but it reads like a bug.
- These names are stale since S1/S2: `test_release_callers_pass_runner_json`, the docstring 'take an optional runner-json', and the comment 'Hosted-only by design: codeql / scorecard / devkit-upgrade'. devkit-upgrade now runs on SMALL per decision (e)-1.

