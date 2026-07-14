"""Scaffold-lint tests: two structural regressions the scaffold must never reship.

**Rule 1 — unshipped-path references** (#1046, #1056): a file scaffolded into a
consumer repo must not point at a repo path the scaffold does not ship, or every
consumer carries a dead pointer. Two deliberately conservative extractors, one
per shape these bugs took:

* **workflow header comments** — the bare ``docs/<path>.md`` tokens in
  ``assets/workspace/.github/workflows/*.yml`` (e.g. ci.yml's ADR pointer,
  #1056); each must resolve inside the scaffold tree.
* **documentation cross-links** — the relative Markdown link targets in the
  shipped ``assets/workspace/docs/*.md`` set (e.g. DOWNSTREAM_RELEASE.md's
  devkit-internal links, #1056); each must resolve inside the scaffold tree.

Extraction is intentionally narrow — #1057: "few false positives beat exhaustive
coverage." Absolute URLs and pure anchors are exempt; ``docs/...`` mentions in
prose that a consumer legitimately never receives (changelog history, agent
skill files that point at repo-root/devkit-only docs) are out of scope by
construction, not by suppression. ``RULE1_ALLOWLIST`` is the documented escape
hatch for a deliberate exception and is empty by design.

**Rule 2 — non-default-ref checkout + local action** (#1034): a workflow job
that checks out a ref other than the one it was triggered on must not invoke a
local (``uses: ./...``) action. GitHub resolves local actions against the
*checked-out* workspace, so a job that pins a foreign branch may run against a
tree that does not carry the action yet — the sync-main-to-dev bootstrap
deadlock. Every current scaffold + devkit workflow is asserted clean, and the
rule predicate is unit-tested against the pre-#1034 pattern as a constructed
regression fixture.

Refs: #1057
"""

from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path

import pytest
import yaml

# Repository root (tests/ -> repo root) and the consumer scaffold tree.
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"


# --------------------------------------------------------------------------- #
# Rule 1 — unshipped-path references
# --------------------------------------------------------------------------- #

# Deliberate, documented exceptions to Rule 1, keyed by the exact reference
# string. Empty by design: the fix (#1056) resolves the only known instances.
RULE1_ALLOWLIST: dict[str, str] = {}

_ABSOLUTE_URL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
# A bare repo-relative ``docs/....md`` path token, as written in a workflow
# comment. The negative lookbehind keeps it from matching the same substring
# embedded in an absolute URL (``.../blob/main/docs/....md``) or a longer path.
_DOCS_TOKEN = re.compile(r"(?<![\w./-])docs/[A-Za-z0-9_./-]+\.md")
_MD_LINK = re.compile(r"\]\(([^)]+)\)")


def _scaffold_workflows() -> list[Path]:
    base = WORKSPACE / ".github" / "workflows"
    return sorted([*base.glob("*.yml"), *base.glob("*.yaml")])


def _scaffold_docs() -> list[Path]:
    return sorted((WORKSPACE / "docs").glob("*.md"))


def _workflow_comment_violations() -> list[tuple[Path, str]]:
    """``docs/....md`` tokens in scaffold workflows that do not resolve."""
    out: list[tuple[Path, str]] = []
    for wf in _scaffold_workflows():
        for token in _DOCS_TOKEN.findall(wf.read_text(encoding="utf-8")):
            if token in RULE1_ALLOWLIST:
                continue
            if not (WORKSPACE / token).exists():
                out.append((wf, token))
    return out


def _doc_crosslink_violations() -> list[tuple[Path, str]]:
    """Relative Markdown links in shipped docs that do not resolve."""
    out: list[tuple[Path, str]] = []
    for doc in _scaffold_docs():
        for target in _MD_LINK.findall(doc.read_text(encoding="utf-8")):
            target = target.strip()
            base = target.split("#", 1)[0]
            if base == "" or target.startswith(("#", "mailto:")):
                continue
            if _ABSOLUTE_URL.match(target) or target in RULE1_ALLOWLIST:
                continue
            if not (doc.parent / base).exists():
                out.append((doc, target))
    return out


def test_scaffold_has_no_unshipped_path_references() -> None:
    """No scaffolded file points at a repo path the scaffold does not ship."""
    violations = _workflow_comment_violations() + _doc_crosslink_violations()
    assert not violations, (
        "scaffolded files reference paths absent from the scaffold "
        "(rewrite to an absolute https://github.com/vig-os/devkit/... URL, or "
        "add to RULE1_ALLOWLIST with a reason):\n"
        + "\n".join(f"  {p.relative_to(REPO_ROOT)} -> {ref}" for p, ref in violations)
    )


