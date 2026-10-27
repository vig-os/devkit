"""Tests for the pure helpers of gh-app-provision (no network, no Apps)."""

import io
import json
import logging
import socket
import subprocess
import sys
import types
import unittest
import urllib.request
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

import pytest
from vig_utils import gh_app_provision as mod


class SecretNames(unittest.TestCase):
    def test_names(self):
        self.assertEqual(
            mod.credential_slot_names("RP_APP"),
            {
                "client_id": "RP_APP_CLIENT_ID",
                "id": "RP_APP_ID",
                "private_key": "RP_APP_PRIVATE_KEY",
            },
        )

    def test_custom_prefix(self):
        self.assertEqual(
            mod.credential_slot_names("COMMIT_APP")["client_id"], "COMMIT_APP_CLIENT_ID"
        )


class WiringSnippet(unittest.TestCase):
    def test_client_id_not_deprecated_app_id(self):
        snippet = mod.wiring_snippet("RP_APP")
        self.assertIn("client-id: ${{ secrets.RP_APP_CLIENT_ID }}", snippet)
        self.assertNotIn("app-id:", snippet)

    def test_private_key_and_current_action_major(self):
        snippet = mod.wiring_snippet("RP_APP")
        self.assertIn("private-key: ${{ secrets.RP_APP_PRIVATE_KEY }}", snippet)
        self.assertIn(f"uses: {mod.ACTION_REF}", snippet)
        self.assertRegex(mod.ACTION_REF, r"^actions/create-github-app-token@v\d+$")

    def test_missing_client_id_is_flagged_in_the_snippet(self):
        snippet = mod.wiring_snippet("RP_APP", client_id_stored=False)
        self.assertIn("RP_APP_CLIENT_ID was NOT set", snippet)
        self.assertIn("client-id: ${{ secrets.RP_APP_CLIENT_ID }}", snippet)
        self.assertNotIn("NOT set", mod.wiring_snippet("RP_APP"))


