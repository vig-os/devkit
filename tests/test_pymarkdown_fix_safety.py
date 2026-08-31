"""The scaffolded ``.pymarkdown`` must be safe to run in *fix* mode (#1574).

The generated hook runs ``pymarkdown -c .pymarkdown fix`` (#1170) with
modify-and-fail semantics, so on "files were modified by this hook" the natural
operator move is re-add and re-commit. That makes an unsafe fixer a *silent*
corrupter: whatever it rewrote lands in history as an unreviewed "lint fix".

Field use in exo-pet/exo-fleet (exo-pet/exo-fleet#229, #427) found three such
hazards on ordinary documentation — fenced code blocks indented inside ordered
list items — each reduced to a synthetic reproducer below and verified against
both the devkit pin (0.9.23) and upstream 0.9.39, then filed upstream as
jackdewinter/pymarkdown#1672 / #1673 / #1674. None of the three is fixed
upstream, so **a pin bump is not the remedy**: these tests are the gate that
re-runs the reproducers against whatever version the flake pins, and they fail
the bump if the rules are re-enabled or upstream regresses.

The remedy the config carries is disabling the three rules whose *fixers* are
unsafe (md029, md031, md046). Their reproducers are inlined here rather than
committed as fixture ``.md`` files on purpose: the repo's own ``pymarkdown``
hook lints every tracked markdown file, so a committed reproducer would feed
the crash straight back into the hook that is meant to be gated.

Refs: #1574
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = REPO_ROOT / ".pymarkdown"

pytestmark = pytest.mark.skipif(
    shutil.which("pymarkdown") is None,
    reason="pymarkdown is not on PATH; the fix-mode hook shells out to it",
)

# Bug 1 (upstream #1672) — a numbered list continuing across a heading (the
# runbook "phase" idiom) plus an unspaced fence: MD029 and MD031 both claim the
# same token and the whole fix run dies with BadPluginFixError, which the hook
# comment's "tolerates unfixable violations" contract says cannot happen.
CRASH_ON_LIST_RESUMING_AFTER_HEADING = """\
# Repro

## Phase A

1. Step one.
2. Step two.

## Phase B

3. Step three:
   ```sh
   echo three
   ```
4. Step four.
"""

# Bug 2 (upstream #1673) — two consecutive list items each carrying an indented
# fence: the first is fixed correctly and the SECOND is dumped to column 0, its
# body and closing fence left at the old indent, the continuation paragraph
# pulled out of the list. Exits "success", so it survives an inattentive
# re-commit. This is the one md029/md046 alone do not stop — MD031 is the
# corrupter.
CORRUPTS_SECOND_IN_LIST_FENCE = """\
# Repro

1. First step:
   ```sh
   echo one
   ```
2. Second step:
   ```sh
   echo two
   ```
   Trailing note.
3. Third step.
"""

# Bug 3 (upstream #1674) — the documented escape hatch does not reach fix mode:
# the pragma suppresses the scan finding, and fix renumbers the list anyway.
# Deliberate continuation numbering ("as in step 9 above") is a semantic claim,
# and there is no per-site opt-out for it.
PRAGMA_IGNORED_BY_FIX = """\
# Repro

<!-- pyml disable-next-line ol-prefix -->
9. Step nine.
10. Step ten.
"""

UNSAFE_FIXERS = ("md029", "md031", "md046")


def _fix(tmp_path: Path, document: str) -> subprocess.CompletedProcess[str]:
    """Run the hook's exact command over ``document`` in a scratch copy.

    Same ``-c .pymarkdown fix`` invocation the generated hook uses, against the
    repo's own config — the file ``sync-manifest`` seeds into every consumer as
    ``assets/workspace/.pymarkdown``.
    """
    target = tmp_path / "repro.md"
    target.write_text(document, encoding="utf-8")
    proc = subprocess.run(
        ["pymarkdown", "-c", str(CONFIG), "fix", str(target)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    proc.stdout = target.read_text(encoding="utf-8")  # the fixed document
    return proc


@pytest.mark.parametrize(
    "document",
    [
        CRASH_ON_LIST_RESUMING_AFTER_HEADING,
        CORRUPTS_SECOND_IN_LIST_FENCE,
        PRAGMA_IGNORED_BY_FIX,
    ],
    ids=["crash-md029xmd031", "corrupt-md031", "pragma-ignored-md029"],
)
def test_fix_leaves_the_reproducers_untouched(tmp_path: Path, document: str) -> None:
    """``fix`` must exit 0 and rewrite nothing on all three reproducers (#1574).

    ``pymarkdown fix`` exits 0 only when it changed nothing; 3 means "Fixed"
    and 1 means it failed outright. Asserting both the exit code and the byte
    content catches every observed failure shape: the BadPluginFixError crash,
    the de-indent corruption that reports success, and the pragma-defying
    renumber.
    """
    proc = _fix(tmp_path, document)

    assert proc.returncode == 0, (
        "pymarkdown fix must leave ordinary in-list fenced code alone; got "
        f"rc={proc.returncode} stderr={proc.stderr.strip()[:400]!r}"
    )
    assert proc.stdout == document, (
        "pymarkdown fix rewrote the document — a semantics-changing edit the "
        "hook's modify-and-fail loop would land as an unreviewed lint fix:\n"
        f"{proc.stdout}"
    )


def test_config_disables_the_unsafe_fixers() -> None:
    """The three unsafe fixers are disabled in the config itself (#1574).

    The behavioural tests above are the real gate, but they need ``pymarkdown``
    on PATH. This one pins the scaffold's *intent* in every lane: md029
    (renumbers ordered lists), md031 (de-indents in-list fences) and md046
    (deletes fence markers, dropping language tags) must ship disabled because
    the hook runs ``fix``. A scan-only consumer can re-enable them.
    """
    plugins = json.loads(CONFIG.read_text(encoding="utf-8"))["plugins"]

    for rule in UNSAFE_FIXERS:
        assert plugins.get(rule, {}).get("enabled") is False, (
            f"{rule}'s fixer is unsafe in fix mode (#1574); .pymarkdown must "
            f"ship it disabled, got: {plugins.get(rule)!r}"
        )
