{
  description = "Personal home environment on the vigOS home modules.";

  inputs = {
    # Pin a devkit release tag once you depend on module-option stability
    # (docs/NIX.md "Home-manager modules - versioning & release policy"):
    #   vigos.url = "github:vig-os/devcontainer?ref=<tag>";
    vigos.url = "github:vig-os/devcontainer";
    nixpkgs.follows = "vigos/nixpkgs";
    home-manager.follows = "vigos/home-manager";
  };

  outputs =
    {
      vigos,
      nixpkgs,
      home-manager,
      ...
    }:
    {
      # Activate with: home-manager switch --flake .#me
      homeConfigurations.me = home-manager.lib.homeManagerConfiguration {
        pkgs = import nixpkgs {
          system = "x86_64-linux"; # aarch64-darwin on an Apple-silicon Mac
          overlays = [ vigos.overlays.default ]; # fast-movers (claude-code, uv, gh)
          config.allowUnfree = true; # claude-code
        };
        modules = [
          vigos.homeManagerModules.default
          {
            home = {
              username = "me"; # your unix user
              homeDirectory = "/home/me"; # /Users/me on macOS
              stateVersion = "26.05";
            };
            vigos = {
              packages.enable = true;
              shell.enable = true;
              multiplexer.enable = true;
              cli.enable = true;
              direnv.enable = true;
              git = {
                enable = true;
                userName = "Your Name";
                userEmail = "you@example.com";
              };
            };
          }
        ];
      };
    };
}
