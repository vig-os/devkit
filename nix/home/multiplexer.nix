# vigos.multiplexer — org tmux configuration (#821).
#
# Config only where possible; the tmux binary itself also ships via
# vigos.packages (devTools). programs.tmux hard-requires a package for its
# plugin/wrapper plumbing — it comes from this module's pkgs (self-pkgs in
# the flake's own homeConfigurations), matching the devTools version, so no
# second copy appears in practice. extraConfig stays open for personal
# keybindings.
{
  config,
  lib,
  ...
}:
{
  options.vigos.multiplexer.enable = lib.mkEnableOption "the vigOS tmux configuration";

  config = lib.mkIf config.vigos.multiplexer.enable {
    programs.tmux = {
      enable = lib.mkDefault true;
      # vi keys and a sane scrollback are org defaults; everything is
      # mkDefault so a personal config overrides with a bare assignment.
      keyMode = lib.mkDefault "vi";
      historyLimit = lib.mkDefault 100000;
      mouse = lib.mkDefault true;
      escapeTime = lib.mkDefault 10;
      baseIndex = lib.mkDefault 1;
      # home-manager defaults to "screen": 8 colors, no italics, for every
      # colored tool the org ships (starship, neovim, delta, lazygit,
      # gh-dash) the moment it runs inside tmux (#1605).
      terminal = lib.mkDefault "tmux-256color";
    };

    # Keybindings and settings a host gets purely by enabling the module,
    # rather than every consumer re-deriving them (#1605). Plain (not
    # mkAfter) so the merged tmux.conf keeps these first: tmux takes the
    # LAST binding of a key, so a consumer's own `lib.mkAfter` block — the
    # seam vigos.sesh already uses for `bind o` — still wins.
    programs.tmux.extraConfig = ''
      # End a project. `X` is unbound in stock tmux, so this takes nothing
      # away, and vigos.sesh makes the session the unit of work. The confirm
      # prompt keeps a stray prefix from destroying a project's layout.
      bind-key X confirm-before -p "kill session '#S'? (y/n)" kill-session

      # Truecolor on top of the tmux-256color terminal above.
      set -ga terminal-overrides ",*256col*:Tc"

      # Splits and new windows inherit the pane's cwd (stock tmux starts them
      # in the session's), window numbers stay contiguous after a close, and
      # focus events reach the editor (neovim autoread/autosave).
      bind '"' split-window -v -c "#{pane_current_path}"
      bind % split-window -h -c "#{pane_current_path}"
      bind c new-window -c "#{pane_current_path}"
      set -g renumber-windows on
      set -g focus-events on

      # OSC 52: a yank inside tmux on a remote host reaches the LOCAL
      # clipboard with no X forwarding. v/y match the module's own vi
      # keyMode, which stock tmux does not bind in copy mode.
      set -g set-clipboard on
      bind-key -T copy-mode-vi v send-keys -X begin-selection
      bind-key -T copy-mode-vi y send-keys -X copy-pipe-and-cancel

      # Killing one project switches to another live session instead of
      # dropping to a bare shell (the client still detaches if it was the
      # last one); titles make several terminal windows distinguishable by
      # project rather than all showing the launch command.
      set -g detach-on-destroy off
      set -g set-titles on
      set -g set-titles-string "#S"

      # Pane navigation coherent with the vi keyMode. The one default this
      # module replaces: `prefix + l` was last-window.
      bind h select-pane -L
      bind j select-pane -D
      bind k select-pane -U
      bind l select-pane -R
    '';
  };
}
