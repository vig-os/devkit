# sops-nix + age — inert reference example

> **This is an illustrative, non-functional example.** It is documentation for
> the pattern recorded in [`../../ADR-secrets-management.md`](../../ADR-secrets-management.md)
> (issue [#780](https://github.com/vig-os/devkit/issues/780)). It is **not**
> imported by `flake.nix`, the image build, or any release/CI path, and it must
> **never** be wired into a live path.
>
> - The `age` recipients in `.sops.yaml` are **placeholders**, not real keys.
> - `secrets.example.yaml` is **plaintext** and holds only a fake value — it is
>   deliberately *not* a real sops-encrypted file, so nothing here decrypts to a
>   secret. Never commit a real key or a real encrypted secret to this repo.

## What the three files show

| File | Role |
|------|------|
| [`.sops.yaml`](./.sops.yaml) | `creation_rules` mapping secret paths → the `age` recipients allowed to decrypt them (the per-consumer key group). |
| [`secrets.example.yaml`](./secrets.example.yaml) | The *shape* of a secrets file. In real use you would `sops secrets.yaml` to edit it and sops would encrypt the values in place; here it stays plaintext and inert. |
| [`example.nix`](./example.nix) | The NixOS/home-manager module wiring: point `sops-nix` at the file + the machine's own key, declare secrets, and read them from `/run/secrets/<name>`. |

## The lifecycle in real use (do not run against this example)

1. **Each consumer generates an `age` keypair once:**
   `age-keygen -o ~/.config/sops/age/keys.txt` (or derive from an existing SSH
   host key with `ssh-to-age`). The **public** recipient (`age1…`) is shared; the
   private key never leaves the machine.
2. **Add the recipient to `.sops.yaml`** under the relevant `creation_rules`
   `age:` group and re-encrypt (`sops updatekeys secrets.yaml`). This is a
   public-key operation — no secret is handed over.
3. **Edit secrets** with `sops secrets.yaml`; values are encrypted at rest in git.
4. **On the machine**, `sops-nix` decrypts at activation into `/run/secrets/<name>`
   with the owner/mode you declared.

## The CI caveat (see the ADR)

On GitHub-hosted runners there is no per-machine key, so decrypting in CI needs an
`age` private key delivered as a single `SOPS_AGE_KEY` GitHub secret. That
**relocates** the root of trust to one bootstrap key — it does not remove the
GitHub secret. For "no stored secret", cloud/registry auth must use **OIDC**
instead (see the ADR).
