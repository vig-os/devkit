# INERT EXAMPLE — see ./README.md. Illustrative NixOS/home-manager wiring for
# sops-nix; NOT imported by this repo's flake, image, or any live path.
#
# Real use: add sops-nix as a flake input and import its NixOS (or home-manager)
# module, then configure the three things below. Adapted from the sops-nix docs
# (https://github.com/Mic92/sops-nix).
{
  # 1. Where the machine's OWN private key lives. Two common options:
  #    (a) derive from the existing SSH host key (no extra key to manage):
  sops.age.sshKeyPaths = [ "/etc/ssh/ssh_host_ed25519_key" ];
  #    (b) or a dedicated age key file (optionally auto-generated on first boot):
  #    sops.age.keyFile = "/var/lib/sops-nix/key.txt";
  #    sops.age.generateKey = true;

  # 2. Which encrypted file holds the secrets (the sops-managed file, encrypted
  #    to the recipients in .sops.yaml). Here it points at the example shape.
  sops.defaultSopsFile = ./secrets.example.yaml;

  # 3. Declare each secret this machine needs. sops-nix decrypts them at
  #    activation into /run/secrets/<name> with the owner/mode you set.
  sops.secrets."example_service/api_token" = {
    # owner = "example-service"; # the service user that reads it
    # mode  = "0400";
    # path  = "/run/secrets/example_service_api_token"; # override default path
  };

  # A consumer service then reads the decrypted value from the runtime path,
  # never from the Nix store (secrets are NOT world-readable in the store):
  #   systemd.services.example-service.serviceConfig.EnvironmentFile =
  #     config.sops.secrets."example_service/api_token".path;
}