# --------------------------------------------------------------------------- #
# Rule 2 — non-default-ref checkout + local action
# --------------------------------------------------------------------------- #

ALL_WORKFLOWS = [
    p
    for base in (
        REPO_ROOT / ".github" / "workflows",
        WORKSPACE / ".github" / "workflows",
    )
    for p in sorted([*base.glob("*.yml"), *base.glob("*.yaml")])
]


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _on(doc: dict) -> object:
    # YAML 1.1 parses the bare ``on:`` key as the boolean ``True``.
    return doc.get("on", doc.get(True))


def _job_uses_local_action(job: dict) -> bool:
    return any(
        isinstance(s, dict) and str(s.get("uses", "")).startswith("./")
        for s in job.get("steps", []) or []
    )


def _checkout_refs(job: dict) -> list[str | None]:
    refs: list[str | None] = []
    for s in job.get("steps", []) or []:
        if isinstance(s, dict) and "actions/checkout" in str(s.get("uses", "")):
            refs.append((s.get("with") or {}).get("ref"))
    return refs


def _push_branches(on: object) -> set[str] | None:
    """Literal branch filters of a ``push`` trigger, else ``None``.

    ``None`` means the run's ref cannot be pinned statically (dispatch, PR,
    schedule, ``workflow_call``), so a static checkout ref cannot be proven
    foreign and is not flagged.
    """
    if not isinstance(on, dict):
        return None
    push = on.get("push")
    if not isinstance(push, dict):
        return None
    branches = push.get("branches")
    if not isinstance(branches, list):
        return None
    return {str(b) for b in branches}


def job_checks_out_foreign_ref_with_local_action(on: object, job: dict) -> bool:
    """True if a job runs a local action against a ref foreign to its trigger.

    The pre-#1034 shape: a ``push``-triggered job that pins a static branch ref
    other than the pushed branch and then invokes a local ``uses: ./...``
    action. Dynamic ``${{ ... }}`` refs (the run's own ref/SHA) are safe, as is
    the absence of an explicit ref (the triggering SHA).
    """
    if not _job_uses_local_action(job):
        return False
    branches = _push_branches(on)
    if branches is None:
        return False
    for ref in _checkout_refs(job):
        if ref is None or "${{" in ref:
            continue
        if not any(fnmatch(ref, pattern) for pattern in branches):
            return True
    return False


@pytest.mark.parametrize(
    "path", ALL_WORKFLOWS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_no_local_action_on_foreign_ref(path: Path) -> None:
    """No current workflow job runs a local action on a foreign checkout ref."""
    doc = _load(path)
    if not isinstance(doc, dict):
        return
    on = _on(doc)
    jobs = doc.get("jobs") or {}
    offending = [
        name
        for name, job in jobs.items()
        if isinstance(job, dict)
        and job_checks_out_foreign_ref_with_local_action(on, job)
    ]
    assert not offending, (
        f"{path.relative_to(REPO_ROOT)} jobs {offending} check out a ref foreign "
        "to the trigger while invoking a local `uses: ./...` action (#1034): a "
        "local action resolves against the checked-out workspace, which may not "
        "carry it yet. Check out the triggering ref (drop `ref:` or use a "
        "run-scoped `${{ ... }}` expression)."
    )


def test_rule2_predicate_catches_pre_1034_pattern() -> None:
    """Regression fixture: the exact pre-#1034 sync-main-to-dev job shape."""
    on = {"push": {"branches": ["main"]}}
    job = {
        "steps": [
            {"uses": "actions/checkout@v4", "with": {"ref": "dev"}},
            {"uses": "./.github/actions/setup-env"},
        ]
    }
    assert job_checks_out_foreign_ref_with_local_action(on, job) is True


def test_rule2_predicate_allows_triggering_ref_checkout() -> None:
    """The #1034 fix: no explicit ref (triggering SHA) + local action is safe."""
    on = {"push": {"branches": ["main"]}}
    job = {
        "steps": [
            {"uses": "actions/checkout@v4"},
            {"uses": "./.github/actions/setup-env"},
        ]
    }
    assert job_checks_out_foreign_ref_with_local_action(on, job) is False
