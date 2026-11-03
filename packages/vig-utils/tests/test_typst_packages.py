"""Dependency artifacts and process lifecycle for the docs compiler wrapper."""

import json
import os
import select
import shutil
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

import pytest
from vig_utils import typst_packages


@pytest.fixture
def compiler(tmp_path):
    source = tmp_path / "source space #$colon:" / "local/mypkg/0.1.0"
    source.mkdir(parents=True)
    (source / "lib.typ").write_text("Content")
    outer = tmp_path / "outer"
    outer.mkdir()
    temporary = tmp_path / "temporary unions #$"
    temporary.mkdir()
    script = tmp_path / "compiler.py"
    script.write_text("""import json, os, signal, sys
from contextlib import suppress
from pathlib import Path
args = sys.argv[1:]
union = Path(os.environ["TYPST_PACKAGE_PATH"])
def option(name, default):
    value = default
    for i, arg in enumerate(args):
        if arg == name:
            value = args[i + 1]
        elif arg.startswith(name + "="):
            value = arg.split("=", 1)[1]
    return value
def make_path(path):
    return "".join("$$" if c == "$" else "\\\\" + c if c in " \\t#:\\\\" else c for c in str(path))
path = str(union / "local/mypkg/0.1.0/lib.typ")
fmt = option("--deps-format", "json")
data = {"json": json.dumps({"inputs": [path], "outputs": ["main.pdf"]}).encode(),
        "make": ("main.pdf: " + make_path(path) + "\\n").encode(),
        "zero": os.fsencode(path) + b"\\0"}[fmt]
Path("union.json").write_text(json.dumps(str(union)))
if "--no-deps" in args:
    sys.exit(1)
output = option("--deps", "-")
if output == "-":
    sys.stdout.buffer.write(data)
else:
    Path(output).write_bytes(data)
    if "watch" not in args:
        print("Compiler stdout")
if "watch" in args:
    for signum in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, signal.SIG_DFL)
    print(json.dumps({"pid": os.getpid(), "union": str(union)}), flush=True)
    while True:
        signal.pause()
sys.exit(int(option("--exit-code", "0")))
""")
    env = dict(os.environ, TYPST_PACKAGE_PATH=str(outer), TMPDIR=str(temporary))
    argv = [
        sys.executable,
        "-c",
        "from vig_utils.typst_packages import main; raise SystemExit(main())",
        str(source.parents[2]),
        sys.executable,
        str(script),
    ]
    return argv, env, source


