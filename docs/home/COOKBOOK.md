# Home environment — override cookbook

Org defaults are `lib.mkDefault`: **a bare assignment in your flake wins.**

```nix
{
  # Override a default
  programs.tmux.keyMode = "emacs";

  # Disable a whole module you don't want
  vigos.multiplexer.enable = false;   # keep your own tmux.conf

  # Append rather than replace where the underlying option supports it
  programs.tmux.extraConfig = ''
    bind r source-file ~/.config/tmux/tmux.conf
  '';

  # Force a value against a non-default org setting (rare; check why first)
  programs.gh.settings.git_protocol = lib.mkForce "https";
}
```

Keeping your own dotfile for a tool entirely: disable the module
(`vigos.<name>.enable = false`) — home-manager then leaves the file alone —
or manage the file yourself via `xdg.configFile`/`home.file`, which always
beats module-written content on conflict errors you resolve explicitly.

Per-project toolchains are **not** this layer: repos carry their own
dev-shell (`.envrc` + `mkProjectShell`), which fronts your PATH inside the
project directory and evaporates outside it.
