from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError

# Raw authentication or biometric material may never be persisted in ordinary
# Construction JSON. Opaque references are permitted and are resolved only by
# a separately governed vault or restricted-asset subsystem.
_FORBIDDEN_EXACT_KEYS = {
    "password",
    "passwd",
    "passcode",
    "pin",
    "pin_code",
    "access_code",
    "controller_password",
    "programming_password",
    "control_password",
    "credential_secret",
    "client_secret",
    "api_secret",
    "api_token",
    "access_token",
    "refresh_token",
    "bearer_token",
    "private_key",
    "privatekey",
    "security_key",
    "biometric_template",
    "biometric_value",
    "face_embedding",
    "voice_embedding",
}
_FORBIDDEN_KEY_PARTS = (
    "password",
    "passcode",
    "private_key",
    "privatekey",
    "biometric_template",
    "credential_secret",
    "access_token",
    "refresh_token",
    "client_secret",
)
_REFERENCE_SUFFIXES = (
    "_vault_ref",
    "_asset_ref",
    "_secret_ref",
    "_credential_ref",
    "_key_ref",
    "_biometric_ref",
)
_REFERENCE_PATTERN = re.compile(r"^(?:vault|sip-asset)://[A-Za-z0-9][A-Za-z0-9._:/@+-]{2,509}$")


def is_opaque_restricted_reference_key(key: str) -> bool:
    normalized = key.strip().lower()
    return normalized.endswith(_REFERENCE_SUFFIXES)


def is_forbidden_secret_key(key: str) -> bool:
    normalized = key.strip().lower()
    if is_opaque_restricted_reference_key(normalized):
        return False
    return normalized in _FORBIDDEN_EXACT_KEYS or any(part in normalized for part in _FORBIDDEN_KEY_PARTS)


def validate_no_raw_restricted_values(value: Any, *, code_prefix: str = "CONSTRUCTION", path: str = "$") -> None:
    findings: list[str] = []
    invalid_refs: list[str] = []

    def walk(item: Any, current: str) -> None:
        if isinstance(item, Mapping):
            for raw_key, child in item.items():
                key = str(raw_key)
                child_path = f"{current}.{key}"
                if is_opaque_restricted_reference_key(key):
                    if not isinstance(child, str) or _REFERENCE_PATTERN.fullmatch(child.strip()) is None:
                        invalid_refs.append(child_path)
                    continue
                if is_forbidden_secret_key(key) and child not in (None, "", [], {}):
                    findings.append(child_path)
                    continue
                walk(child, child_path)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{current}[{index}]")

    walk(value, path)
    if findings:
        raise ValidationError(
            f"{code_prefix}_RAW_SECRET_PROHIBITED",
            "raw passwords, tokens, passcodes, private keys, credential secrets, and biometric values may not be stored; use an opaque vault or restricted-asset reference",
            {"paths": sorted(set(findings))},
        )
    if invalid_refs:
        raise ValidationError(
            f"{code_prefix}_RESTRICTED_REFERENCE_INVALID",
            "restricted references must use an opaque vault:// or sip-asset:// reference",
            {"paths": sorted(set(invalid_refs))},
        )


def strip_raw_restricted_values(value: Any, *, path: str = "$") -> tuple[Any, list[str]]:
    """Defense-in-depth scrub for legacy rows created before enforcement.

    The function never returns a raw secret value. Opaque references remain.
    """

    removed: list[str] = []

    def walk(item: Any, current: str) -> Any:
        if isinstance(item, Mapping):
            output: dict[str, Any] = {}
            for raw_key, child in item.items():
                key = str(raw_key)
                child_path = f"{current}.{key}"
                if is_forbidden_secret_key(key):
                    removed.append(child_path)
                    continue
                if is_opaque_restricted_reference_key(key):
                    if isinstance(child, str) and _REFERENCE_PATTERN.fullmatch(child.strip()):
                        output[key] = child.strip()
                    else:
                        removed.append(child_path)
                    continue
                output[key] = walk(child, child_path)
            return output
        if isinstance(item, list):
            return [walk(child, f"{current}[{index}]") for index, child in enumerate(item)]
        return item

    return walk(value, path), sorted(set(removed))
