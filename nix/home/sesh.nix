# vigos.sesh — one-keypress project sessions with a standard tmux layout
# (#824). Parameterized port of the maintainer's proven setup: the hardcoded
# project list became the `sessions` option, the window set became
# `layout.windows` with devTools-only defaults. A project that should not open
# like the rest picks a named set from `layout.profiles` via its own `layout`
# field (#1583).
#
# Packages: sesh and the two generated scripts ship from here — sesh is NOT
# in devTools, so this does not duplicate vigos.packages.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.vigos.sesh;

  windowFlags = w: "-n ${lib.escapeShellArg w.name} -c \"$PWD\"";

  # Every selectable window set. `default` is `layout.windows`, so it always
  # wins over a same-named key in `profiles` — one obvious home for the
  # default set rather than two that can disagree.
  layoutProfiles = cfg.layout.profiles // {
    default = cfg.layout.windows;
  };

  # Build one profile's layout: window 1 hosts the first entry (its command
  # runs in place with a shell fallback so the window survives quitting the
  # TUI); the rest are created detached, commands typed via send-keys against
  # captured window ids (stable even if names collide or auto-rename).
  renderProfile =
    windows:
    let
      first = lib.head windows;
    in
    ''
      # Idempotent guard: re-running (or a restored session that already has
      # the first window's name) must not duplicate windows.
      if tmux list-windows -t "$sess" -F '#{window_name}' | grep -qx ${lib.escapeShellArg first.name}; then
        tmux select-window -t "$sess:${first.name}" || true
        exit 0
      fi

      tmux rename-window -t "$sess:1" ${lib.escapeShellArg first.name}
      ${lib.concatMapStringsSep "\n" (
        w:
        if w.command != null then
          ''
            wid=$(tmux new-window -d -P -F '#{window_id}' -t "$sess:" ${windowFlags w})
            tmux send-keys -t "$wid" ${lib.escapeShellArg w.command} Enter
          ''
        else
          ''tmux new-window -d -t "$sess:" ${windowFlags w}''
      ) (lib.tail windows)}
      tmux select-window -t "$sess:1"
      ${lib.optionalString (first.command != null) ''
        ${first.command} || true
      ''}
      exec "''${SHELL:-bash}"
    '';

  # One script for every profile, selected by argument. Consumers probe for
  # `sesh-layout` by name to detect a provisioned host, so the binary set
  # must not grow with the profile count.
  seshLayout = pkgs.writeShellApplication {
    name = "sesh-layout";
    runtimeInputs = [ pkgs.tmux ];
    text = ''
      profile="''${1:-default}"
      sess=$(tmux display-message -p '#S')

      case "$profile" in
        ${lib.concatStringsSep "\n  " (
          lib.mapAttrsToList (name: windows: ''
            ${name})
              ${renderProfile windows}
              ;;
          '') layoutProfiles
        )}
        *)
          printf 'sesh-layout: unknown profile %s\n' "$profile" >&2
          exit 1
          ;;
      esac
    '';
  };

  # Curated-seeds picker: fzf over the sessions list (plus live tmux
  # sessions), in sesh.toml order. Bind it where you like — tmux gets a
  # popup bind below; a desktop key is personal-config territory.
  seshPicker = pkgs.writeShellApplication {
    name = "sesh-picker";
    runtimeInputs = with pkgs; [
      sesh
      fzf
      zoxide
      tmux
    ];
    text = ''
      selected=$(sesh list -c -d -H -i | fzf --ansi --no-sort --prompt='project> ' --height=100%) || exit 0
      [ -z "$selected" ] && exit 0
      exec sesh connect "$selected"
    '';
  };

  windowModule = lib.types.submodule {
    options = {
      name = lib.mkOption {
        type = lib.types.str;
        description = "tmux window name.";
      };
      command = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Command launched in the window (null = plain shell).";
      };
    };
  };

  sessionModule = lib.types.submodule {
    options = {
      name = lib.mkOption {
        type = lib.types.str;
        example = "vigOS · devcontainer";
        description = "Picker label; use a 'Group · project' prefix to cluster the list.";
      };
      path = lib.mkOption {
        type = lib.types.str;
        description = "Project directory the session starts in.";
      };
      layout = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "docs";
        description = ''
          Layout profile this project opens with: `default` or a key of
          {option}`vigos.sesh.layout.profiles`. Null inherits the default
          through sesh's `[default_session]`.
        '';
      };
    };
  };

  # Caught here rather than left to `sesh connect`: a typo would otherwise
  # produce a sesh.toml whose sessions all fail at launch with an unknown
  # profile, far from the definition that caused it.
  layoutCommand =
    s:
    lib.throwIf (!(layoutProfiles ? ${s.layout})) ''
      vigos.sesh: session "${s.name}" selects layout profile "${s.layout}", which is not defined.
      Valid profiles: ${lib.concatStringsSep ", " (lib.attrNames layoutProfiles)}.
    '' "sesh-layout ${s.layout}";

  # A session without a profile stays bare and inherits [default_session];
  # sesh resolves per-session config ahead of it (startup.Exec: per-session
  # -> wildcard -> default), so an explicit line here wins where present.
  sessionToml =
    s:
    ''
      [[session]]
      name = "${s.name}"
      path = "${s.path}"
    ''
    + lib.optionalString (s.layout != null) ''
      startup_command = "${layoutCommand s}"
    '';
in
{
  options.vigos.sesh = {
    enable = lib.mkEnableOption "sesh project sessions with the standard tmux layout";
    sessions = lib.mkOption {
      type = lib.types.listOf sessionModule;
      default = [ ];
      description = "Curated project seeds shown by sesh-picker, in order.";
    };
    layout.windows = lib.mkOption {
      type = lib.types.listOf windowModule;
      default = [
        {
          name = "edit";
          command = "nvim .";
        }
        {
          name = "git";
          command = "lazygit";
        }
        { name = "shell"; }
        # A plain shell on purpose: no agent session/API call fires on
        # connect — type `claude` when wanted (worktrees for parallel runs).
        { name = "claude"; }
      ];
      description = "Standard window set for every new session; the first entry owns window 1.";
    };
    layout.profiles = lib.mkOption {
      type = lib.types.attrsOf (lib.types.listOf windowModule);
      default = { };
      example = lib.literalExpression ''
        {
          docs = [
            {
              name = "edit";
              command = "nvim .";
            }
            { name = "shell"; }
          ];
        }
      '';
      description = ''
        Extra named window sets a session may select through its
        {option}`layout` field, for projects that should not open like the
        rest — a repo with no pull requests has no use for a dashboard
        window. The `default` profile is {option}`layout.windows` and cannot
        be redefined here.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    home = {
      packages = [
        pkgs.sesh
        seshLayout
        seshPicker
      ];
      file.".config/sesh/sesh.toml".text = ''
        [default_session]
        startup_command = "sesh-layout"

        ${lib.concatMapStringsSep "\n" sessionToml cfg.sessions}
      '';
    };

    # prefix+o pops the picker inside tmux (merges with vigos.multiplexer).
    programs.tmux.extraConfig = lib.mkAfter ''
      bind o display-popup -E "sesh-picker"
    '';
  };
}