class Callback(unittest.TestCase):
    """The conversion callback, with the network and gh stubbed out."""

    def run_callback(self, conv):
        args = types.SimpleNamespace(
            owner_type="user", owner="o", repo="o/r", slot_prefix="RP_APP"
        )
        p = mod.Provisioner(args)
        set_names = []
        with (
            mock.patch.object(mod, "exchange_code", return_value=conv),
            mock.patch.object(
                mod,
                "set_secret",
                side_effect=lambda repo, name, value: set_names.append(name),
            ),
            redirect_stderr(io.StringIO()) as err,
        ):
            status, page = p.handle_callback({"state": [p.state], "code": ["c"]})
        return status, page, set_names, p.result, err.getvalue()

    BASE = {
        "id": 42,
        "pem": "PEM",
        "slug": "s",
        "html_url": "https://github.com/apps/s",
    }

    def test_with_client_id_all_three_are_stored(self):
        status, page, names, result, err = self.run_callback(
            {**self.BASE, "client_id": "Iv1.x"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            sorted(names), ["RP_APP_CLIENT_ID", "RP_APP_ID", "RP_APP_PRIVATE_KEY"]
        )
        self.assertNotIn("Not set", page)
        self.assertEqual(err, "")

    def test_without_client_id_warns_and_never_claims_it(self):
        status, page, names, result, err = self.run_callback(dict(self.BASE))
        self.assertEqual(status, 200)
        self.assertEqual(sorted(names), ["RP_APP_ID", "RP_APP_PRIVATE_KEY"])
        self.assertNotIn("RP_APP_CLIENT_ID", result["stored"])
        self.assertIn("Not set:</b> RP_APP_CLIENT_ID", page)
        self.assertIn("WARNING", err)

    def test_success_page_escapes_credential_slot_names(self):
        args = types.SimpleNamespace(
            owner_type="user", owner="o", repo="o/r", slot_prefix="<b>X"
        )
        p = mod.Provisioner(args)
        with (
            mock.patch.object(mod, "exchange_code", return_value=dict(self.BASE)),
            mock.patch.object(mod, "set_secret"),
            redirect_stderr(io.StringIO()),
        ):
            _, page = p.handle_callback({"state": [p.state], "code": ["c"]})
        self.assertNotIn("<b>X", page)
        self.assertIn("&lt;b&gt;X_CLIENT_ID", page)


@pytest.fixture
def args():
    return types.SimpleNamespace(
        name="example-bot",
        owner="example",
        owner_type="org",
        repo="example/repo",
        perms="contents=write,issues=read",
        slot_prefix="BOT",
        public=False,
        host="127.0.0.1",
        port=0,
        base_url=None,
        pem_out=None,
        no_secrets=False,
        timeout=1,
    )


@pytest.fixture
def conversion():
    return {
        "id": 42,
        "client_id": "Iv1.example",
        "slug": "example-bot",
        "html_url": "https://github.com/apps/example-bot",
        "pem": "sensitive-private-key",
        "client_secret": "sensitive-client-secret",
        "webhook_secret": "sensitive-webhook-secret",
    }


def test_manifest_from_flags(args):
    provisioner = mod.Provisioner(args)
    assert provisioner.manifest("https://proxy.example/session") == {
        "name": "example-bot",
        "url": "https://github.com/example/repo",
        "redirect_url": "https://proxy.example/session/callback",
        "setup_url": "https://proxy.example/session/installed",
        "setup_on_update": True,
        "public": False,
        "default_permissions": {
            "contents": "write",
            "issues": "read",
            "metadata": "read",
        },
        "default_events": [],
    }
    assert (
        provisioner.new_app_url
        == "https://github.com/organizations/example/settings/apps/new"
    )
    args.public = True
    assert mod.Provisioner(args).manifest("http://localhost")["public"] is True
    assert mod.parse_perms("contents, issues=write, ,") == {
        "contents": "read",
        "issues": "write",
        "metadata": "read",
    }


@pytest.mark.parametrize("extra", [[], ["--base-url", "https://proxy.example/prefix/"]])
def test_dry_run_has_no_external_effects(monkeypatch, capsys, tmp_path, extra):
    pem_path = tmp_path / "key.pem"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gh-app-provision",
            "--name",
            "example-bot",
            "--owner",
            "example",
            "--repo",
            "example/repo",
            "--perms",
            "checks=write",
            "--public",
            "--pem-out",
            str(pem_path),
            "--dry-run",
            *extra,
        ],
    )
    with (
        mock.patch.object(mod.http.server, "ThreadingHTTPServer") as server,
        mock.patch.object(mod.subprocess, "run") as run,
        mock.patch.object(mod.subprocess, "check_output") as check_output,
        mock.patch.object(urllib.request, "urlopen") as urlopen,
        mock.patch.object(socket, "socket") as network_socket,
    ):
        assert mod.main() == 0
    for operation in (server, run, check_output, urlopen, network_socket):
        operation.assert_not_called()
    captured = capsys.readouterr()
    manifest = json.loads(captured.out)
    assert captured.err == ""
    assert manifest["name"] == "example-bot"
    assert manifest["public"] is True
    assert manifest["default_permissions"] == {"checks": "write", "metadata": "read"}
    expected = "https://proxy.example/prefix/" if extra else "http://127.0.0.1:0/"
    assert manifest["redirect_url"].startswith(expected)
    assert manifest["redirect_url"].endswith("/callback")
    assert manifest["setup_url"].endswith("/installed")
    assert not pem_path.exists()


def test_private_file_mode_and_exclusive_creation(tmp_path):
    path = tmp_path / "keys" / "app.pem"
    mod.write_private(str(path), "private-value")
    assert path.read_text() == "private-value"
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    with pytest.raises(FileExistsError):
        mod.write_private(str(path), "replacement")
    assert path.read_text() == "private-value"
    link = tmp_path / "link.pem"
    link.symlink_to(path)
    with pytest.raises(FileExistsError):
        mod.write_private(str(link), "replacement")


def test_callback_persists_pem_before_secrets(args, conversion, tmp_path):
    args.pem_out = str(tmp_path / "key.pem")
    provisioner = mod.Provisioner(args)

    def fail_secret(*_):
        assert Path(args.pem_out).read_text() == conversion["pem"]
        raise subprocess.CalledProcessError(1, ["gh", "secret", "set"])

    with (
        mock.patch.object(mod, "exchange_code", return_value=conversion),
        mock.patch.object(mod, "set_secret", side_effect=fail_secret),
    ):
        status, _ = provisioner.handle_callback(
            {"state": [provisioner.state], "code": ["code"]}
        )
    assert status == 500
    assert provisioner.code_done.is_set()


