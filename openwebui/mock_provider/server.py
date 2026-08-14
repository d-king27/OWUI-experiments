"""Tiny OpenAI-compatible provider for validating the local chat UI."""

from __future__ import annotations

import json
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

MODEL_ID = "hello-world"
RESPONSE_TEXT = "Hello, world! The baseline chat connection is working."


class MockProviderHandler(BaseHTTPRequestHandler):
    """Serve the minimum API surface Open WebUI needs for a chat."""

    server_version = "HowToAgentMockProvider/1.0"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlsplit(self.path).path

        if path == "/health":
            self._send_json({"status": True})
            return

        if path == "/v1/models":
            self._send_json(
                {
                    "object": "list",
                    "data": [
                        {
                            "id": MODEL_ID,
                            "object": "model",
                            "created": 0,
                            "owned_by": "local-baseline",
                        }
                    ],
                }
            )
            return

        if path == f"/v1/models/{MODEL_ID}":
            self._send_json(
                {
                    "id": MODEL_ID,
                    "object": "model",
                    "created": 0,
                    "owned_by": "local-baseline",
                }
            )
            return

        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlsplit(self.path).path
        if path != "/v1/chat/completions":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(content_length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(
                {"error": "request body must be valid JSON"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if request.get("stream", False):
            self._send_stream()
            return

        created = int(time.time())
        self._send_json(
            {
                "id": "chatcmpl-hello-world",
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": RESPONSE_TEXT,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
        )

    def do_OPTIONS(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_stream(self) -> None:
        created = int(time.time())
        chunks = [
            {
                "id": "chatcmpl-hello-world",
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": RESPONSE_TEXT,
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-hello-world",
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ],
            },
        ]

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        for chunk in chunks:
            payload = json.dumps(chunk, separators=(",", ":"))
            self.wfile.write(f"data: {payload}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _send_json(
        self,
        payload: dict[str, Any],
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), MockProviderHandler)
    print(f"Hello provider listening on port {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
