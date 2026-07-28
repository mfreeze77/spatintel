from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path


def _decode_key(name: str, fallback: bytes | None, *, required: bool) -> bytes:
    raw = os.getenv(name)
    if not raw:
        if required or fallback is None:
            raise ValueError(f"{name} is required")
        return fallback
    try:
        value = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError(f"{name} must be valid base64") from exc
    if len(value) != 32:
        raise ValueError(f"{name} must decode to exactly 32 bytes")
    return value


def _optional(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    object_store_backend: str
    object_store_root: Path
    multipart_root: Path
    s3_bucket: str | None
    s3_prefix: str
    s3_region: str | None
    s3_endpoint_url: str | None
    s3_kms_key_id: str | None
    master_key: bytes
    master_key_id: str
    signing_key: bytes
    allow_development_auth: bool
    max_api_body_bytes: int = 67_108_864

    def __post_init__(self) -> None:
        if self.environment not in {"development", "test", "staging", "production"}:
            raise ValueError("SIP_ENV must be development, test, staging, or production")
        if self.object_store_backend not in {"local", "s3"}:
            raise ValueError("SIP_OBJECT_STORE_BACKEND must be local or s3")
        if self.object_store_backend == "s3" and not self.s3_bucket:
            raise ValueError("SIP_S3_BUCKET is required for the s3 object-store backend")
        if self.environment == "production" and self.allow_development_auth:
            raise ValueError("development authentication cannot be enabled in production")
        if self.environment == "production" and self.master_key_id.startswith("development"):
            raise ValueError("a development encryption key identifier cannot be used in production")
        if self.max_api_body_bytes <= 0:
            raise ValueError("SIP_MAX_API_BODY_BYTES must be positive")

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("SIP_ENV", "development")
        production = environment == "production"
        return cls(
            environment=environment,
            database_url=os.getenv("SIP_DATABASE_URL", "sqlite:///runtime/sip.sqlite3"),
            object_store_backend=os.getenv("SIP_OBJECT_STORE_BACKEND", "local"),
            object_store_root=Path(os.getenv("SIP_OBJECT_STORE_ROOT", "runtime/objects")),
            multipart_root=Path(os.getenv("SIP_MULTIPART_ROOT", "runtime/multipart")),
            s3_bucket=_optional("SIP_S3_BUCKET"),
            s3_prefix=os.getenv("SIP_S3_PREFIX", "sip"),
            s3_region=_optional("SIP_S3_REGION"),
            s3_endpoint_url=_optional("SIP_S3_ENDPOINT_URL"),
            s3_kms_key_id=_optional("SIP_S3_KMS_KEY_ID"),
            master_key=_decode_key("SIP_MASTER_KEY_B64", b"d" * 32, required=production),
            master_key_id=os.getenv("SIP_MASTER_KEY_ID", "development-only-v1"),
            signing_key=_decode_key("SIP_SIGNING_KEY_B64", b"s" * 32, required=production),
            allow_development_auth=os.getenv("SIP_ALLOW_DEVELOPMENT_AUTH", "false").lower() == "true",
            max_api_body_bytes=int(os.getenv("SIP_MAX_API_BODY_BYTES", "67108864")),
        )
