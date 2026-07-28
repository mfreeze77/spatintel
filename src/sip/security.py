from __future__ import annotations

import base64
import hmac
import json
import os
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .canonical import canonical_json
from .errors import AuthenticationError, ValidationError


@dataclass(frozen=True)
class EnvelopeCipher:
    master_key: bytes
    key_id: str

    def __post_init__(self) -> None:
        if len(self.master_key) != 32:
            raise ValueError("master key must be 32 bytes")

    def encrypt(self, plaintext: bytes, *, aad: bytes) -> tuple[bytes, dict[str, Any]]:
        data_key = AESGCM.generate_key(bit_length=256)
        content_nonce = os.urandom(12)
        ciphertext = AESGCM(data_key).encrypt(content_nonce, plaintext, aad)
        wrap_nonce = os.urandom(12)
        wrapped_key = AESGCM(self.master_key).encrypt(wrap_nonce, data_key, aad)
        return ciphertext, {
            "algorithm": "AES-256-GCM",
            "key_id": self.key_id,
            "content_nonce_b64": base64.b64encode(content_nonce).decode(),
            "wrap_nonce_b64": base64.b64encode(wrap_nonce).decode(),
            "wrapped_key_b64": base64.b64encode(wrapped_key).decode(),
            "aad_sha256": sha256(aad).hexdigest(),
        }

    def decrypt(self, ciphertext: bytes, metadata: dict[str, Any], *, aad: bytes) -> bytes:
        if metadata.get("algorithm") != "AES-256-GCM":
            raise ValidationError("ENCRYPTION_ALGORITHM_UNSUPPORTED", "unsupported object encryption algorithm")
        if metadata.get("aad_sha256") != sha256(aad).hexdigest():
            raise ValidationError("ENCRYPTION_AAD_MISMATCH", "encrypted object binding does not match")
        data_key = AESGCM(self.master_key).decrypt(
            base64.b64decode(metadata["wrap_nonce_b64"]),
            base64.b64decode(metadata["wrapped_key_b64"]),
            aad,
        )
        return AESGCM(data_key).decrypt(base64.b64decode(metadata["content_nonce_b64"]), ciphertext, aad)

    def rewrap(self, metadata: dict[str, Any], *, aad: bytes, new_cipher: "EnvelopeCipher") -> dict[str, Any]:
        data_key = AESGCM(self.master_key).decrypt(
            base64.b64decode(metadata["wrap_nonce_b64"]),
            base64.b64decode(metadata["wrapped_key_b64"]),
            aad,
        )
        wrap_nonce = os.urandom(12)
        wrapped_key = AESGCM(new_cipher.master_key).encrypt(wrap_nonce, data_key, aad)
        return {
            **metadata,
            "key_id": new_cipher.key_id,
            "wrap_nonce_b64": base64.b64encode(wrap_nonce).decode(),
            "wrapped_key_b64": base64.b64encode(wrapped_key).decode(),
        }


class SignedTokenCodec:
    """Small deterministic HMAC token used for local signed URLs and fixture auth.

    Production profiles replace this boundary with OIDC/JWT verification and managed keys.
    """

    def __init__(self, key: bytes, issuer: str = "sip-local") -> None:
        if len(key) < 32:
            raise ValueError("token signing key must be at least 32 bytes")
        self.key = key
        self.issuer = issuer

    def encode(self, claims: dict[str, Any], *, ttl_seconds: int) -> str:
        now = int(time.time())
        body = {**claims, "iss": self.issuer, "iat": now, "exp": now + ttl_seconds}
        payload = base64.urlsafe_b64encode(canonical_json(body)).rstrip(b"=")
        signature = hmac.new(self.key, payload, sha256).digest()
        return f"{payload.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"

    def decode(self, token: str) -> dict[str, Any]:
        try:
            payload_text, signature_text = token.split(".", 1)
            payload = payload_text.encode()
            padding = "=" * (-len(signature_text) % 4)
            signature = base64.urlsafe_b64decode(signature_text + padding)
            expected = hmac.new(self.key, payload, sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise AuthenticationError("TOKEN_SIGNATURE_INVALID", "token signature is invalid")
            body_padding = "=" * (-len(payload_text) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload_text + body_padding))
        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError("TOKEN_MALFORMED", "token is malformed") from exc
        if claims.get("iss") != self.issuer:
            raise AuthenticationError("TOKEN_ISSUER_INVALID", "token issuer is invalid")
        if int(claims.get("exp", 0)) < int(time.time()):
            raise AuthenticationError("TOKEN_EXPIRED", "token has expired")
        return claims
