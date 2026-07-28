#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import os
import secrets
from pathlib import Path


def write_once(path: Path, value: str) -> None:
    if path.exists():
        return
    path.write_text(value + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate local-only SIP Compose secrets")
    parser.add_argument("--output", type=Path, default=Path("infrastructure/compose/secrets"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_once(args.output / "postgres_password.txt", secrets.token_urlsafe(32))
    write_once(args.output / "minio_root_user.txt", "sip-local-admin")
    write_once(args.output / "minio_root_password.txt", secrets.token_urlsafe(40))
    write_once(args.output / "valkey_password.txt", secrets.token_urlsafe(32))
    write_once(args.output / "master_key_b64.txt", base64.b64encode(secrets.token_bytes(32)).decode())
    write_once(args.output / "signing_key_b64.txt", base64.b64encode(secrets.token_bytes(32)).decode())
    write_once(args.output / "grafana_admin_password.txt", secrets.token_urlsafe(40))
    print(f"Generated or retained local secrets in {args.output}")


if __name__ == "__main__":
    main()
