from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "docker-compose.yml"
INSTALL_SCRIPT = ROOT / "scripts" / "install-howto-function.ps1"


class FunctionApiState:
    def __init__(self) -> None:
        self.function: dict | None = None
        self.create_count = 0
        self.update_count = 0
        self.toggle_count = 0
        self.authorization_headers: list[str | None] = []

    def response(self) -> dict:
        assert self.function is not None
        return {
            **self.function,
            "user_id": "admin-1",
            "meta": self.function.get("meta", {}),
            "type": "pipe",
            "is_global": False,
            "updated_at": 1,
            "created_at": 1,
        }


def make_handler(state: FunctionApiState):
    class Handler(BaseHTTPRequestHandler):
        def _record_authorization(self) -> None:
            state.authorization_headers.append(self.headers.get("Authorization"))

        def do_GET(self) -> None:  # noqa: N802
            self._record_authorization()
            if self.path == "/api/v1/functions/list":
                payload = [] if state.function is None else [state.response()]
                self._send(payload)
                return
            if self.path == "/api/v1/functions/id/open_webui_guide":
                if state.function is None:
                    self._send({"detail": "not found"}, status=HTTPStatus.UNAUTHORIZED)
                else:
                    self._send(state.response())
                return
            self._send({"detail": "not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            self._record_authorization()
            body = self._read_json()
            if self.path == "/api/v1/functions/create":
                state.create_count += 1
                state.function = {**body, "is_active": False}
                self._send(state.response())
                return
            if self.path == "/api/v1/functions/id/open_webui_guide/update":
                state.update_count += 1
                active = bool(state.function and state.function["is_active"])
                state.function = {**body, "is_active": active}
                self._send(state.response())
                return
            if self.path == "/api/v1/functions/id/open_webui_guide/toggle":
                state.toggle_count += 1
                assert state.function is not None
                state.function["is_active"] = not state.function["is_active"]
                self._send(state.response())
                return
            self._send({"detail": "not found"}, status=HTTPStatus.NOT_FOUND)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(length) or b"{}")

        def _send(self, payload, *, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


class MockFunctionApi:
    def __init__(self) -> None:
        self.state = FunctionApiState()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(self.state),
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __enter__(self) -> MockFunctionApi:
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class ComposeInstallationTests(unittest.TestCase):
    def test_open_webui_mounts_guide_sources_read_only(self) -> None:
        compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
        service = compose["services"]["open-webui"]

        self.assertIn("./agent:/opt/howto/agent:ro", service["volumes"])
        self.assertIn("./knowledge:/opt/howto/knowledge:ro", service["volumes"])
        self.assertIn("./openwebui:/opt/howto/openwebui:ro", service["volumes"])

    def test_open_webui_configures_the_guide_import_boundary(self) -> None:
        compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
        environment = compose["services"]["open-webui"]["environment"]

        self.assertEqual(environment["ENABLE_PLUGINS"], "true")
        self.assertEqual(environment["ENABLE_API_KEYS"], "true")
        self.assertEqual(environment["HOWTO_CONTENT_ROOT"], "/opt/howto")
        self.assertEqual(
            environment["PYTHONPATH"],
            "/opt/howto/agent/src:/opt/howto",
        )
        self.assertEqual(
            environment["ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS"],
            "false",
        )


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required")
class FunctionInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pwsh = shutil.which("pwsh")
        assert cls.pwsh is not None

    def test_creates_enables_and_then_makes_no_changes(self) -> None:
        with TemporaryDirectory() as directory, MockFunctionApi() as api:
            source = Path(directory) / "guide.py"
            source.write_text("class Pipe:\n    pass\n", encoding="utf-8")

            first = self._run(api.base_url, source)
            second = self._run(api.base_url, source)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(api.state.create_count, 1)
        self.assertEqual(api.state.update_count, 0)
        self.assertEqual(api.state.toggle_count, 1)
        assert api.state.function is not None
        self.assertTrue(api.state.function["is_active"])
        self.assertTrue(api.state.authorization_headers)
        self.assertEqual(
            set(api.state.authorization_headers),
            {"Bearer test-admin-api-key"},
        )

    def test_requires_an_administrator_api_key(self) -> None:
        environment = os.environ.copy()
        environment.pop("OPEN_WEBUI_API_KEY", None)

        result = subprocess.run(
            [
                self.pwsh,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(INSTALL_SCRIPT),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env=environment,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("administrator API key is required", result.stderr)

    def test_refuses_source_replacement_without_explicit_update(self) -> None:
        with TemporaryDirectory() as directory, MockFunctionApi() as api:
            source = Path(directory) / "guide.py"
            source.write_text("class Pipe:\n    version = 1\n", encoding="utf-8")
            created = self._run(api.base_url, source)
            source.write_text("class Pipe:\n    version = 2\n", encoding="utf-8")

            refused = self._run(api.base_url, source)
            updated = self._run(api.base_url, source, "-Update")

        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Re-run with -Update", refused.stderr)
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(api.state.create_count, 1)
        self.assertEqual(api.state.update_count, 1)
        self.assertEqual(api.state.toggle_count, 1)

    def test_can_create_without_enabling(self) -> None:
        with TemporaryDirectory() as directory, MockFunctionApi() as api:
            source = Path(directory) / "guide.py"
            source.write_text("class Pipe:\n    pass\n", encoding="utf-8")

            result = self._run(api.base_url, source, "-NoEnable")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(api.state.create_count, 1)
        self.assertEqual(api.state.toggle_count, 0)
        assert api.state.function is not None
        self.assertFalse(api.state.function["is_active"])

    def _run(self, base_url: str, source: Path, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                self.pwsh,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(INSTALL_SCRIPT),
                "-BaseUrl",
                base_url,
                "-SourcePath",
                str(source),
                "-ApiKey",
                "test-admin-api-key",
                *extra,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
