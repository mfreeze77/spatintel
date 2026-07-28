#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sip.desktop_review import LocalRequestDecision, ReviewProject, validate_local_request


class Handler(BaseHTTPRequestHandler):
    """Loopback-only review handler with authorization-before-response ordering."""

    project: ReviewProject
    csrf: str

    def _security_decision(self) -> LocalRequestDecision:
        cookie_header = self.headers.get("Cookie", "")
        csrf_cookie: str | None = None
        for item in cookie_header.split(";"):
            key, separator, value = item.strip().partition("=")
            if separator and key == "sip_csrf":
                csrf_cookie = value or None
                break
        return validate_local_request(
            bind_host=str(self.server.server_address[0]),
            host_header=self.headers.get("Host", ""),
            origin=self.headers.get("Origin"),
            method=self.command,
            content_type=self.headers.get("Content-Type"),
            csrf_header=self.headers.get("X-SIP-CSRF"),
            csrf_cookie=csrf_cookie,
        )

    def _send_json(self, *, status: int, payload: dict[str, Any], decision: LocalRequestDecision) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        # Exactly one status is emitted, and only after the policy decision exists.
        self.send_response(status)
        for key, value in decision.security_headers.items():
            self.send_header(key, value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler protocol name
        decision = self._security_decision()
        if not decision.allowed:
            self._send_json(
                status=403,
                payload={"error": {"code": decision.code, "message": "request denied by local review policy"}},
                decision=decision,
            )
            return
        if urlparse(self.path).path != "/api/project":
            self._send_json(
                status=404,
                payload={"error": {"code": "DESKTOP_ROUTE_NOT_FOUND", "message": "route not found"}},
                decision=decision,
            )
            return
        self._send_json(
            status=200,
            payload={"manifest": self.project.manifest, "integrity": self.project.verify_integrity()},
            decision=decision,
        )

    def log_message(self, format: str, *args: object) -> None:
        return


def create_server(
    project: ReviewProject,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    csrf: str = "local-session-only",
) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "::1"}:
        raise ValueError("desktop review server must bind to loopback")
    project_handler = type(
        "ProjectReviewHandler",
        (Handler,),
        {"project": project, "csrf": csrf},
    )
    server = ThreadingHTTPServer((host, port), project_handler)
    server.daemon_threads = True
    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "::1"])
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    project = ReviewProject.open(args.project)
    server = create_server(project, host=args.host, port=args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
