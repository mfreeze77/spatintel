from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy.orm import Session

from .database import AssetRefRow, AssetRow
from .errors import ValidationError

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def require_scoped_immutable_assets(
    session: Session,
    *,
    tenant_id: str,
    project_id: str,
    asset_ids: Iterable[str],
    expected_hashes: Mapping[str, str] | None = None,
    code_prefix: str = "EVIDENCE",
    require_nonempty: bool = False,
) -> list[AssetRefRow]:
    """Resolve evidence to live immutable CAS references in one tenant/project.

    The function intentionally returns no partial result. A missing, blank,
    tombstoned, cross-scope, hash-mismatched, or object-metadata-broken reference
    fails the entire controlled operation.
    """

    normalized: list[str] = []
    for raw in asset_ids:
        asset_id = str(raw or "").strip()
        if not asset_id:
            raise ValidationError(
                f"{code_prefix}_ASSET_ID_REQUIRED",
                "evidence asset identifiers must be non-empty",
            )
        if asset_id not in normalized:
            normalized.append(asset_id)
    if require_nonempty and not normalized:
        raise ValidationError(
            f"{code_prefix}_ASSET_REQUIRED",
            "at least one immutable evidence asset is required",
        )

    resolved: list[AssetRefRow] = []
    hashes = dict(expected_hashes or {})
    unknown_hash_keys = sorted(set(hashes) - set(normalized))
    if unknown_hash_keys:
        raise ValidationError(
            f"{code_prefix}_HASH_REFERENCE_INVALID",
            "expected evidence hashes may refer only to supplied asset identifiers",
            {"asset_ids": unknown_hash_keys},
        )

    for asset_id in normalized:
        ref = session.get(AssetRefRow, asset_id)
        if (
            ref is None
            or ref.tenant_id != tenant_id
            or ref.project_id != project_id
            or ref.tombstoned_at is not None
        ):
            raise ValidationError(
                f"{code_prefix}_ASSET_SCOPE",
                "evidence asset is missing, tombstoned, or outside the tenant/project scope",
                {"asset_id": asset_id},
            )
        if _SHA256.fullmatch(str(ref.sha256 or "")) is None:
            raise ValidationError(
                f"{code_prefix}_ASSET_HASH_INVALID",
                "evidence asset does not retain a valid SHA-256 content identity",
                {"asset_id": asset_id},
            )
        if session.get(AssetRow, ref.sha256) is None:
            raise ValidationError(
                f"{code_prefix}_ASSET_OBJECT_MISSING",
                "evidence asset points to missing immutable object metadata",
                {"asset_id": asset_id, "sha256": ref.sha256},
            )
        expected = hashes.get(asset_id)
        if expected is not None:
            expected = expected.removeprefix("sha256:").lower()
            if _SHA256.fullmatch(expected) is None or expected != ref.sha256:
                raise ValidationError(
                    f"{code_prefix}_ASSET_HASH_MISMATCH",
                    "evidence asset hash does not match the retained immutable content identity",
                    {"asset_id": asset_id, "expected_sha256": expected, "actual_sha256": ref.sha256},
                )
        resolved.append(ref)
    return resolved


def evidence_ids_and_hashes(items: Iterable[Mapping[str, Any]], *, code_prefix: str) -> tuple[list[str], dict[str, str]]:
    """Extract governed asset identifiers from evidence envelopes.

    Every evidence envelope must identify an immutable asset. Optional sha256
    fields are checked by :func:`require_scoped_immutable_assets`.
    """

    asset_ids: list[str] = []
    hashes: dict[str, str] = {}
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValidationError(
                f"{code_prefix}_ITEM_INVALID",
                "evidence entries must be objects",
                {"index": index},
            )
        asset_id = str(item.get("asset_id") or "").strip()
        if not asset_id:
            raise ValidationError(
                f"{code_prefix}_ASSET_ID_REQUIRED",
                "every evidence entry must identify an immutable asset",
                {"index": index},
            )
        asset_ids.append(asset_id)
        supplied_hash = item.get("sha256")
        if supplied_hash is not None:
            digest = str(supplied_hash).removeprefix("sha256:").lower()
            prior = hashes.get(asset_id)
            if prior is not None and prior != digest:
                raise ValidationError(
                    f"{code_prefix}_HASH_CONFLICT",
                    "one evidence asset cannot be submitted with conflicting hashes",
                    {"asset_id": asset_id},
                )
            hashes[asset_id] = digest
    return asset_ids, hashes
