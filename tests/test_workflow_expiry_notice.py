"""Workflow-shape tests: the nightly scan warns before an exception expires.

``check-expirations`` runs in all PR CI, in pre-commit, in both nightly
``security-scan`` lanes and in the release train, so a single lapsed block reds
every open branch and the release path at once, with no prior signal — three
times in two months (#1260, #1481, #1547).

``security-scan.yml`` therefore carries a third, NON-failing issue class: a
seven-day advance notice, one deduplicated issue per (matrix ref x distinct
upcoming expiry date). It is a notice, never a gate.

These are pure YAML-shape assertions (no ``nix``/``gh`` needed).

Refs: #1552
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

SECURITY_SCAN_WF = REPO_ROOT / ".github" / "workflows" / "security-scan.yml"

SCAN_JOB = "scan-nix-image"

# The blocking step the notice must precede.
VALIDATION_RUN = "uv run check-expirations .vulnixignore"


def _steps() -> list[dict]:
    workflow = yaml.safe_load(SECURITY_SCAN_WF.read_text(encoding="utf-8"))
    return workflow["jobs"][SCAN_JOB]["steps"]


def _index_of(predicate) -> int:
    for index, step in enumerate(_steps()):
        if predicate(step):
            return index
    raise AssertionError("no matching step found in security-scan.yml")


def _notice_index() -> int:
    """Index of the advance-notice step (matched on what it runs)."""
    return _index_of(lambda step: "--warn-days" in step.get("run", ""))


def _notice_step() -> dict:
    return _steps()[_notice_index()]


def test_the_notice_runs_before_the_blocking_validation_step() -> None:
    """Placement is load-bearing, not cosmetic.

    The validation step fails the job on an already-expired entry, ending the
    run. A notice scheduled after it would therefore go silent exactly on the
    runs where the *next* wave of expiries most needs surfacing.
    """
    validation_index = _index_of(
        lambda step: step.get("run", "").strip() == VALIDATION_RUN
    )

    assert _notice_index() < validation_index, (
        "the advance-notice step must run BEFORE the blocking validation step, "
        "or an already-red register suppresses the notice entirely (#1552)"
    )


def test_the_notice_never_fails_the_job() -> None:
    """The hard gate stays the validation step; the notice is best-effort.

    A classification hiccup or an issue the API refuses to create must never
    turn a green nightly scan red.
    """
    assert _notice_step().get("continue-on-error") is True, (
        "the advance-notice step must be continue-on-error: a missed notice is "
        "not a security regression, but a red scan hides real ones (#1552)"
    )


def test_the_notice_covers_all_three_exception_registers() -> None:
    """The nightly gate reads ``.vulnixignore``, but all three red every branch.

    #1260 was a ``.trivyignore`` lapse; the dependency-review allow-list shares
    the same format and the same blast radius.
    """
    script = _notice_step()["run"]

    for register in (
        ".vulnixignore",
        ".trivyignore",
        ".github/dependency-review-allow.txt",
    ):
        assert register in script, (
            f"{register} lapses red every branch too and must be covered (#1552)"
        )


def test_the_notice_window_is_one_expiry_grid_period() -> None:
    """Seven days: dates land on a Wednesday, so the notice does too.

    One full Renovate cycle ahead of the red — see the expiry grid in
    ``docs/CONTAINER_SECURITY.md``.
    """
    step = _notice_step()

    assert step.get("env", {}).get("WARN_DAYS") == "7", (
        "the warning window must be 7 days — one expiry-grid period (#1552)"
    )
    assert "--warn-days" in step["run"], "the window must be passed to the utility"


def test_the_notice_never_reparses_the_expiration_grammar() -> None:
    """``check-expirations --json`` stays the single parser of the register.

    A second implementation of the ``Expiration:`` grammar inside a workflow is
    exactly the drift this flag exists to prevent.
    """
    script = _notice_step()["run"]

    assert "--json" in script, (
        "the step must consume the utility's JSON classification rather than "
        "re-reading the register itself (#1552)"
    )
    # Comments are free to *mention* the grammar; executable lines are not.
    code = "\n".join(
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    )
    assert "Expiration:" not in code, (
        "the workflow must not parse the `Expiration:` grammar itself — "
        "check-expirations is its single parser (#1552)"
    )


def test_the_notice_dedups_per_ref_and_per_expiry_date() -> None:
    """One issue per (ref x date): a date maps 1:1 to one combined review pass.

    The ref keeps the two matrix lanes from colliding (#1237); the date keeps a
    staggered register from collapsing back into a single rolling issue.
    """
    script = _notice_step()["run"]

    assert "gh issue list --state open --label security-scan" in script, (
        "dedup must reuse the existing open-issue lookup (#965, #1237, #1548)"
    )
    assert "${SCAN_REF}" in script and "${EXPIRY}" in script, (
        "the issue title must carry both the ref and the expiry date so each "
        "(ref x date) dedups independently (#1552)"
    )
    assert "--label security-scan --label security" in script, (
        "the notice must carry the same labels as the other scan issues"
    )


def test_the_notice_body_forbids_a_blind_date_bump() -> None:
    """The notice lands BEFORE the week's findings delta exists.

    That is deliberate — but it is also exactly when a blind date bump is
    tempting, which is the failure mode the Wednesday grid exists to prevent.
    The body must say so and point at the register's own standard.
    """
    script = _notice_step()["run"]

    assert "re-verification, not a date bump" in script, (
        "the body must state that a renewal is a re-verification (#1552)"
    )
    assert "delta" in script, (
        "the body must send the reader to the latest findings delta first"
    )
    assert "Delete" in script or "delete" in script, (
        "the body must say to delete what the pin advance cleared, not extend it"
    )
    assert "docs/CONTAINER_SECURITY.md" in script, (
        "the body must link the expiry-grid documentation (#1552)"
    )