@pytest.mark.parametrize("code", [0, 143])
@pytest.mark.parametrize("fmt", ["json", "make", "zero"])
@pytest.mark.parametrize("joined_deps", [False, True])
@pytest.mark.parametrize("joined_format", [False, True])
@pytest.mark.parametrize("stdout", [False, True])
def test_dependency_spellings_and_formats(
    compiler, tmp_path, fmt, joined_deps, joined_format, stdout, code
):
    argv, env, source = compiler
    output = "-" if stdout else "deps.out"
    flags = [f"--deps={output}"] if joined_deps else ["--deps", output]
    flags += [f"--deps-format={fmt}"] if joined_format else ["--deps-format", fmt]
    result = subprocess.run(
        [*argv, *flags, f"--exit-code={code}"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode == code, result.stderr
    data = result.stdout if stdout else (tmp_path / output).read_bytes()
    assert b"/devkit-typst-packages-" not in data, data
    target = source / "lib.typ"
    if fmt == "json":
        assert json.loads(data)["inputs"] == [str(target)]
    elif fmt == "zero":
        assert data.split(b"\0") == [os.fsencode(target), b""]
    else:
        escaped = "".join(
            "$$" if c == "$" else "\\" + c if c in " \t#:\\" else c for c in str(target)
        )
        assert data == f"main.pdf: {escaped}\n".encode()
    assert not Path(json.loads((tmp_path / "union.json").read_text())).exists()
    if not stdout:
        assert result.stdout == b"Compiler stdout\n"


@pytest.mark.parametrize("signum", [signal.SIGHUP, signal.SIGTERM, signal.SIGINT])
@pytest.mark.parametrize("fmt", ["json", "zero"])
def test_signals_reach_child_and_cleanup_union(compiler, tmp_path, signum, fmt):
    argv, env, source = compiler
    process = subprocess.Popen(
        [*argv, "watch", "--deps=deps.out", f"--deps-format={fmt}"],
        env=env,
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    child = None
    try:
        assert select.select([process.stdout], [], [], 10)[0], (
            "child never became ready"
        )
        child = json.loads(process.stdout.readline())
        process.send_signal(signum)
        _, stderr = process.communicate(timeout=10)
        assert process.returncode == 128 + signum, stderr
        with pytest.raises(ProcessLookupError):
            os.kill(child["pid"], 0)
        data = (tmp_path / "deps.out").read_bytes()
        assert b"/devkit-typst-packages-" not in data, data
        names = (
            json.loads(data)["inputs"]
            if fmt == "json"
            else [os.fsdecode(n) for n in data.split(b"\0") if n]
        )
        assert names == [str(source / "lib.typ")]
        assert not Path(child["union"]).exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if child:
            with suppress(ProcessLookupError):
                os.kill(child["pid"], signal.SIGTERM)


@pytest.fixture
def registry(tmp_path):
    assets = Path(__file__).resolve().parents[3] / "assets/typst"
    root = tmp_path / "registry"
    shutil.copytree(assets / "vendor/preview", root / "preview")
    shutil.copytree(assets / "releases/devkit-docs", root / "local/devkit-docs")
    shutil.copytree(assets / "devkit-docs", root / "local/devkit-docs/0.1.1")
    shutil.copy(assets / "devkit-docs.lock.json", root)
    if (assets / "released-packages.json").exists():
        shutil.copy(assets / "released-packages.json", root)
    return root


@pytest.mark.parametrize("mutation", ["vendor", "release", "nested-license"])
def test_registry_integrity_rejects_mutations(registry, mutation):
    verify = typst_packages.verify_registry
    verify(registry)
    if mutation == "vendor":
        path = registry / "preview/cetz/0.3.4/src/aabb.typ"
        path.write_bytes(path.read_bytes() + b"\n// changed\n")
    elif mutation == "release":
        shutil.rmtree(registry / "local/devkit-docs/0.1.0")
        lock_path = registry / "devkit-docs.lock.json"
        lock = json.loads(lock_path.read_text())
        lock.pop("local/devkit-docs/0.1.0", None)
        lock.pop("0.1.0", None)
        lock_path.write_text(json.dumps(lock))
    else:
        path = registry / "local/devkit-docs/0.1.1/nested/LICENSE"
        path.parent.mkdir()
        path.write_text("New nested content")
    with pytest.raises(ValueError):
        verify(registry)


def test_only_injected_root_license_is_excluded(registry):
    verify = typst_packages.verify_registry
    verify(registry)
    (registry / "local/devkit-docs/0.1.1/LICENSE").write_text(
        "Injected repository license"
    )
    verify(registry)


@pytest.mark.parametrize("suffix", ["\nunsafe", "\\unsafe"])
def test_make_unrepresentable_destination_keeps_compiler_success(
    compiler, tmp_path, suffix
):
    argv, env, source = compiler
    root = source.parents[2]
    renamed = root.with_name(root.name + suffix)
    root.rename(renamed)
    argv[3] = str(renamed)
    result = subprocess.run(
        [*argv, "--deps-format=make", "--deps=deps.out"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert b"/devkit-typst-packages-" in (tmp_path / "deps.out").read_bytes()
    assert not Path(json.loads((tmp_path / "union.json").read_text())).exists()


@pytest.mark.parametrize("code", [0, 143])
def test_artifact_rewrite_io_failure_preserves_child_exit(
    compiler, tmp_path, monkeypatch, capsys, code
):
    argv, env, _ = compiler
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TYPST_PACKAGE_PATH", env["TYPST_PACKAGE_PATH"])
    monkeypatch.setattr(
        sys,
        "argv",
        ["typst-with-packages", *argv[3:], "--deps=deps.out", f"--exit-code={code}"],
    )

    def fail_replace(*args, **kwargs):
        raise OSError("artifact replacement denied")

    monkeypatch.setattr(Path, "replace", fail_replace)
    assert typst_packages.main() == code
    assert "artifact unchanged" in capsys.readouterr().err
    assert b"/devkit-typst-packages-" in (tmp_path / "deps.out").read_bytes()


@pytest.mark.parametrize("fmt", ["json", "make", "zero"])
@pytest.mark.parametrize("code", [0, 143])
def test_dependency_symlink_is_preserved(compiler, tmp_path, fmt, code):
    argv, env, source = compiler
    target = tmp_path / "real.deps"
    target.touch()
    link = tmp_path / "deps.out"
    link.symlink_to(target.name)
    result = subprocess.run(
        [*argv, "--deps=deps.out", f"--deps-format={fmt}", f"--exit-code={code}"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode == code, result.stderr
    assert link.is_symlink()
    data = target.read_bytes()
    assert data == link.read_bytes() and b"/devkit-typst-packages-" not in data
    if fmt == "json":
        assert json.loads(data)["inputs"] == [str(source / "lib.typ")]
    assert not Path(json.loads((tmp_path / "union.json").read_text())).exists()


def test_failed_child_without_artifact_keeps_exit_and_diagnostics(compiler, tmp_path):
    argv, env, _ = compiler
    result = subprocess.run(
        [*argv, "--deps=missing.deps", "--no-deps"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1 and result.stderr == b""
    assert not (tmp_path / "missing.deps").exists()
    assert not Path(json.loads((tmp_path / "union.json").read_text())).exists()