def test_no_secrets_never_sets_gh_secrets(args, conversion, tmp_path, capsys):
    args.no_secrets = True
    args.pem_out = str(tmp_path / "key.pem")
    provisioner = mod.Provisioner(args)
    with (
        mock.patch.object(mod, "exchange_code", return_value=conversion) as exchange,
        mock.patch.object(mod.subprocess, "run") as run,
    ):
        status, _ = provisioner.handle_callback(
            {"state": [provisioner.state], "code": ["code"]}
        )
    assert status == 200
    exchange.assert_called_once_with("code")
    run.assert_not_called()
    assert Path(args.pem_out).read_text() == conversion["pem"]
    assert "BOT_CLIENT_ID" not in provisioner.result["stored"]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("query", [{"state": ["wrong"], "code": ["code"]}, {}])
def test_invalid_callback_never_exchanges_code(args, query):
    provisioner = mod.Provisioner(args)
    with mock.patch.object(mod, "exchange_code") as exchange:
        assert provisioner.handle_callback(query)[0] == 400
    exchange.assert_not_called()
    assert provisioner.code_done.is_set()


def test_missing_code_never_exchanges(args):
    provisioner = mod.Provisioner(args)
    with mock.patch.object(mod, "exchange_code") as exchange:
        assert provisioner.handle_callback({"state": [provisioner.state]})[0] == 400
    exchange.assert_not_called()


def test_base_url_binds_loopback_and_preserves_proxy_prefix(args):
    args.base_url = "https://proxy.example/provision/"
    args.host = "192.0.2.1"
    provisioner = mod.Provisioner(args)
    with (
        mock.patch.object(mod.http.server, "ThreadingHTTPServer") as server,
        mock.patch.object(mod.threading, "Thread"),
    ):
        server.return_value.server_address = ("127.0.0.1", 8123)
        provisioner.serve()
    assert server.call_args.args[0] == ("127.0.0.1", 0)
    base = f"https://proxy.example/provision/{provisioner.path}"
    assert provisioner.base() == base
    assert provisioner.manifest(base)["redirect_url"] == f"{base}/callback"
    assert provisioner.manifest(base)["setup_url"] == f"{base}/installed"


@pytest.mark.parametrize("host", ["127.0.0.1", "192.0.2.1"])
def test_server_binds_and_advertises_only_chosen_address(args, host):
    args.host = host
    provisioner = mod.Provisioner(args)
    with (
        mock.patch.object(mod.http.server, "ThreadingHTTPServer") as server,
        mock.patch.object(mod.threading, "Thread"),
    ):
        server.return_value.server_address = (host, 8123)
        provisioner.serve()
    assert server.call_args.args[0] == (host, 0)
    assert server.call_args.args[0][0] not in ("0.0.0.0", "::", "")
    assert provisioner.base() == f"http://{host}:8123/{provisioner.path}"


def test_default_host_is_loopback():
    args = mod.argument_parser().parse_args(
        [
            "--name",
            "example-bot",
            "--owner",
            "example",
            "--repo",
            "example/repo",
        ]
    )
    assert args.host == "127.0.0.1"


@pytest.mark.parametrize("host", ["0.0.0.0", "::"])
def test_wildcard_host_is_rejected(host):
    with pytest.raises(SystemExit) as error:
        mod.argument_parser().parse_args(
            [
                "--name",
                "example-bot",
                "--owner",
                "example",
                "--repo",
                "example/repo",
                "--host",
                host,
            ]
        )
    assert error.value.code == 2


