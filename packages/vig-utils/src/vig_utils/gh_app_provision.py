#!/usr/bin/env python3
"""gh-app-provision — create a GitHub App from a manifest, then capture its
credentials into secrets and print the workflow wiring snippet.

GitHub has **no API to create an App** — creation is deliberately gated behind a
human browser action (the manifest flow). This tool automates everything around
that one unavoidable click:

  * builds the App manifest from flags
  * serves a one-shot auto-submitting form on an EPHEMERAL free port + a random
    URL path — so any number of concurrent sessions can run it without colliding
  * manifest ``redirect_url`` -> local ``/callback``: auto-captures the ``?code``,
    exchanges it for the App client id + App id + private key (PEM), and stores
    them as secrets (the PEM is piped straight into ``gh secret set`` — never
    printed or logged)
  * manifest ``setup_url`` -> local ``/installed``: auto-detects the Install click
  * waits up to ``--timeout`` for creation, then up to 300 seconds for Install;
    closes the server on success, failure, timeout or interruption

The only steps a human must do (GitHub security — no tool escapes them) are
clicking **Create GitHub App** and **Install**. The tool prints one URL to open
and blocks until both are done, then prints the ``create-github-app-token``
snippet for whatever workflow will consume the App.

Example:
    gh-app-provision \
        --name my-release-bot --owner my-org --owner-type org \
        --repo my-org/my-repo --perms contents=write,pull_requests=write \
        --secret-prefix RP_APP

Stdlib only. Requires an authenticated ``gh`` on PATH for code exchange and
secret writes. --org-secret --repos a,b stores organization secrets with selected
repository visibility instead (requires --owner-type org, excludes --no-secrets).
The default binds and advertises 127.0.0.1. A browser on
another machine cannot reach that listener: choose an explicit IPv4 --host
on a reachable LAN/VPN interface, or --base-url for a reverse proxy. --host
binds exactly the chosen address; wildcard listeners are rejected and there
is no address autodetection. With --base-url it binds loopback; configure it to
forward to a fixed --port and strip any base URL path prefix. Proxy access logs
must omit query strings, which contain the single-use conversion code.
--base-url requires an HTTP(S) URL with a host and is mutually exclusive with
--host. After a failed callback, later requests return HTTP 200 "This provisioning
run has ended". Otherwise later callbacks return "Callback already accepted", including
while the first callback is running, without exchanging again or changing state.

--pem-out writes an exclusive 0600 recovery key before secret writes. Existing
files are never replaced. Secret writes are sequential, so failure may leave
some secrets set; without --pem-out a failed conversion/storage attempt may
require regenerating the key in GitHub settings. --no-secrets skips repo secret
writes (the gh API exchange still runs); without --pem-out the returned private
key is discarded. No credentials are printed. Errors omit upstream details because they can contain secrets.
Dry-run previews use 127.0.0.1:0 unless overridden, and start no server.
Exit codes: 0 success/preview, 1 provisioning/startup failure, 2 timeout or
invalid CLI usage, 130 interrupted.
"""

from __future__ import annotations

import argparse
import http.server
import ipaddress
import json
import os
import secrets
import subprocess
import sys
import threading
from functools import partial
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

ACTION_REF = "actions/create-github-app-token@v3"


