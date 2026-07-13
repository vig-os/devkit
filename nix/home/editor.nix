# vigos.editor — neovim with the Claude Code bridge (#824). Deliberately
# small (plain programs.neovim + nixpkgs vimPlugins; no nixvim input per the
# ADR): the org default is "nvim works and talks to Claude"; a richer
# editor stack stays personal.
{
  config,
  lib,
  pkgs,
  ...
}:
{
  options.vigos.editor.enable = lib.mkEnableOption "neovim with the claudecode.nvim bridge";

  config = lib.mkIf config.vigos.editor.enable {
    programs.neovim = {
      enable = lib.mkDefault true;
      defaultEditor = lib.mkDefault true;
      viAlias = lib.mkDefault true;
      vimAlias = lib.mkDefault true;
      plugins = [ pkgs.vimPlugins.claudecode-nvim ];
      initLua = lib.mkAfter ''
        -- claudecode.nvim: :ClaudeCode toggles a Claude terminal; visual
        -- selections go over with :ClaudeCodeSend.
        require("claudecode").setup({})
        vim.opt.number = true
      '';
    };
  };
}
