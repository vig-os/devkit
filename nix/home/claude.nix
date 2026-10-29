# vigos.claude — Claude Code conventions (#823, ADR Axis 5).
#
# Policy implemented here, in order of strictness:
#   never managed:  ~/.claude.json, settings.local.json (mutable runtime state)
#   seeded:         settings.json — copy-if-absent, then user-owned (Claude
#                   rewrites it; org seed updates are announced in the
#                   changelog, re-seed = delete + re-activate)
#   managed (copy): ~/.claude/vigos.md org fragment — checksum-overwrite with
#                   a .bak of local edits. No symlinks of ANY kind under
#                   ~/.claude/ (store symlinks break Claude's sandbox and
#                   atomic writes; out-of-store needs a local checkout).
# The user-owned ~/.claude/CLAUDE.md gets a single `@vigos.md` import line
# seeded (created if missing, appended once if absent — Claude Code itself
# writes to this file via the memory feature, so it is never overwritten).
# Packages: none — claude-code, nodejs, uv ship via vigos.packages (devTools + agent-tools).
# Org defaults pre-authorize nothing (no permission modes in the seed).
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.vigos.claude;
  settingsFormat = pkgs.formats.json { };
  seedFile = settingsFormat.generate "vigos-claude-settings-seed.json" cfg.settingsSeed;
  fragment = ./claude/vigos.md;
in
{
  options.vigos.claude = {
    enable = lib.mkEnableOption "the vigOS Claude Code conventions (~/.claude seeding + org fragment)";
    settingsSeed = lib.mkOption {
      inherit (settingsFormat) type;
      default = {
        includeCoAuthoredBy = false;
      };
      description = ''
        Initial content for ~/.claude/settings.json, written only when the
        file does not exist (user-owned afterwards). The default enforces the
        org's no-AI-attribution rule and nothing else.
      '';
    };
    claudeMd.workspaceFiles = lib.mkOption {
      type = lib.types.attrsOf lib.types.path;
      default = { };
      example = lib.literalExpression ''{ "Documents/CLAUDE.md" = ./workspace-root.md; }'';
      description = ''
        Optional workspace-level CLAUDE.md files to manage, keyed by path
        relative to the home directory (templates: docs/home/claude-md/).
        Empty by default — guidelines, not enforcement.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    home = {
      # Nix owns claude-code updates; the native self-updater stays off. Set
      # here (not in the user-editable seed) so the promise survives edits.
      sessionVariables.DISABLE_AUTOUPDATER = lib.mkDefault "1";

      file = lib.mapAttrs (_name: source: { inherit source; }) cfg.claudeMd.workspaceFiles;

      activation.vigosClaude = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        claudeDir="$HOME/.claude"
        run mkdir -p "$claudeDir"

        # settings.json: seed once, never touch again.
        if [ ! -e "$claudeDir/settings.json" ]; then
          run install -m 0644 ${seedFile} "$claudeDir/settings.json"
        fi

        # vigos.md fragment: checksum-overwrite, .bak of local edits.
        if ! cmp -s ${fragment} "$claudeDir/vigos.md" 2>/dev/null; then
          if [ -e "$claudeDir/vigos.md" ]; then
            run cp "$claudeDir/vigos.md" "$claudeDir/vigos.md.bak"
          fi
          run install -m 0644 ${fragment} "$claudeDir/vigos.md"
        fi

        # CLAUDE.md: user-owned; ensure the @vigos.md import line exists once.
        if [ ! -e "$claudeDir/CLAUDE.md" ]; then
          run sh -c 'printf "@vigos.md\n" > "$1"' _ "$claudeDir/CLAUDE.md"
        elif ! grep -q "^@vigos\.md$" "$claudeDir/CLAUDE.md"; then
          run sh -c 'printf "\n@vigos.md\n" >> "$1"' _ "$claudeDir/CLAUDE.md"
        fi
      '';
    };
  };
}
