# pymarkdownlnt packaged for the flake toolchain (#1170).
#
# `pymarkdownlnt` (the `pymarkdown` markdown linter) is the single residual of
# the one-hook-definition system (#883): it was not in nixpkgs, so the
# `pymarkdown` pre-commit hook could only run runner-only from its upstream
# pre-commit repo, whose native `pyjson5` C-extension fails to load on a bare
# host runner (`ImportError: libstdc++.so.6`) — which is why every direnv
# consumer silently lost markdown linting (#1167/#1168).
#
# Packaging it here promotes the hook to a `language: system` hook resolved from
# PATH, like shellcheck/typos, so it reaches the sandbox gate and the consumer
# generation surface too. Only two of its dependencies are missing from nixpkgs
# (`application-properties`, `columnar`, both small pure-Python packages); its
# JSON5 backend `pyjson5` IS in nixpkgs, so it is taken from there.
#
# A function of the (overlaid) `pkgs`; returns the wrapped `pymarkdown` CLI.
# Consumed by nix/devtools.nix (dev-shell + image + `vigos.packages`) and by the
# `pymarkdown` hook's gate/consumer fragments in nix/hooks.nix.
pkgs:
let
  # Built against the project interpreter (3.14), matching the rest of the
  # toolchain; pymarkdownlnt and both extra deps are pure Python.
  py = pkgs.python314.pkgs;

  # application-properties 0.9.x reads layered config (the `.pymarkdown` JSON the
  # hook passes via `-c`). Its JSON5 support pulls `pyjson5` (nixpkgs).
  application-properties = py.buildPythonPackage rec {
    pname = "application-properties";
    version = "0.9.3";
    pyproject = true;
    src = pkgs.fetchPypi {
      pname = "application_properties";
      inherit version;
      hash = "sha256-fcfY8j0R5TlCfnuOOvpwNT4VnBb3A7rW3Qgsxs3+6qg=";
    };
    build-system = [ py.setuptools ];
    dependencies = [
      py.typing-extensions
      py.tomli
      py.pyyaml
      py.pyjson5
    ];
    pythonImportsCheck = [ "application_properties" ];
    # The upstream test suite needs pytest + fixtures not shipped in the sdist;
    # pythonImportsCheck is the build-time smoke test here.
    doCheck = false;
  };

  # columnar renders pymarkdown's tabular scan output.
  columnar = py.buildPythonPackage rec {
    pname = "columnar";
    version = "1.4.1";
    pyproject = true;
    src = pkgs.fetchPypi {
      pname = "Columnar";
      inherit version;
      hash = "sha256-w8tXJzMzsv+c+q/IbwkwdBkzDJf6qI3P4j3wXm+7nHI=";
    };
    build-system = [ py.setuptools ];
    dependencies = [
      py.toolz
      py.wcwidth
    ];
    pythonImportsCheck = [ "columnar" ];
    doCheck = false;
  };
in
py.buildPythonPackage rec {
  pname = "pymarkdownlnt";
  version = "0.9.23";
  pyproject = true;
  src = pkgs.fetchPypi {
    inherit pname version;
    hash = "sha256-wabIYzLSU5D2FBYLObzZLdPSCxGe0HUKo/j5+L6U90w=";
  };
  build-system = [ py.setuptools ];
  dependencies = [
    application-properties
    columnar
    py.typing-extensions
  ];
  pythonImportsCheck = [ "pymarkdown" ];
  # Upstream's own test suite is heavy and not shipped complete in the sdist; the
  # hook exercises the CLI, and pythonImportsCheck covers importability.
  doCheck = false;
  meta = {
    description = "A GitHub Flavored Markdown compliant linter (pymarkdownlnt)";
    homepage = "https://github.com/jackdewinter/pymarkdown";
    mainProgram = "pymarkdown";
  };
}
