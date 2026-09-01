# vigos.sesh — one-keypress project sessions with a standard tmux layout
# (#824). Parameterized port of the maintainer's proven setup: the hardcoded
# project list became the `sessions` option, the window set became
# `layout.windows` with devTools-only defaults. A project that should not open
# like the rest picks a named set from `layout.profiles` via its own `layout`
# field (#1583). Projects checked out on other machines are reachable through
# the `remotes` inventory and the picker's runner stage (#1585).
#
# Packages: sesh and the three generated scripts ship from here — sesh is NOT
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

  # Attach-or-create a project session on a remote host:
  #   sesh-remote-connect <host> <session-name> <remote-path>
  # Called by sesh-picker for remote runners; fine to run by hand too.
  # `tmux new -A` is idempotent — attach if the session exists, create it
  # otherwise — which is what makes "leave it running, reattach later" work
  # with no state on this machine. TERM is forced to an entry every remote
  # terminfo db has, because a modern local terminal's own TERM is frequently
  # unknown off-NixOS and the session comes up broken.
  seshRemoteConnect = pkgs.writeShellApplication {
    name = "sesh-remote-connect";
    runtimeInputs = with pkgs; [
      openssh
      coreutils
    ];
    text = ''
      host=$1
      session=$2
      path=$3

      # The remote command is a tiered dispatch: probe and launch happen in
      # the same ssh round-trip, so capability detection is always current
      # and needs no local per-host flags or cache (a declared capability
      # flag would be a second source of truth that goes stale).
      #
      #   1. sesh-layout on PATH  -> full standard layout. Its presence is an
      #      all-or-nothing test for a provisioned host (remote sesh itself
      #      is not needed: tmux runs the layout as the session's startup
      #      command on create and ignores it on attach).
      #   2. tmux only            -> persistent blank session (baseline).
      #   3. neither              -> plain login shell at the project path,
      #      after an unmissable warning that nothing survives a disconnect.
      #
      # Non-interactive ssh shells do not load home-manager session vars, so
      # the dispatch first prepends the two per-user Nix profile bin dirs.
      # The quoted heredoc keeps every $-expansion remote; __NAME__ and
      # __PATH__ are substituted locally below — session names and paths in
      # this config carry no single quotes, so plain single-quoting survives
      # the remote shell.
      dispatch=$(cat <<'EOF'
      PATH="$HOME/.nix-profile/bin:/etc/profiles/per-user/''${USER:-$(id -un)}/bin:$PATH"
      if command -v sesh-layout >/dev/null 2>&1; then
        exec tmux new-session -A -s __NAME__ -c __PATH__ sesh-layout
      elif command -v tmux >/dev/null 2>&1; then
        exec tmux new-session -A -s __NAME__ -c __PATH__
      else
        printf '\n\033[1;31mWARNING:\033[0m no tmux on this host - this session will NOT survive a disconnect.\n\n'
        cd __PATH__ 2>/dev/null || printf 'note: __PATH__ not found, staying in %s\n' "$HOME"
        exec "''${SHELL:-sh}" -l
      fi
      EOF
      )
      remote_cmd=''${dispatch//__NAME__/"'$session'"}
      remote_cmd=''${remote_cmd//__PATH__/"'$path'"}

      export TERM=xterm-256color
      if ! ssh -t -o ConnectTimeout=5 "$host" -- "$remote_cmd"; then
        # Hold the window open on failure (host unreachable, tmux missing,
        # bad path) so the error is readable; a clean detach exits 0 and
        # closes normally.
        printf '\nsesh-remote-connect: session on %s ended with an error.\n' "$host"
        read -rsn1 -p 'press any key to close'
      fi
    '';
  };

  # The picker must not nest a remote tmux inside the local server when it is
  # invoked from a tmux popup. With `remoteTerminal` set the ssh client gets
  # its own terminal window; the null default opens a local tmux window
  # instead — degraded (nested prefix keys) but functional everywhere, with
  # no personal terminal baked into the module.
  remoteEscapeHatch =
    if cfg.remoteTerminal != null then
      ''
        setsid ${cfg.remoteTerminal} sesh-remote-connect "$choice" "$name" "$rpath" >/dev/null 2>&1 &
        exit 0
      ''
    else
      ''exec tmux new-window -n "$name" sesh-remote-connect "$choice" "$name" "$rpath"'';

  # Curated-seeds picker: fzf over the sessions list (plus live tmux
  # sessions), in sesh.toml order. Bind it where you like — tmux gets a
  # popup bind below; a desktop key is personal-config territory.
  #
  # With a populated `remotes` inventory the picker grows a second stage:
  # stage 1 picks the project, stage 2 the *runner* (local or an SSH host) —
  # and only appears when there is a real choice. The last-used runner per
  # project is remembered and pre-selected, so `Enter Enter` returns to
  # wherever the session was left. One script for both shapes: the
  # empty-inventory guard at the top keeps today's one-stage flow bit-for-bit
  # rather than a second generated picker that could drift.
  seshPicker = pkgs.writeShellApplication {
    name = "sesh-picker";
    runtimeInputs = with pkgs; [
      sesh
      fzf
      zoxide
      tmux
      gawk
      gnugrep
      coreutils
      util-linux
      seshRemoteConnect
    ];
    text = ''
      remotes="''${XDG_CONFIG_HOME:-$HOME/.config}/sesh/remotes.tsv"

      # No inventory -> today's behaviour, unchanged.
      if [ ! -s "$remotes" ]; then
        selected=$(sesh list -c -d -H -i | fzf --ansi --no-sort --prompt='project> ' --height=100%) || exit 0
        [ -z "$selected" ] && exit 0
        exec sesh connect "$selected"
      fi

      state_dir="''${XDG_STATE_HOME:-$HOME/.local/state}/sesh-picker"
      state="$state_dir/last-runner"
      mkdir -p "$state_dir"
      touch "$state"

      # ── Stage 1: project ──
      # Local seeds keep sesh's own icons; remote-only entries (in the
      # inventory but not sesh.toml — e.g. plain host access) are appended
      # with a portable marker. Every line is "<glyph> <name>", so stripping
      # through the first space recovers the bare name.
      selected=$(
        {
          sesh list -c -d -H -i
          awk -F'\t' '
            NR == FNR { if ($0 != "") local[$0] = 1; next }
            $1 != "" && !($1 in local) && !($1 in seen) {
              seen[$1] = 1
              printf "⇄ %s\n", $1
            }' <(sesh list -c -d) "$remotes"
        } | fzf --ansi --no-sort --prompt='project> ' --height=100%
      ) || exit 0
      [ -z "$selected" ] && exit 0
      name="''${selected#* }"

      # ── Stage 2: runner ──
      # Shown only when the project has more than one possible location; a
      # purely local project or a single-runner entry keeps the current
      # one-keystroke flow. Stable order (local first, then inventory order);
      # the cursor starts on the last-used runner.
      runners=()
      if sesh list -c -d | grep -qxF "$name"; then
        runners+=("local")
      fi
      remote_count=0
      while IFS=$'\t' read -r p h _; do
        if [ "$p" = "$name" ]; then
          runners+=("$h")
          remote_count=$((remote_count + 1))
        fi
      done < "$remotes"

      if [ "$remote_count" -eq 0 ]; then
        # No remote runners -> local-only project; connect as the one-stage
        # picker does (also covers the not-in-either-source edge).
        exec sesh connect "$name"
      fi

      if [ "''${#runners[@]}" -eq 1 ]; then
        choice="''${runners[0]}"
      else
        last=$(awk -F'\t' -v n="$name" '$1 == n { print $2 }' "$state")
        pos=1
        for i in "''${!runners[@]}"; do
          if [ "''${runners[$i]}" = "$last" ]; then
            pos=$((i + 1))
            break
          fi
        done
        choice=$(printf '%s\n' "''${runners[@]}" \
          | fzf --no-sort --prompt='runner> ' --header="$name" --height=100% \
                --sync --bind "start:pos($pos)") || exit 0
        [ -z "$choice" ] && exit 0
      fi

      # Remember the choice as next time's pre-selection (atomic rewrite).
      tmp=$(mktemp "$state_dir/.last-runner.XXXXXX")
      awk -F'\t' -v n="$name" '$1 != n' "$state" > "$tmp"
      printf '%s\t%s\n' "$name" "$choice" >> "$tmp"
      mv "$tmp" "$state"

      if [ "$choice" = "local" ]; then
        exec sesh connect "$name"
      fi

      rpath=$(awk -F'\t' -v n="$name" -v h="$choice" '$1 == n && $2 == h { print $3; exit }' "$remotes")

      if [ -n "''${TMUX:-}" ]; then
        ${remoteEscapeHatch}
      fi
      exec sesh-remote-connect "$choice" "$name" "$rpath"
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

  remoteModule = lib.types.submodule {
    options = {
      project = lib.mkOption {
        type = lib.types.str;
        description = ''
          Picker label this entry belongs to: a `sessions[].name` (the
          project then offers several runners), or a standalone name for a
          host-access entry that is not a local project.
        '';
      };
      host = lib.mkOption {
        type = lib.types.str;
        description = "An `~/.ssh/config` alias — no connection details live here.";
      };
      path = lib.mkOption {
        type = lib.types.str;
        description = "Project root on that host.";
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
    remotes = lib.mkOption {
      type = lib.types.listOf remoteModule;
      default = [ ];
      example = lib.literalExpression ''
        [
          {
            project = "vigOS · devkit";
            host = "buildbox";
            path = "/home/me/devkit";
          }
        ]
      '';
      description = ''
        Remote project seeds — one entry per project × host — offered by the
        picker's runner stage and opened via `sesh-remote-connect` (which
        probes the host's capability at connect time: standard layout, bare
        tmux, or a warned plain shell). Empty — the default — leaves the
        one-stage picker behaviour unchanged. The inventory itself is
        consumer data; only the type lives here.
      '';
    };
    remoteTerminal = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "ghostty -e";
      description = ''
        Command prefix that opens the ssh client in its own terminal window
        when a remote runner is picked from inside tmux (a remote tmux must
        not nest in the local server's popup). Null — the default — opens a
        local tmux window instead: functional everywhere, at the cost of
        nested prefix keys. The concrete terminal is personal-config
        territory, hence an option rather than a default binary.
      '';
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
        # Ships unconditionally: useful standalone, and consumers probe hosts
        # by capability at connect time rather than by config presence.
        seshRemoteConnect
      ];
      file = {
        ".config/sesh/sesh.toml".text = ''
          [default_session]
          startup_command = "sesh-layout"

          ${lib.concatMapStringsSep "\n" sessionToml cfg.sessions}
        '';
      }
      # Rendered only when the inventory is populated, so the empty default
      # is a bit-for-bit no-op (and directly assertable as one).
      // lib.optionalAttrs (cfg.remotes != [ ]) {
        ".config/sesh/remotes.tsv".text = lib.concatMapStrings (
          r: "${r.project}\t${r.host}\t${r.path}\n"
        ) cfg.remotes;
      };
    };

    # prefix+o pops the picker inside tmux (merges with vigos.multiplexer).
    programs.tmux.extraConfig = lib.mkAfter ''
      bind o display-popup -E "sesh-picker"
    '';
  };
}