@pytest.mark.parametrize("failure", [None, "exchange", "secret"])
def test_server_callback_never_exposes_secrets(
    args, conversion, failure, capfd, caplog
):
    code = "sensitive-manifest-code"
    leaked = " ".join(
        [
            code,
            conversion["pem"],
            conversion["client_secret"],
            conversion["webhook_secret"],
        ]
    )
    provisioner = mod.Provisioner(args)
    with (
        mock.patch.object(mod, "exchange_code", return_value=conversion) as exchange,
        mock.patch.object(mod, "set_secret") as store,
        caplog.at_level(logging.DEBUG),
    ):
        if failure == "exchange":
            exchange.side_effect = RuntimeError(leaked)
        elif failure == "secret":
            store.side_effect = subprocess.CalledProcessError(
                1, ["gh", leaked], output=leaked, stderr=leaked
            )
        provisioner.serve()
        try:
            url = f"http://127.0.0.1:{provisioner.port}/{provisioner.path}/callback?state={provisioner.state}&code={code}"
            try:
                response = urllib.request.urlopen(url, timeout=5)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                page = response.read().decode()
                assert response.status == (500 if failure else 200)
            assert provisioner.code_done.is_set()
            output = capfd.readouterr()
            for secret in (
                code,
                conversion["pem"],
                conversion["client_secret"],
                conversion["webhook_secret"],
            ):
                assert secret not in output.out + output.err + caplog.text + page + (
                    provisioner.error or ""
                )
        finally:
            provisioner.httpd.shutdown()
            provisioner.httpd.server_close()


def test_set_secret_only_passes_value_on_stdin():
    with mock.patch.object(mod.subprocess, "run") as run:
        mod.set_secret("example/repo", "BOT_PRIVATE_KEY", "private-value")
    assert run.call_args.args == (
        ["gh", "secret", "set", "BOT_PRIVATE_KEY", "--repo", "example/repo"],
    )
    assert run.call_args.kwargs["input"] == "private-value"
    assert run.call_args.kwargs["capture_output"] is True
    assert run.call_args.kwargs["check"] is True


@pytest.mark.parametrize("outcome", ["timeout", "error", "success", "interrupt"])
def test_run_always_closes_server(args, outcome, capsys):
    provisioner = mod.Provisioner(args)
    provisioner.httpd = mock.Mock()
    provisioner.port = 8123
    provisioner.result = {
        "app_id": 42,
        "slug": "example-bot",
        "html_url": "https://github.com/apps/example-bot",
        "stored": ["BOT_CLIENT_ID", "BOT_ID", "BOT_PRIVATE_KEY"],
    }
    provisioner.code_done = mock.Mock()
    provisioner.code_done.wait.return_value = outcome != "timeout"
    provisioner.installed = mock.Mock()
    provisioner.installed.wait.return_value = True
    if outcome == "error":
        provisioner.error = "conversion failed"
    if outcome == "interrupt":
        provisioner.code_done.wait.side_effect = KeyboardInterrupt
    with mock.patch.object(provisioner, "serve"):
        if outcome == "interrupt":
            with pytest.raises(KeyboardInterrupt):
                provisioner.run()
        else:
            assert (
                provisioner.run() == {"timeout": 2, "error": 1, "success": 0}[outcome]
            )
    provisioner.httpd.shutdown.assert_called_once()
    provisioner.httpd.server_close.assert_called_once()
    if outcome == "success":
        assert "client-id: ${{ secrets.BOT_CLIENT_ID }}" in capsys.readouterr().out