def listener_address(value: str) -> str:
    """Accept an explicit IPv4 listener address, never a wildcard."""
    try:
        address = ipaddress.IPv4Address(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--host must be an IPv4 address") from error
    if address.is_unspecified:
        raise argparse.ArgumentTypeError("--host must not be a wildcard address")
    return str(address)


def proxy_base_url(value: str) -> str:
    """Require an HTTP(S) scheme and host for the reverse proxy."""
    message = "--base-url must be an HTTP(S) URL with a host"
    try:
        parsed = urlparse(value)
        valid = parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except ValueError as error:
        raise argparse.ArgumentTypeError(message) from error
    if not valid:
        raise argparse.ArgumentTypeError(message)
    return value


def parse_perms(spec: str) -> dict[str, str]:
    perms: dict[str, str] = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        k, _, v = pair.partition("=")
        perms[k.strip()] = v.strip() or "read"
    perms.setdefault("metadata", "read")  # mandatory
    return perms


def exchange_code(code: str) -> dict:
    """Convert the single-use manifest code via gh, capturing all secret output."""
    response = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"/app-manifests/{quote(code, safe='')}/conversions",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(response.stdout)


def credential_slot_names(prefix: str) -> dict[str, str]:
    """Return public Actions slot names, never credential values.

    These labels identify where the client id, numeric App id and PEM are stored.
    """
    return {
        "client_id": f"{prefix}_CLIENT_ID",
        "id": f"{prefix}_ID",
        "private_key": f"{prefix}_PRIVATE_KEY",
    }


def wiring_snippet(prefix: str, client_id_stored: bool = True) -> str:
    """The create-github-app-token step for the consuming workflow. When the
    client id was not stored, the snippet says so instead of silently pointing
    at an unset secret (the step would get an empty ``client-id``)."""
    names = credential_slot_names(prefix)
    warn = (
        ""
        if client_id_stored
        else (
            f"      # !! {names['client_id']} was NOT set by gh-app-provision: set it (or set it\n"
            "      # !! to the numeric App id, which GitHub accepts as the JWT iss) before using this step.\n"
        )
    )
    return (
        warn
        + f"""      - uses: {ACTION_REF}
        id: app-token
        with:
          client-id: ${{{{ secrets.{names["client_id"]} }}}}
          private-key: ${{{{ secrets.{names["private_key"]} }}}}
      # then reference:  token: ${{{{ steps.app-token.outputs.token }}}}"""
    )


def set_secret(
    repo: str, name: str, value: str, *, org_repos: str | None = None
) -> None:
    """Write an Actions secret via gh, passing the value on stdin so it never
    appears in argv / process listings / logs."""
    target = (
        ["--org", repo, "--visibility", "selected", "--repos", org_repos]
        if org_repos is not None
        else ["--repo", repo]
    )
    subprocess.run(
        ["gh", "secret", "set", name, *target],
        input=value,
        text=True,
        check=True,
        capture_output=True,
    )


def write_private(path: str, value: str) -> None:
    """Write value to path with mode 0600 (dir 0700), never via a world-readable temp."""
    Path(path).resolve().parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(value)


class Provisioner:
    def __init__(self, args):
        self.args = args
        self.state = secrets.token_urlsafe(16)
        self.path = secrets.token_urlsafe(8)
        self.result: dict = {}
        self.error: str | None = None
        self.code_done = threading.Event()
        self._callback_lock = threading.Lock()
        self._callback_started = False
        self.installed = threading.Event()
        if args.owner_type == "org":
            self.new_app_url = (
                f"https://github.com/organizations/{args.owner}/settings/apps/new"
            )
        else:
            self.new_app_url = "https://github.com/settings/apps/new"

    def manifest(self, base: str) -> dict:
        return {
            "name": self.args.name,
            "url": f"https://github.com/{self.args.repo}",
            "redirect_url": f"{base}/callback",
            "setup_url": f"{base}/installed",
            "setup_on_update": True,
            "public": self.args.public,
            "default_permissions": parse_perms(self.args.perms),
            "default_events": [],
        }

    def form_html(self, base: str) -> str:
        mjson = escape(json.dumps(self.manifest(base)), quote=True)
        return f"""<!doctype html><meta charset=utf-8><title>Create {escape(self.args.name)}</title>
<body style="font-family:system-ui;max-width:40em;margin:4em auto">
<h2>Creating GitHub App "{escape(self.args.name)}"…</h2>
<p>Submitting a pre-filled manifest to GitHub. If nothing happens, click below.</p>
<form id=f action="{escape(self.new_app_url)}?state={self.state}" method=post>
  <input type=hidden name=manifest value="{mjson}">
  <button style="font-size:1.1em;padding:.6em 1.2em">Create GitHub App →</button>
</form><script>document.getElementById('f').submit()</script></body>"""

    def store_credentials(self, conversion: dict) -> list[str]:
        """Save the optional recovery key before attempting secret writes."""
        if getattr(self.args, "pem_out", None):
            write_private(self.args.pem_out, conversion["pem"])
        if getattr(self.args, "no_secrets", False):
            return []
        names = credential_slot_names(self.args.slot_prefix)
        store = (
            partial(set_secret, self.args.owner, org_repos=self.args.repos)
            if getattr(self.args, "org_secret", False)
            else partial(set_secret, self.args.repo)
        )
        store(names["id"], str(conversion["id"]))
        store(names["private_key"], conversion["pem"])
        stored = [names["id"], names["private_key"]]
        if conversion.get("client_id"):
            store(names["client_id"], str(conversion["client_id"]))
            stored.insert(0, names["client_id"])
        else:
            print(
                f"WARNING: the conversion returned no client_id; {names['client_id']} "
                "was NOT set. Set it manually to the numeric App id before use.",
                file=sys.stderr,
            )
        return stored

    def handle_callback(self, qs: dict) -> tuple[int, str]:
        """Claim the callback once; later requests get a fixed HTTP 200 page."""
        with self._callback_lock:
            if self.code_done.is_set() and self.error:
                return 200, "<h2>This provisioning run has ended.</h2>"
            if self._callback_started or self.code_done.is_set():
                return 200, "<h2>Callback already accepted.</h2>"
            self._callback_started = True
        if qs.get("state", [""])[0] != self.state:
            self.error = "state mismatch (possible CSRF) — aborting"
            self.code_done.set()
            return 400, "<h2>State mismatch — aborted.</h2>"
        code = qs.get("code", [""])[0]
        if not code:
            self.error = "no code in callback"
            self.code_done.set()
            return 400, "<h2>No code returned.</h2>"
        try:
            conversion = exchange_code(code)
            stored = self.store_credentials(conversion)
            self.result = {
                "app_id": conversion["id"],
                "slug": conversion["slug"],
                "html_url": conversion["html_url"],
                "stored": stored,
            }
        except subprocess.CalledProcessError:
            self.error = (
                "gh API or secret write failed; check gh authentication and repo access"
            )
        except FileExistsError:
            self.error = "PEM output already exists; refusing to overwrite it"
        except Exception:  # Conversion/IO errors can contain codes or secret values.
            self.error = "conversion or credential storage failed; check connectivity and output permissions"
        self.code_done.set()
        if self.error:
            return 500, f"<h2>Failed:</h2><pre>{escape(self.error)}</pre>"
        return 200, self.success_html()

    def success_html(self) -> str:
        install = f"{self.result['html_url']}/installations/new"
        if getattr(self.args, "no_secrets", False):
            summary = "App created; repository secrets were not written (--no-secrets)."
            warning = ""
        else:
            summary = f"App created — secrets set: {', '.join(self.result['stored'])}."
            missing = [
                name
                for name in credential_slot_names(self.args.slot_prefix).values()
                if name not in self.result["stored"]
            ]
            warning = (
                f"<p><b>Not set:</b> {escape(', '.join(missing))} — "
                "see the terminal for how to set it.</p>"
                if missing
                else ""
            )
        return (
            "<body style='font-family:system-ui;max-width:40em;margin:4em auto'>"
            f"<h2>{escape(summary)}</h2>{warning}"
            f"<p><b>Now install it:</b> <a href='{escape(install)}'>{escape(install)}</a></p>"
            "<p>Pick the repo, click Install — then you can close this tab.</p></body>"
        )

    def serve(self):
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def _send(self, code, body):
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body.encode())

            def do_GET(self):
                u = urlparse(self.path)
                base = outer.base()
                if u.path == f"/{outer.path}" or u.path == f"/{outer.path}/":
                    self._send(200, outer.form_html(base))
                elif u.path == f"/{outer.path}/callback":
                    code, body = outer.handle_callback(parse_qs(u.query))
                    self._send(code, body)
                elif u.path == f"/{outer.path}/installed":
                    outer.installed.set()
                    self._send(200, "<h2>Installed ✓ — you can close this tab.</h2>")
                else:
                    self._send(404, "<h2>404</h2>")

        bind = "127.0.0.1" if getattr(self.args, "base_url", None) else self.args.host
        self.httpd = http.server.ThreadingHTTPServer((bind, self.args.port), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def base(self) -> str:
        if getattr(self.args, "base_url", None):
            return f"{self.args.base_url.rstrip('/')}/{self.path}"
        return f"http://{self.args.host}:{self.port}/{self.path}"

    def run(self) -> int:
        self.serve()
        try:
            return self.wait_for_provisioning()
        finally:
            self.httpd.shutdown()
            self.httpd.server_close()

    def wait_for_provisioning(self) -> int:
        print("Open this in your browser, click Create GitHub App, then Install:\n")
        print(f"    {self.base()}/\n")
        print(f"(serving on port {self.port}; creation timeout {self.args.timeout}s)")
        sys.stdout.flush()
        if not self.code_done.wait(timeout=self.args.timeout):
            print("TIMEOUT: no App created within the window.", file=sys.stderr)
            return 2
        if self.error:
            print(f"ERROR: {self.error}", file=sys.stderr)
            return 1
        result = self.result
        print("\n=== App created ===")
        print(f"app_id={result['app_id']}  slug={result['slug']}")
        if getattr(self.args, "no_secrets", False):
            print("Repository secrets were not written (--no-secrets).")
        else:
            target = (
                f"organization {self.args.owner} (selected repos: {self.args.repos})"
                if getattr(self.args, "org_secret", False)
                else self.args.repo
            )
            print(f"secrets set on {target}: {', '.join(result['stored'])}")
        print(f"install: {result['html_url']}/installations/new")
        if self.installed.wait(timeout=min(self.args.timeout, 300)):
            print("install: confirmed ✓")
        else:
            print("install: not yet confirmed — finish it at the URL above.")
        print("\n=== Wiring snippet (paste into the consuming workflow) ===")
        print(
            wiring_snippet(
                self.args.slot_prefix,
                credential_slot_names(self.args.slot_prefix)["client_id"]
                in result["stored"],
            )
        )
        return 0


def argument_parser() -> argparse.ArgumentParser:
    """Build the manifest and credential options."""
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--name", required=True, help="GitHub App name (globally unique)")
    ap.add_argument(
        "--owner", required=True, help="org (or user) that will own the App"
    )
    ap.add_argument("--owner-type", choices=["org", "user"], default="org")
    ap.add_argument(
        "--repo",
        required=True,
        help="OWNER/REPO for the manifest URL and default secret destination",
    )
    ap.add_argument(
        "--perms",
        default="contents=write,pull_requests=write",
        help="comma list, e.g. contents=write,pull_requests=write",
    )
    ap.add_argument(
        "--public", action="store_true", help="make the App public (default private)"
    )
    add_secret_arguments(ap)
    add_server_arguments(ap)
    return ap


def add_secret_arguments(ap: argparse.ArgumentParser) -> None:
    """Add credential destination and recovery options."""
    ap.add_argument(
        "--secret-prefix",
        dest="slot_prefix",
        default="RP_APP",
        help="secrets become <prefix>_CLIENT_ID / <prefix>_ID / <prefix>_PRIVATE_KEY",
    )
    ap.add_argument(
        "--pem-out",
        default=None,
        help="also write the App private key to this path (0600, must not exist)",
    )
    storage = ap.add_mutually_exclusive_group()
    storage.add_argument(
        "--org-secret",
        action="store_true",
        help="write organization secrets with selected-repo visibility (requires --owner-type org and --repos)",
    )
    ap.add_argument(
        "--repos", help="comma-separated repositories allowed to read org secrets"
    )
    storage.add_argument(
        "--no-secrets",
        action="store_true",
        help="do not write repo secrets (use with --pem-out)",
    )


def add_server_arguments(ap: argparse.ArgumentParser) -> None:
    """Add listener, proxy and preview options."""
    binding = ap.add_mutually_exclusive_group()
    binding.add_argument(
        "--host",
        default="127.0.0.1",
        type=listener_address,
        help="IPv4 address to bind and advertise (default: 127.0.0.1); for a remote browser choose a reachable LAN/VPN address or use --base-url; wildcards are rejected",
    )
    ap.add_argument(
        "--port",
        type=int,
        default=0,
        help="bind port (default 0 = ephemeral free port)",
    )
    binding.add_argument(
        "--base-url",
        default=None,
        type=proxy_base_url,
        help="public HTTP(S) base URL of a reverse proxy in front of --port; binds 127.0.0.1; use a fixed --port for proxy configuration",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="creation wait in seconds (default 900), then up to min(timeout, 300) for installation",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print manifest JSON without network, server or gh calls; default preview host is 127.0.0.1 and port is 0",
    )


def main() -> int:
    parser = argument_parser()
    args = parser.parse_args()
    if args.org_secret and (
        args.owner_type != "org"
        or not args.repos
        or not all(repo.strip() for repo in args.repos.split(","))
    ):
        parser.error("--org-secret requires --owner-type org and non-empty --repos")
    if args.dry_run:
        provisioner = Provisioner(args)
        provisioner.port = args.port
        print(json.dumps(provisioner.manifest(provisioner.base()), indent=2))
        return 0
    try:
        return Provisioner(args).run()
    except OSError:
        print(
            "ERROR: unable to start the callback server; check --host and --port",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
