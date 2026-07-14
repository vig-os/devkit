# `native` capability module (#884): the generic native-build (sdist)
# capability — compiler + the build tools PEP 517 backends actually invoke
# (scikit-build-core, setuptools, meson-python). The long-term consumer
# answer to #879: the image-side sysconfig sanitize (0.4.1, #893) makes
# build backends fall back to PATH discovery with generic cc/c++ names,
# and this module provides that PATH. Field-validated need: hyrr/pycatima
# (#639). Third-party libraries (Geant4, ROOT, OCCT, …) stay per-project
# `extraPackages` — or a future ask-gated module.
#
# Takes no options (`_options`): the module calling convention is uniformly
# `pkgs -> options -> contribution` since #1027 landed per-module options; the
# native capability has nothing to configure.
pkgs: _options: {
  packages = with pkgs; [
    # C/C++ compiler wrapper: puts cc/c++ (and gcc/g++) on PATH and links
    # against the same Nix C++ runtime the toolchain SSoT already exposes.
    stdenv.cc
    cmake
    gnumake
    pkg-config
  ];

  # Generic POSIX names, not store paths: build backends that consult the
  # environment resolve them via the PATH above, matching the sanitized
  # image sysconfig (#879/#893) and staying honest when a consumer swaps
  # the compiler via extraPackages (which wins PATH lookup — see the ADR
  # composition rules). Exported as a shellHook fragment, NOT as `env`:
  # stdenv.cc's own setup hook exports CC=gcc/CXX=g++ while `nix develop`
  # computes the shell environment, which would clobber a static env attr;
  # the shellHook runs after every setup hook, so the generic names win.
  shellHook = ''
    export CC=cc
    export CXX=c++
  '';
}