def test_console_script_dry_run():
    result = subprocess.run(
        [
            "gh-app-provision",
            "--name",
            "example-bot",
            "--owner",
            "example",
            "--repo",
            "example/repo",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["name"] == "example-bot"
    assert result.stderr == ""


def test_existing_pem_aborts_before_secret_writes(args, conversion, tmp_path):
    path = tmp_path / "key.pem"
    path.write_text("original")
    args.pem_out = str(path)
    provisioner = mod.Provisioner(args)
    with (
        mock.patch.object(mod, "exchange_code", return_value=conversion),
        mock.patch.object(mod, "set_secret") as store,
    ):
        assert (
            provisioner.handle_callback(
                {"state": [provisioner.state], "code": ["code"]}
            )[0]
            == 500
        )
    store.assert_not_called()
    assert path.read_text() == "original"


def test_exchange_code_posts_to_manifest_conversion(conversion, capsys):
    response = subprocess.CompletedProcess(
        [], 0, stdout=json.dumps(conversion), stderr=""
    )
    with (
        mock.patch.object(mod.subprocess, "run", return_value=response) as run,
        mock.patch.object(
            urllib.request,
            "urlopen",
            side_effect=AssertionError("unexpected network call"),
        ),
    ):
        assert mod.exchange_code("example-code") == conversion
    assert run.call_args.args == (
        ["gh", "api", "-X", "POST", "/app-manifests/example-code/conversions"],
    )
    assert run.call_args.kwargs["capture_output"] is True
    assert run.call_args.kwargs["text"] is True
    assert run.call_args.kwargs["check"] is True
    assert run.call_args.kwargs["timeout"] == 30
    output = capsys.readouterr()
    assert output.out == output.err == ""


@pytest.mark.parametrize("replay", ["valid", "wrong-state", "missing-code"])
def test_callback_replay_preserves_success(args, conversion, replay):
    args.no_secrets = True
    provisioner = mod.Provisioner(args)
    query = {"state": [provisioner.state], "code": ["code"]}
    response = subprocess.CompletedProcess([], 0, stdout=json.dumps(conversion))
    with mock.patch.object(mod.subprocess, "run", return_value=response) as run:
        assert provisioner.handle_callback(query)[0] == 200
        result = provisioner.result.copy()
        later = {
            "valid": query,
            "wrong-state": {},
            "missing-code": {"state": [provisioner.state]},
        }[replay]
        assert provisioner.handle_callback(later) == (
            200,
            "<h2>Callback already accepted.</h2>",
        )
    run.assert_called_once()
    assert provisioner.result == result
    assert provisioner.error is None


def test_concurrent_callback_cannot_repeat_exchange(args, conversion):
    args.no_secrets = True
    provisioner = mod.Provisioner(args)
    query = {"state": [provisioner.state], "code": ["code"]}
    entered = mod.threading.Event()
    release = mod.threading.Event()

    def exchange(_):
        entered.set()
        assert release.wait(5)
        return conversion

    with mock.patch.object(mod, "exchange_code", side_effect=exchange) as exchange_mock:
        worker = mod.threading.Thread(target=provisioner.handle_callback, args=(query,))
        worker.start()
        try:
            assert entered.wait(5)
            assert provisioner.handle_callback(query) == (
                200,
                "<h2>Callback already accepted.</h2>",
            )
            assert not provisioner.code_done.is_set()
        finally:
            release.set()
            worker.join(5)
        assert not worker.is_alive()
    exchange_mock.assert_called_once_with("code")
    assert provisioner.code_done.is_set()
    assert provisioner.error is None


@pytest.mark.parametrize("failure", ["timeout", "json"])
def test_exchange_failure_is_sanitized(args, conversion, failure, capsys):
    provisioner = mod.Provisioner(args)
    provisioner.port = 8123
    secret = json.dumps(conversion)
    response = subprocess.CompletedProcess([], 0, stdout=secret + "invalid")
    with mock.patch.object(mod.subprocess, "run", return_value=response) as run:
        if failure == "timeout":
            run.side_effect = subprocess.TimeoutExpired(
                ["gh", "sensitive-code"], 30, output=secret, stderr=secret
            )
        status, page = provisioner.handle_callback(
            {"state": [provisioner.state], "code": ["sensitive-code"]}
        )
        assert provisioner.wait_for_provisioning() == 1
    expected = "conversion or credential storage failed; check connectivity and output permissions"
    assert status == 500
    assert provisioner.error == expected
    assert expected in page
    output = capsys.readouterr()
    assert output.err == f"ERROR: {expected}\n"
    for value in ["sensitive-code", *conversion.values()]:
        if isinstance(value, str):
            assert value not in output.out + output.err + page
    run.assert_called_once()


@pytest.mark.parametrize(
    "url", ["proxy.example", "ftp://proxy.example", "https://", "http:///path"]
)
def test_invalid_base_url_is_rejected(url, capsys):
    with pytest.raises(SystemExit) as error:
        mod.argument_parser().parse_args(
            [
                "--name",
                "bot",
                "--owner",
                "example",
                "--repo",
                "example/repo",
                "--base-url",
                url,
            ]
        )
    assert error.value.code == 2
    assert "--base-url must be an HTTP(S) URL with a host" in capsys.readouterr().err


def test_host_and_base_url_are_mutually_exclusive(capsys):
    with pytest.raises(SystemExit) as error:
        mod.argument_parser().parse_args(
            [
                "--name",
                "bot",
                "--owner",
                "example",
                "--repo",
                "example/repo",
                "--host",
                "127.0.0.1",
                "--base-url",
                "https://proxy.example",
            ]
        )
    assert error.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


@pytest.mark.parametrize("failure", [False, True])
def test_org_secrets_selected_repos(args, conversion, capsys, failure):
    args.org_secret = True
    args.repos = "repo,other"
    provisioner = mod.Provisioner(args)
    provisioner.port = 8123
    provisioner.installed.set()
    with (
        mock.patch.object(mod, "exchange_code", return_value=conversion),
        mock.patch.object(mod.subprocess, "run") as run,
    ):
        if failure:
            run.side_effect = subprocess.CalledProcessError(
                1, ["gh"], output=conversion["pem"], stderr=conversion["pem"]
            )
        status, page = provisioner.handle_callback(
            {"state": [provisioner.state], "code": ["code"]}
        )
        assert status == (500 if failure else 200)
        assert provisioner.wait_for_provisioning() == (1 if failure else 0)
    expected = [
        mock.call(
            [
                "gh",
                "secret",
                "set",
                name,
                "--org",
                "example",
                "--visibility",
                "selected",
                "--repos",
                "repo,other",
            ],
            input=value,
            text=True,
            check=True,
            capture_output=True,
        )
        for name, value in [
            ("BOT_ID", "42"),
            ("BOT_PRIVATE_KEY", conversion["pem"]),
            ("BOT_CLIENT_ID", conversion["client_id"]),
        ]
    ]
    assert run.call_args_list == (expected[:1] if failure else expected)
    output = capsys.readouterr()
    for key in ("pem", "client_secret", "webhook_secret", "client_id"):
        assert conversion[key] not in output.out + output.err + page
    if not failure:
        assert "secrets set on organization example" in output.out


@pytest.mark.parametrize(
    "extra",
    [
        ["--owner-type", "user", "--repos", "repo"],
        [],
        ["--repos", ""],
        ["--repos", " , "],
        ["--repos", "repo", "--no-secrets"],
    ],
)
def test_invalid_org_secret_options(extra, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gh-app-provision",
            "--name",
            "bot",
            "--owner",
            "example",
            "--repo",
            "example/repo",
            "--dry-run",
            "--org-secret",
            *extra,
        ],
    )
    with pytest.raises(SystemExit) as error:
        mod.main()
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert "--org-secret" in message
    assert "unrecognized arguments" not in message


@pytest.mark.parametrize("rejection", ["state", "code", "exchange"])
def test_callback_after_rejection_shows_terminal_state(args, rejection):
    provisioner = mod.Provisioner(args)
    query = {"state": [provisioner.state], "code": ["code"]}
    first = {**query}
    if rejection == "state":
        first["state"] = ["wrong"]
    elif rejection == "code":
        del first["code"]
    with mock.patch.object(mod, "exchange_code", side_effect=RuntimeError) as exchange:
        assert provisioner.handle_callback(first)[0] == (
            500 if rejection == "exchange" else 400
        )
        error = provisioner.error
        assert provisioner.handle_callback(query) == (
            200,
            "<h2>This provisioning run has ended.</h2>",
        )
    assert exchange.call_count == (1 if rejection == "exchange" else 0)
    assert provisioner.error == error
    assert provisioner.result == {}


@pytest.mark.parametrize("repos", ["a,b", " a , b "])
def test_cli_normalizes_repos_before_secret_writes(monkeypatch, conversion, repos):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gh-app-provision",
            "--name",
            "bot",
            "--owner",
            "example",
            "--repo",
            "example/a",
            "--org-secret",
            "--repos",
            repos,
        ],
    )

    def provision(provisioner):
        provisioner.store_credentials(conversion)
        return 0

    with (
        mock.patch.object(mod.Provisioner, "run", provision),
        mock.patch.object(mod.subprocess, "run") as run,
    ):
        assert mod.main() == 0
    assert len(run.call_args_list) == 3
    for call in run.call_args_list:
        assert call.args[0][-2:] == ["--repos", "a,b"]


@pytest.mark.parametrize("repos", ["a,b", ""])
def test_repos_requires_org_secret(monkeypatch, capsys, repos):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gh-app-provision",
            "--name",
            "bot",
            "--owner",
            "example",
            "--repo",
            "example/a",
            "--repos",
            repos,
            "--dry-run",
        ],
    )
    with pytest.raises(SystemExit) as error:
        mod.main()
    assert error.value.code == 2
    assert "--repos requires --org-secret" in capsys.readouterr().err
