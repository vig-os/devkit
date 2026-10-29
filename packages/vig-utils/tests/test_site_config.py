"""Site configuration and initializer contract tests (ADR §8–§9)."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GIT = shutil.which("git")


@pytest.fixture(autouse=True)
def git_repository(tmp_path):
    subprocess.run([GIT, "init", "-q", str(tmp_path)], check=True)


def cli(root, command, *args):
    result = subprocess.run(
        [sys.executable, "-m", "vig_utils.site_config", command, *args],
        cwd=root,
        env=dict(
            os.environ,
            PATH=os.environ.get("PATH", "") + os.pathsep + str(Path(GIT).parent),
        ),
        input="",
        capture_output=True,
        text=True,
        check=False,
    )
    assert "No module named" not in result.stderr, result.stderr
    return result


def config(root, name="fixture", extra=""):
    path = root / ".site" / f"{name}.toml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(f'schema = 1\nsite = "{name}"\n' + extra)
    return path


@pytest.mark.parametrize("location", ["", "/srv/data", "s3://bucket/data"])
def test_valid_bindings(tmp_path, location):
    config(tmp_path, extra=f'[datasets.raw]\nlocation = "{location}"\n')
    result = cli(tmp_path, "check-site-config")
    assert result.returncode == 0, result.stderr
    assert ("unbound" in result.stderr) == (location == "")
    if not location:
        assert "raw" in result.stderr


@pytest.mark.parametrize(
    "extra",
    [
        '[datasets.raw]\nlocation = "relative/data"\n',
        '[datasets.raw]\nlocation = "s3://user:pw@bucket/data"\n',
        '[hints]\nACCESS_KEY = "hidden"\n',
        "[hints]\nrunner = 1\n",
        "[datasets.raw]\nlocation = 2\n",
    ],
)
def test_invalid_bindings(tmp_path, extra):
    config(tmp_path, extra=extra)
    result = cli(tmp_path, "check-site-config")
    assert result.returncode != 0
    if "user:pw@" in extra:
        assert "datasets.raw.location" in result.stderr
        assert "user:pw@" not in result.stderr


@pytest.mark.parametrize(
    "text",
    [
        'schema = 2\nsite = "fixture"',
        'schema = true\nsite = "fixture"',
        'schema = 1\nsite = "other"',
    ],
)
def test_schema(tmp_path, text):
    config(tmp_path).write_text(text)
    assert cli(tmp_path, "check-site-config").returncode != 0


def test_lookup(tmp_path, monkeypatch):
    monkeypatch.delenv("DEVKIT_SITE", raising=False)
    assert cli(tmp_path, "check-site-config", "--print-path").stdout == ""
    first = config(tmp_path)
    (first.parent / "leak-patterns.toml").write_text("")
    assert cli(tmp_path, "check-site-config", "--print-path").stdout.strip() == str(
        first
    )
    config(tmp_path, "second")
    result = cli(tmp_path, "check-site-config")
    assert result.returncode != 0
    assert "fixture" in result.stderr and "second" in result.stderr
    monkeypatch.setenv("DEVKIT_SITE", "fixture")
    assert cli(tmp_path, "check-site-config").returncode == 0
    monkeypatch.setenv("DEVKIT_SITE", "missing")
    assert cli(tmp_path, "check-site-config").returncode != 0


def initializer(tmp_path, monkeypatch, name="fixture", body=None):
    bindir = tmp_path.parent / (tmp_path.name + "-bin")
    bindir.mkdir(exist_ok=True)
    script = bindir / f"devkit-site-init-{name}"
    script.write_text(
        "#!/bin/sh\n"
        + (
            body
            or (
                'test "$PWD" = "$(dirname "$DEVKIT_SITE_DIR" | xargs dirname)" || exit 8\n'
                'test "$DEVKIT_DATA_MANIFEST" = "$PWD/data.toml" || exit 9\n'
                'printf \'schema = 1\\nsite = "%s"\\n\' "$DEVKIT_SITE" > "$DEVKIT_SITE_DIR/$DEVKIT_SITE.toml"\n'
            )
        )
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    (tmp_path / "data.toml").write_text("[datasets.raw]\n")


def test_discovery_force_and_ambiguity(tmp_path, monkeypatch):
    initializer(tmp_path, monkeypatch)
    assert cli(tmp_path, "site-init").returncode == 0
    path = tmp_path / ".site/fixture.toml"
    before = path.read_bytes()
    assert cli(tmp_path, "site-init").returncode != 0
    assert path.read_bytes() == before
    assert cli(tmp_path, "site-init", "--force").returncode == 0
    initializer(tmp_path, monkeypatch, "second")
    result = cli(tmp_path, "site-init")
    assert result.returncode != 0
    assert "fixture" in result.stderr and "second" in result.stderr
    assert cli(tmp_path, "site-init", "second").returncode == 0


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ('touch "$DEVKIT_SITE_DIR/partial"\nexit 7\n', 7),
        ('echo "schema = 2" > "$DEVKIT_SITE_DIR/$DEVKIT_SITE.toml"\n', 1),
    ],
)
def test_failed_initializer_cleans_up(tmp_path, monkeypatch, body, code):
    initializer(tmp_path, monkeypatch, body=body)
    result = cli(tmp_path, "site-init")
    assert result.returncode == code, result.stderr
    assert not (tmp_path / ".site").exists()


def test_non_tty_fallback_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    (tmp_path / "data.toml").write_text("[datasets.raw]\n[datasets.processed]\n")
    result = cli(tmp_path, "site-init")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(tmp_path / ".site/local.toml")
    result = cli(tmp_path, "check-site-config")
    assert result.returncode == 0
    assert all(name in result.stderr for name in ("unbound", "raw", "processed"))


def test_scaffold_integration(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(
        (ROOT / "assets/workspace/.gitignore").read_text()
    )
    for directory in (".site", ".aws"):
        result = subprocess.run(
            ["git", "check-ignore", directory + "/fixture"],
            cwd=tmp_path,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0
    recipe = (ROOT / "assets/workspace/justfile").read_text()
    assert "site-init" in recipe
    scripts = (ROOT / "packages/vig-utils/pyproject.toml").read_text()
    assert 'check-site-config = "vig_utils.site_config:main"' in scripts
    assert 'site-init = "vig_utils.site_config:site_init"' in scripts


@pytest.mark.parametrize(
    "location",
    [
        "localhost:9000/x",
        "foo:bar",
        "s3:",
        "s3://",
        "https://",
        "file:",
    ],
)
def test_unknown_or_empty_uri_forms(tmp_path, location):
    config(tmp_path, extra=f'[datasets.raw]\nlocation = "{location}"\n')
    result = cli(tmp_path, "check-site-config")
    assert result.returncode == 1, result.stderr


@pytest.mark.parametrize(
    "location",
    [
        "gs://bucket/data",
        "az://container/data",
        "abfs://container/data",
        "http://example.com/data",
        "https://example.com/data",
        "file:///srv/data",
    ],
)
def test_supported_uri_forms(tmp_path, location):
    config(tmp_path, extra=f'[datasets.raw]\nlocation = "{location}"\n')
    assert cli(tmp_path, "check-site-config").returncode == 0


def test_realistic_leak_patterns(tmp_path, monkeypatch):
    initializer(
        tmp_path,
        monkeypatch,
        body=(
            'printf \'schema = 1\\nsite = "fixture"\\n\' > "$DEVKIT_SITE_DIR/fixture.toml"\n'
            "cat > \"$DEVKIT_SITE_DIR/leak-patterns.toml\" <<'TOML'\n"
            "[[rules]]\nid = \"userinfo\"\nregex = 's3://[^/]*@'\nsecretGroup = 1\n"
            "[[rules]]\nid = \"fixture-pattern\"\nregex = '(fixture)'\nsecretGroup = 1\n"
            "[allowlist]\npaths = ['tests/']\nTOML\n"
        ),
    )
    result = cli(tmp_path, "site-init")
    assert result.returncode == 0, result.stderr
    assert "secretGroup = 1" in (tmp_path / ".site/leak-patterns.toml").read_text()


@pytest.mark.parametrize(
    "patterns",
    [
        'rules = "bad"',
        '[[rules]]\nid = "missing-regex"',
        '[[rules]]\nid = 1\nregex = "x"',
        '[[rules]]\nid = "x"\nregex = 1',
    ],
)
def test_invalid_leak_pattern_shape(tmp_path, monkeypatch, patterns):
    initializer(
        tmp_path,
        monkeypatch,
        body=(
            'printf \'schema = 1\\nsite = "fixture"\\n\' > "$DEVKIT_SITE_DIR/fixture.toml"\n'
            "cat > \"$DEVKIT_SITE_DIR/leak-patterns.toml\" <<'TOML'\n"
            + patterns
            + "\nTOML\n"
        ),
    )
    result = cli(tmp_path, "site-init")
    assert result.returncode == 1, result.stderr
    assert "leak-patterns.toml" in result.stderr
    assert not (tmp_path / ".site").exists()


@pytest.mark.parametrize(
    "entry",
    ["", ".", "bin", "absolute-root", "absolute-bin", "symlink-dir", "symlink-binary"],
)
def test_repo_cannot_supply_initializer(tmp_path, monkeypatch, entry):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = tmp_path / "devkit-site-init-evil"
    script.write_text("#!/bin/sh\nprintf ran > marker\nexit 17\n")
    script.chmod(0o755)
    (bindir / script.name).symlink_to(script)
    if entry == "absolute-root":
        entry = str(tmp_path)
    elif entry == "absolute-bin":
        entry = str(bindir)
    elif entry.startswith("symlink-"):
        external = tmp_path.parent / (tmp_path.name + "-external")
        if entry == "symlink-dir":
            external.symlink_to(bindir, target_is_directory=True)
        else:
            external.mkdir()
            (external / script.name).symlink_to(script)
        entry = str(external)
    monkeypatch.setenv("PATH", entry)
    result = cli(tmp_path, "site-init")
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "marker").exists()
    assert (tmp_path / ".site/local.toml").exists()


def test_detect_unstaged_output(tmp_path, monkeypatch):
    initializer(
        tmp_path,
        monkeypatch,
        body=(
            'printf \'schema = 1\\nsite = "fixture"\\n\' > "$DEVKIT_SITE_DIR/fixture.toml"\n'
            "printf 'schema = 1\\nsite = \"sneaky\"\\n' > .site/sneaky.toml\n"
        ),
    )
    result = cli(tmp_path, "site-init")
    assert result.returncode == 1, result.stderr
    assert "sneaky.toml" in result.stderr
    assert not (tmp_path / ".site/fixture.toml").exists()
    assert not list((tmp_path / ".site").glob(".staging-*"))


def test_keep_existing_site_directory_on_failure(tmp_path, monkeypatch):
    (tmp_path / ".site").mkdir()
    initializer(tmp_path, monkeypatch, body="exit 7\n")
    assert cli(tmp_path, "site-init").returncode == 7
    assert (tmp_path / ".site").is_dir()


def test_module_without_arguments(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "vig_utils.site_config"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "usage:" in result.stderr
    assert "Traceback" not in result.stderr


def test_default_recipe_is_help(tmp_path):
    import shutil

    just = shutil.which("just")
    assert just is not None, "just must be available in the development environment"
    (tmp_path / "justfile").write_text((ROOT / "assets/workspace/justfile").read_text())
    result = subprocess.run(
        [just, "--dry-run"], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr.strip() == "just --list"


@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize(
    "entry", ["absolute", "relative", "parent-relative", "symlink"]
)
def test_subdirectory_cannot_supply_initializer(tmp_path, monkeypatch, depth, entry):
    sub = tmp_path / "sub"
    if depth == 2:
        sub /= "nested"
    sub.mkdir(parents=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    binary = bindir / "devkit-site-init-evil"
    binary.write_text("#!/bin/sh\nprintf ran > marker\nexit 17\n")
    binary.chmod(0o755)
    if entry == "absolute":
        value = str(bindir)
    elif entry == "symlink":
        link = tmp_path.parent / (tmp_path.name + "-link")
        link.symlink_to(bindir, target_is_directory=True)
        value = str(link)
    else:
        value = os.path.relpath(bindir, sub)
        if entry == "relative":
            value = "./" + value
    monkeypatch.setenv("PATH", value)
    result = cli(sub, "site-init")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(tmp_path / ".site/local.toml")
    assert not list(tmp_path.rglob("marker"))
    assert not (sub / ".site").exists()
    result = cli(sub, "check-site-config", "--print-path")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(tmp_path / ".site/local.toml")


@pytest.mark.parametrize("command", ["site-init", "check-site-config"])
def test_outside_git_refused(tmp_path_factory, command):
    outside = tmp_path_factory.mktemp("outside")
    result = cli(outside, command)
    assert result.returncode == 2
    assert "git work tree" in result.stderr
    assert not (outside / ".site").exists()


def test_linked_worktree_uses_own_site(tmp_path, monkeypatch):
    subprocess.run(
        [
            GIT,
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.com",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    linked = tmp_path.parent / (tmp_path.name + "-linked")
    subprocess.run(
        [GIT, "-C", str(tmp_path), "worktree", "add", "--detach", str(linked)],
        check=True,
        capture_output=True,
    )
    sub = linked / "sub"
    sub.mkdir()
    monkeypatch.setenv("PATH", str(Path(GIT).parent))
    result = cli(sub, "site-init")
    assert result.returncode == 0, result.stderr
    assert (linked / ".site/local.toml").exists()
    assert not (tmp_path / ".site").exists()
    assert not (sub / ".site").exists()


@pytest.mark.parametrize(
    "location",
    [
        "https://exa\nmple.example/x",
        "https://example.com/x\n",
        "s3://b\tucket",
        "s3://bucket ",
        "/srv/x\nrm -rf",
        "/srv/with space",
        "/srv/x\x00",
        "/srv/x\x7f",
        "/srv/x\x85",
        "/srv/x\u2028",
        "/srv/x\u2029",
        "https://example.com/x\r",
        " https://example.com/x",
        "file://example.com/srv/x",
        "file:///srv/../x",
        "file:///srv/%2e%2e/x",
        "s3://..",
        "s3://ab",
        "s3://Bucket",
        "s3://bucket..name",
        "s3://192.0.2.1",
        "s3://bucket_name",
        "s3://xn--bucket",
        "s3://bucket-s3alias",
        "s3://bucket--x-s3",
        "s3://" + "a" * 64,
    ],
)
@pytest.mark.parametrize("field", ["dataset", "output"])
def test_location_grammar_is_strict_and_redacted(tmp_path, location, field):
    table = "datasets.raw" if field == "dataset" else "output"
    config(tmp_path, extra=f"[{table}]\nlocation = {json.dumps(location)}\n")
    result = cli(tmp_path, "check-site-config")
    assert result.returncode == 1, result.stderr
    assert f"{table}.location" in result.stderr
    assert location not in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("depth", [2, 3])
def test_recursive_writes_detected(tmp_path, monkeypatch, depth):
    directory = tmp_path / ".site"
    nested = directory.joinpath(*["level"] * depth)
    nested.mkdir(parents=True)
    initializer(
        tmp_path,
        monkeypatch,
        body=(
            'printf \'schema = 1\\nsite = "fixture"\\n\' > "$DEVKIT_SITE_DIR/fixture.toml"\n'
            f"printf unexpected > .site/{'/'.join(['level'] * depth)}/evil.toml\n"
        ),
    )
    result = cli(tmp_path, "site-init")
    assert result.returncode == 1, result.stderr
    assert "evil.toml" in result.stderr
    assert not (directory / "fixture.toml").exists()
    assert not list(directory.glob(".staging-*"))


@pytest.mark.parametrize("kind", ["symlink", "fifo"])
@pytest.mark.parametrize("command", ["site-init", "check-site-config"])
def test_special_entries_refused_recursively(tmp_path, kind, command):
    nested = tmp_path / ".site/a/b"
    nested.mkdir(parents=True)
    entry = nested / "forbidden"
    if kind == "symlink":
        entry.symlink_to(tmp_path)
    else:
        os.mkfifo(entry)
    result = cli(tmp_path, command)
    assert result.returncode == 1, result.stderr
    assert "a/b/forbidden" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("name", ["leak-patterns", "LEAK-PATTERNS"])
@pytest.mark.parametrize(
    "entry", ["argument", "discovered", "env", "output", "fallback"]
)
def test_reserved_site_names(tmp_path, monkeypatch, name, entry):
    if entry in ("argument", "discovered"):
        initializer(tmp_path, monkeypatch, name=name)
        result = cli(tmp_path, "site-init", *([name] if entry == "argument" else []))
    elif entry == "env":
        config(tmp_path, name)
        monkeypatch.setenv("DEVKIT_SITE", name)
        result = cli(tmp_path, "check-site-config")
    elif entry == "output":
        initializer(
            tmp_path,
            monkeypatch,
            body=(
                f'printf \'schema = 1\\nsite = "{name}"\\n\' > "$DEVKIT_SITE_DIR/fixture.toml"\n'
            ),
        )
        result = cli(tmp_path, "site-init")
    else:
        # Exercise the interactive fallback without requiring a terminal device.
        from vig_utils import site_config

        stage = tmp_path / "stage"
        stage.mkdir()
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt: name)
        with pytest.raises(ValueError, match="reserved") as error:
            site_config.fallback(stage, tmp_path)
        assert getattr(error.value, "exit_code", None) == 2
        return
    assert result.returncode == 2, result.stderr
    assert "reserved" in result.stderr


@pytest.mark.parametrize(
    "text",
    [
        '[[RuLeS]]\nID="fixture"\nREGEX="private-pattern"',
        '[[rules]]\nid="fixture"\npath="private-pattern"',
        '[[rules]]\nid="fixture"\nregex="private-pattern"\n[[rules]]\nid="stub"',
    ],
)
def test_pattern_case_and_path_rule_supported(tmp_path, text):
    from vig_utils.site_config import validate_patterns

    path = tmp_path / "leak-patterns.toml"
    path.write_text(text)
    validate_patterns(path)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("", "rules"),
        ('[[rule]]\nid="private-id"\nregex="private-pattern"', "rules"),
        ('[rules]\nid="private-id"\nregex="private-pattern"', "rules"),
        ('[[rules]]\nid="private-id"', "rules"),
        ('[[rules]]\nid=""\nregex="private-pattern"', "rules"),
        ('[[rules]]\nid="private-id"\nregex=""', "rules"),
        ('[[rules]]\nid="private-id"\nregex="private-pattern"\n[extend]', "extend"),
        ('[[rules]]\nid="private-id"\nregex="private-pattern"\n[ExTeNd]', "extend"),
        ("rules=[]\nRules=[]", "rules"),
        (
            '[[rules]]\nid="private-id"\nID="private-other"\nregex="private-pattern"',
            "id",
        ),
        (
            '[[rules]]\nid="private-id"\nregex="private-pattern"\nRegex="private-other"',
            "regex",
        ),
    ],
)
def test_pattern_rules_reject_ambiguity_and_empty_files(tmp_path, text, key):
    from vig_utils.site_config import validate_patterns

    path = tmp_path / "leak-patterns.toml"
    path.write_text(text)
    with pytest.raises(ValueError) as error:
        validate_patterns(path)
    message = str(error.value)
    assert path.name in message and key in message.lower()
    assert "private-" not in message


def test_missing_patterns_means_no_check(tmp_path):
    from vig_utils.site_config import validate_patterns

    validate_patterns(tmp_path / "missing.toml")
