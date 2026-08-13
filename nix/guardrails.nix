# Packaging for the vendored guardrails gates (#1488).
#
# Each script in assets/guardrails/gates/ becomes `guardrails-<name>` on PATH,
# and the three tools become `guardrails`, `guardrails-trace` and
# `guardrails-trace-report`. The names are preserved EXACTLY as upstream
# published them, and that is a deliberate compatibility decision rather than
# inertia: `guardrails-ok` is an annotation that lives in consumer SOURCE
# (21 sites in the first consumer alone), `GUARDRAILS_*` env vars are set in
# consumer flakes, and the hook ids appear in committed `.pre-commit-config.yaml`
# files. Renaming any of that to match devkit would be a breaking change to
# every consumer's source code for no functional gain — devkit already ships
# `ruff` and `typos` under their upstream ids without renaming them either.
#
# The scripts are wrapped rather than copied so their runtime dependencies
# resolve from the store instead of from whatever the consumer happens to have
# on PATH. That is not hypothetical tidiness: the first consumer's entire hook
# stack once resolved from a developer's global profile, worked on that
# machine, and would have failed in CI and for every new contributor.
{
  lib,
  stdenvNoCC,
  makeWrapper,
  bash,
  coreutils,
  findutils,
  gnugrep,
  gnused,
  gawk,
  diffutils,
  git,
  jq,
  ripgrep,
  python3,
}:

let
  # Everything the gates shell out to. Kept explicit — a gate that silently
  # falls back to a missing tool is the failure this whole set exists to catch.
  runtimeInputs = [
    bash
    coreutils
    findutils
    gnugrep
    gnused
    gawk
    diffutils
    git
    jq
    ripgrep
    python3
  ];
in
stdenvNoCC.mkDerivation {
  pname = "guardrails";
  version = "0-unstable-2026-08-13";

  src = ../assets/guardrails;

  nativeBuildInputs = [ makeWrapper ];

  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/bin" "$out/share/guardrails"

    # Gates: gates/<name>.sh -> guardrails-<name>.
    #
    # test-*.sh live in this directory because they resolve their subjects via
    # `dirname "$0"` — upstream's layout, kept so the scripts run unmodified.
    # They are fixtures, not gates, so they do not become executables; the
    # canary check runs them from share/ instead.
    for f in gates/*.sh; do
      base="$(basename "$f" .sh)"
      case "$base" in test-*) continue ;; esac
      name="guardrails-$base"
      install -Dm755 "$f" "$out/bin/$name"
      wrapProgram "$out/bin/$name" --prefix PATH : ${lib.makeBinPath runtimeInputs}
    done

    # Tools: tools/trace.sh -> guardrails-trace, tools/guardrails.sh -> guardrails
    for f in tools/*.sh; do
      base="$(basename "$f" .sh)"
      if [ "$base" = "guardrails" ]; then name="guardrails"; else name="guardrails-$base"; fi
      install -Dm755 "$f" "$out/bin/$name"
      wrapProgram "$out/bin/$name" --prefix PATH : ${lib.makeBinPath runtimeInputs}
    done

    # The whole tree ships to share/ so the canary check runs the fixtures
    # against the SAME scripts a consumer gets, not a copy — and because the
    # fixtures resolve siblings relatively, they need the layout intact.
    cp -r gates tools "$out/share/guardrails/"
    [ -d templates ] && cp -r templates "$out/share/guardrails/" || true

    runHook postInstall
  '';

  # Exposed so the canary check can put the SAME dependency set on PATH.
  # The fixtures resolve their subjects as siblings via `dirname "$0"`, so
  # they run the unwrapped share/ copies — which means the wrapper's PATH is
  # not in effect and the check has to supply it. One list, two consumers:
  # a dependency added here cannot be forgotten there.
  passthru = { inherit runtimeInputs; };

  meta = {
    description = "Semantic code gates (vendored from gerchowl/guardrails, now devkit-owned)";
    license = lib.licenses.asl20;
    platforms = lib.platforms.unix;
  };
}
