#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from sip.desktop_review import ReviewProject, validate_local_request


class Handler(BaseHTTPRequestHandler):
    project: ReviewProject
    csrf: str

    def _security(self):
        decision = validate_local_request(
            bind_host=str(self.server.server_address[0]),
            host_header=self.headers.get("Host", ""),
            origin=self.headers.get("Origin"),
            method=self.command,
            content_type=self.headers.get("Content-Type"),
            csrf_header=self.headers.get("X-SIP-CSRF"),
            csrf_cookie=self.headers.get("Cookie", "").removeprefix("sip_csrf=") or None,
        )
        for key, value in decision.security_headers.items():
            self.send_header(key, value)
        return decision

    def do_GET(self):
        if urlparse(self.path).path != "/api/project": self.send_error(404); return
        self.send_response(200); decision = self._security()
        if not decision.allowed: self.send_error(403); return
        self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"manifest": self.project.manifest, "integrity": self.project.verify_integrity()}, sort_keys=True).encode())

    def log_message(self, format: str, *args):
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "::1"])
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    Handler.project = ReviewProject.open(args.project)
    Handler.csrf = "local-session-only"
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
