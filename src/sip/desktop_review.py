from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .canonical import canonical_json as canonical_json_bytes, canonical_sha256, new_uuid, sha256_bytes
from .errors import ConflictError, ValidationError

CORRESPONDENCE_TYPES = {"point", "line", "plane", "semantic", "image_to_scene"}
OBSERVATION_STREAMS = {"rgb", "depth", "trajectory", "geometry"}
ACTION_TYPES = {
    "observation.added", "correspondence.added", "correspondence.updated", "action.undone", "action.redone",
    "branch.created", "factor_residual.recorded", "loop_constraint.recorded", "source_weight.recorded",
    "regional_uncertainty.recorded", "merge.conflict", "merge.completed",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError("DESKTOP_BUNDLE_INVALID", f"cannot read local review bundle: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValidationError("DESKTOP_BUNDLE_INVALID", f"local review bundle record must be an object: {path.name}")
    return value


@dataclass(frozen=True)
class LocalRequestDecision:
    allowed: bool
    code: str
    security_headers: dict[str, str]


def validate_local_request(
    *,
    bind_host: str,
    host_header: str,
    origin: str | None,
    method: str,
    content_type: str | None,
    csrf_header: str | None,
    csrf_cookie: str | None,
) -> LocalRequestDecision:
    headers = {
        "Content-Security-Policy": "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Cache-Control": "no-store",
    }
    if bind_host not in {"127.0.0.1", "::1", "localhost"}:
        return LocalRequestDecision(False, "DESKTOP_LOOPBACK_BIND_REQUIRED", headers)
    allowed_hosts = {"127.0.0.1", "localhost", "[::1]"}
    hostname = host_header.rsplit(":", 1)[0] if not host_header.startswith("[") else host_header.split("]", 1)[0] + "]"
    if hostname not in allowed_hosts:
        return LocalRequestDecision(False, "DESKTOP_HOST_DENIED", headers)
    if origin and origin not in {"http://127.0.0.1", "http://localhost", "http://[::1]"} and not any(
        origin.startswith(prefix) for prefix in ("http://127.0.0.1:", "http://localhost:", "http://[::1]:")
    ):
        return LocalRequestDecision(False, "DESKTOP_ORIGIN_DENIED", headers)
    if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        if content_type is None or not content_type.lower().startswith("application/json"):
            return LocalRequestDecision(False, "DESKTOP_JSON_REQUIRED", headers)
        if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
            return LocalRequestDecision(False, "DESKTOP_CSRF_DENIED", headers)
    return LocalRequestDecision(True, "ALLOW", headers)


class ReviewProject:
    """Crash-safe local-first correspondence and optimization review bundle.

    Inputs are immutable, content-addressed copies. Actions form a hash chain and undo/redo
    append compensating records rather than rewriting history. Exports are proposals only;
    publication remains a server-side governed operation.
    """

    SCHEMA = "sip.desktop-review-project/v1.1"

    def __init__(self, root: Path, manifest: dict[str, Any]) -> None:
        self.root = root
        self.manifest = manifest

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        author_id: str,
        base_commit_id: str,
        input_files: Iterable[Path],
        purpose: str,
        classification: str,
        license_state: str,
    ) -> "ReviewProject":
        if not author_id or not base_commit_id or not purpose:
            raise ValidationError("DESKTOP_IDENTITY_REQUIRED", "author, base commit, and purpose are required")
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        if any(root.iterdir()):
            raise ConflictError("DESKTOP_PROJECT_EXISTS", "desktop review project directory is not empty")
        inputs_dir = root / "inputs"
        inputs_dir.mkdir()
        inputs: list[dict[str, Any]] = []
        for source in sorted((Path(item).resolve() for item in input_files), key=lambda item: str(item)):
            if not source.is_file():
                raise ValidationError("DESKTOP_INPUT_MISSING", f"review input is missing: {source}")
            payload = source.read_bytes()
            digest = sha256_bytes(payload)
            target = inputs_dir / digest
            if not target.exists():
                _write_atomic(target, payload)
                target.chmod(0o440)
            inputs.append({"source_name": source.name, "sha256": digest, "byte_count": len(payload), "relative_path": f"inputs/{digest}"})
        created_at = _now()
        manifest = {
            "schema": cls.SCHEMA,
            "schema_version": "1.1.0",
            "project_id": new_uuid(),
            "author_id": author_id,
            "base_commit_id": base_commit_id,
            "purpose": purpose,
            "classification": classification,
            "license_state": license_state,
            "inputs": inputs,
            "branches": {"main": None},
            "current_branch": "main",
            "head_action_hash": None,
            "action_count": 0,
            "created_at": created_at,
            "updated_at": created_at,
            "manifest_hash": "0" * 64,
        }
        manifest["manifest_hash"] = canonical_sha256({key: value for key, value in manifest.items() if key != "manifest_hash"})
        _write_atomic(root / "project.json", canonical_json_bytes(manifest) + b"\n")
        _write_atomic(root / "actions.jsonl", b"")
        _write_atomic(root / "snapshot.json", canonical_json_bytes({"schema": "sip.desktop-review-snapshot/v1", "state": {}, "head_action_hash": None}) + b"\n")
        return cls(root, manifest)

    @classmethod
    def open(cls, root: Path) -> "ReviewProject":
        root = root.resolve()
        manifest = _read_json(root / "project.json")
        if manifest.get("schema") != cls.SCHEMA:
            raise ValidationError("DESKTOP_SCHEMA_UNSUPPORTED", "desktop review project schema is unsupported")
        expected = canonical_sha256({key: value for key, value in manifest.items() if key != "manifest_hash"})
        if expected != manifest.get("manifest_hash"):
            raise ValidationError("DESKTOP_MANIFEST_TAMPERED", "desktop review manifest hash does not match")
        project = cls(root, manifest)
        project.verify_integrity()
        return project

    def verify_integrity(self) -> dict[str, Any]:
        for item in self.manifest.get("inputs", []):
            path = self.root / str(item["relative_path"])
            if not path.is_file() or path.stat().st_size != int(item["byte_count"]) or sha256_bytes(path.read_bytes()) != item["sha256"]:
                raise ValidationError("DESKTOP_INPUT_TAMPERED", f"immutable review input failed integrity: {item.get('source_name')}")
        previous: str | None = None
        count = 0
        for action in self.actions():
            if action.get("previous_action_hash") != previous:
                raise ValidationError("DESKTOP_ACTION_CHAIN_BROKEN", "desktop review action chain is discontinuous")
            expected = canonical_sha256({key: value for key, value in action.items() if key != "action_hash"})
            if action.get("action_hash") != expected:
                raise ValidationError("DESKTOP_ACTION_TAMPERED", "desktop review action hash does not match")
            previous = expected
            count += 1
        if previous != self.manifest.get("head_action_hash") or count != int(self.manifest.get("action_count", -1)):
            raise ValidationError("DESKTOP_HEAD_MISMATCH", "desktop review manifest head differs from action log")
        return {"status": "passed", "input_count": len(self.manifest.get("inputs", [])), "action_count": count, "head_action_hash": previous}

    def actions(self) -> list[dict[str, Any]]:
        path = self.root / "actions.jsonl"
        if not path.is_file():
            raise ValidationError("DESKTOP_ACTION_LOG_MISSING", "desktop review action log is missing")
        result: list[dict[str, Any]] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValidationError("DESKTOP_ACTION_LOG_INVALID", f"invalid action log line {line_number}") from exc
            if not isinstance(item, dict):
                raise ValidationError("DESKTOP_ACTION_LOG_INVALID", f"action log line {line_number} is not an object")
            result.append(item)
        return result

    def _append(self, action_type: str, payload: dict[str, Any], *, author_id: str) -> dict[str, Any]:
        if action_type not in ACTION_TYPES:
            raise ValidationError("DESKTOP_ACTION_TYPE_INVALID", f"unsupported desktop review action: {action_type}")
        action = {
            "schema": "sip.desktop-review-action/v1",
            "action_id": new_uuid(),
            "action_type": action_type,
            "author_id": author_id,
            "branch": self.manifest["current_branch"],
            "base_commit_id": self.manifest["base_commit_id"],
            "previous_action_hash": self.manifest.get("head_action_hash"),
            "payload": payload,
            "created_at": _now(),
            "action_hash": "0" * 64,
        }
        action["action_hash"] = canonical_sha256({key: value for key, value in action.items() if key != "action_hash"})
        log = self.root / "actions.jsonl"
        existing = log.read_bytes()
        _write_atomic(log, existing + canonical_json_bytes(action) + b"\n")
        self.manifest["head_action_hash"] = action["action_hash"]
        self.manifest["branches"][self.manifest["current_branch"]] = action["action_hash"]
        self.manifest["action_count"] = int(self.manifest["action_count"]) + 1
        self.manifest["updated_at"] = _now()
        self._persist_manifest()
        self._write_snapshot()
        return action

    def add_observation(self, *, stream: str, timestamp_ns: int, asset_sha256: str, coordinate_frame_id: str, metadata: dict[str, Any], author_id: str) -> dict[str, Any]:
        if stream not in OBSERVATION_STREAMS or timestamp_ns < 0 or len(asset_sha256) != 64:
            raise ValidationError("DESKTOP_OBSERVATION_INVALID", "observation stream, timestamp, or asset hash is invalid")
        return self._append("observation.added", {"stream": stream, "timestamp_ns": timestamp_ns, "asset_sha256": asset_sha256, "coordinate_frame_id": coordinate_frame_id, "metadata": metadata}, author_id=author_id)

    def add_correspondence(self, *, correspondence_type: str, source: dict[str, Any], target: dict[str, Any], uncertainty: dict[str, Any], author_id: str, correspondence_id: str | None = None) -> dict[str, Any]:
        if correspondence_type not in CORRESPONDENCE_TYPES or not source or not target or not uncertainty:
            raise ValidationError("DESKTOP_CORRESPONDENCE_INVALID", "correspondence requires a supported type, source, target, and uncertainty")
        identifier = correspondence_id or new_uuid()
        return self._append("correspondence.added", {"correspondence_id": identifier, "correspondence_type": correspondence_type, "source": source, "target": target, "uncertainty": uncertainty}, author_id=author_id)

    def update_correspondence(self, correspondence_id: str, *, patch: dict[str, Any], author_id: str) -> dict[str, Any]:
        if not patch:
            raise ValidationError("DESKTOP_CORRESPONDENCE_PATCH_EMPTY", "correspondence update cannot be empty")
        return self._append("correspondence.updated", {"correspondence_id": correspondence_id, "patch": patch}, author_id=author_id)

    def undo(self, target_action_hash: str, *, author_id: str, reason: str) -> dict[str, Any]:
        if target_action_hash not in {item["action_hash"] for item in self.actions()}:
            raise ValidationError("DESKTOP_UNDO_TARGET_UNKNOWN", "undo target is not in this project")
        return self._append("action.undone", {"target_action_hash": target_action_hash, "reason": reason}, author_id=author_id)

    def redo(self, target_action_hash: str, *, author_id: str, reason: str) -> dict[str, Any]:
        return self._append("action.redone", {"target_action_hash": target_action_hash, "reason": reason}, author_id=author_id)

    def create_branch(self, name: str, *, author_id: str, from_action_hash: str | None = None) -> dict[str, Any]:
        if not name or name in self.manifest["branches"]:
            raise ConflictError("DESKTOP_BRANCH_EXISTS", "desktop review branch already exists or is invalid")
        head = from_action_hash if from_action_hash is not None else self.manifest.get("head_action_hash")
        if head and head not in {item["action_hash"] for item in self.actions()}:
            raise ValidationError("DESKTOP_BRANCH_HEAD_UNKNOWN", "desktop review branch head is unknown")
        self.manifest["branches"][name] = head
        self.manifest["current_branch"] = name
        self.manifest["head_action_hash"] = head
        self._persist_manifest()
        return self._append("branch.created", {"name": name, "from_action_hash": head}, author_id=author_id)

    def record_factor_residual(self, *, factor_id: str, residual: float, units: str, threshold: float, author_id: str) -> dict[str, Any]:
        if residual < 0 or threshold <= 0:
            raise ValidationError("DESKTOP_RESIDUAL_INVALID", "factor residuals must be non-negative with positive thresholds")
        return self._append("factor_residual.recorded", {"factor_id": factor_id, "residual": residual, "units": units, "threshold": threshold, "accepted": residual <= threshold}, author_id=author_id)

    def record_loop_constraint(self, *, from_frame: str, to_frame: str, transform: list[list[float]], switch_weight: float, author_id: str) -> dict[str, Any]:
        if len(transform) != 4 or any(len(row) != 4 for row in transform) or not 0 <= switch_weight <= 1:
            raise ValidationError("DESKTOP_LOOP_CONSTRAINT_INVALID", "loop constraint requires a 4x4 transform and switch weight in [0,1]")
        return self._append("loop_constraint.recorded", {"from_frame": from_frame, "to_frame": to_frame, "transform": transform, "switch_weight": switch_weight}, author_id=author_id)

    def record_source_weight(self, *, source_id: str, weight: float, rationale: str, author_id: str) -> dict[str, Any]:
        if not 0 <= weight <= 1 or not rationale:
            raise ValidationError("DESKTOP_SOURCE_WEIGHT_INVALID", "source weight must be in [0,1] with rationale")
        return self._append("source_weight.recorded", {"source_id": source_id, "weight": weight, "rationale": rationale}, author_id=author_id)

    def record_regional_uncertainty(self, *, region: dict[str, Any], sigma_m: float, basis: str, author_id: str) -> dict[str, Any]:
        if not region or sigma_m < 0 or not basis:
            raise ValidationError("DESKTOP_UNCERTAINTY_INVALID", "regional uncertainty requires region, non-negative sigma, and basis")
        return self._append("regional_uncertainty.recorded", {"region": region, "sigma_m": sigma_m, "basis": basis}, author_id=author_id)

    def merge(self, other: "ReviewProject", *, author_id: str) -> dict[str, Any]:
        if self.manifest["base_commit_id"] != other.manifest["base_commit_id"]:
            raise ConflictError("DESKTOP_MERGE_BASE_MISMATCH", "offline review projects have different base commits")
        ours = self.actions(); theirs = other.actions(); known = {item["action_hash"] for item in ours}
        ours_by_correspondence = {item.get("payload", {}).get("correspondence_id"): item for item in ours if item["action_type"] in {"correspondence.added", "correspondence.updated"}}
        conflicts: list[dict[str, Any]] = []
        imported: list[str] = []
        for action in theirs:
            if action["action_hash"] in known:
                continue
            identifier = action.get("payload", {}).get("correspondence_id")
            ours_action = ours_by_correspondence.get(identifier)
            if identifier and ours_action and ours_action.get("payload") != action.get("payload"):
                conflict = {"correspondence_id": identifier, "ours_action_hash": ours_action["action_hash"], "theirs_action_hash": action["action_hash"], "state": "unresolved"}
                self._append("merge.conflict", conflict, author_id=author_id)
                conflicts.append(conflict)
            else:
                self._append(action["action_type"], {**action["payload"], "imported_action_hash": action["action_hash"], "imported_author_id": action["author_id"]}, author_id=author_id)
                imported.append(action["action_hash"])
        completed = self._append("merge.completed", {"other_project_id": other.manifest["project_id"], "imported_action_hashes": imported, "conflicts": conflicts}, author_id=author_id)
        return {"merge_action": completed, "imported_count": len(imported), "conflicts": conflicts}

    def export_proposal(self, output: Path, *, actor_id: str, policy: dict[str, Any]) -> dict[str, Any]:
        if policy.get("allowed") is not True:
            raise ValidationError("DESKTOP_EXPORT_POLICY_DENIED", "desktop review export is denied by policy")
        if self.manifest.get("license_state") != "approved" or policy.get("license_state") != "approved":
            raise ValidationError("DESKTOP_EXPORT_LICENSE_DENIED", "desktop review export requires approved license posture")
        if self.manifest.get("classification") not in set(policy.get("allowed_classifications", [])):
            raise ValidationError("DESKTOP_EXPORT_CLASSIFICATION_DENIED", "desktop review classification is not approved for export")
        if policy.get("authoritative_publish") is True:
            raise ValidationError("DESKTOP_AUTHORITATIVE_PUBLISH_DENIED", "desktop review exports are proposals and cannot directly publish authoritative state")
        integrity = self.verify_integrity()
        proposal = {
            "schema": "sip.desktop-review-proposal/v1",
            "project_id": self.manifest["project_id"],
            "base_commit_id": self.manifest["base_commit_id"],
            "author_id": self.manifest["author_id"],
            "exported_by": actor_id,
            "purpose": self.manifest["purpose"],
            "classification": self.manifest["classification"],
            "proposal_only": True,
            "requires_server_review": True,
            "input_hashes": sorted(item["sha256"] for item in self.manifest["inputs"]),
            "actions": self.actions(),
            "integrity": integrity,
            "exported_at": _now(),
            "proposal_hash": "0" * 64,
        }
        proposal["proposal_hash"] = canonical_sha256({key: value for key, value in proposal.items() if key != "proposal_hash"})
        _write_atomic(output, canonical_json_bytes(proposal) + b"\n")
        return proposal

    def acquire_lock(self, owner_id: str) -> Path:
        lock = self.root / ".review.lock"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ConflictError("DESKTOP_PROJECT_LOCKED", "desktop review project is already locked") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"owner_id": owner_id, "acquired_at": _now()}, handle, sort_keys=True)
            handle.flush(); os.fsync(handle.fileno())
        return lock

    def release_lock(self, owner_id: str) -> None:
        lock = self.root / ".review.lock"
        record = _read_json(lock)
        if record.get("owner_id") != owner_id:
            raise ConflictError("DESKTOP_LOCK_OWNER_MISMATCH", "only the lock owner can release the desktop review project")
        lock.unlink()

    def _persist_manifest(self) -> None:
        self.manifest["manifest_hash"] = "0" * 64
        self.manifest["manifest_hash"] = canonical_sha256({key: value for key, value in self.manifest.items() if key != "manifest_hash"})
        _write_atomic(self.root / "project.json", canonical_json_bytes(self.manifest) + b"\n")

    def _write_snapshot(self) -> None:
        state: dict[str, Any] = {"observations": [], "correspondences": {}, "diagnostics": [], "conflicts": [], "undone": [], "redone": []}
        for action in self.actions():
            kind = action["action_type"]; payload = action["payload"]
            if kind == "observation.added": state["observations"].append(payload)
            elif kind == "correspondence.added": state["correspondences"][payload["correspondence_id"]] = payload
            elif kind == "correspondence.updated" and payload["correspondence_id"] in state["correspondences"]: state["correspondences"][payload["correspondence_id"]].update(payload["patch"])
            elif kind in {"factor_residual.recorded", "loop_constraint.recorded", "source_weight.recorded", "regional_uncertainty.recorded"}: state["diagnostics"].append({"type": kind, **payload})
            elif kind == "merge.conflict": state["conflicts"].append(payload)
            elif kind == "action.undone": state["undone"].append(payload["target_action_hash"])
            elif kind == "action.redone": state["redone"].append(payload["target_action_hash"])
        snapshot = {"schema": "sip.desktop-review-snapshot/v1", "state": state, "head_action_hash": self.manifest.get("head_action_hash"), "snapshot_hash": "0" * 64}
        snapshot["snapshot_hash"] = canonical_sha256({key: value for key, value in snapshot.items() if key != "snapshot_hash"})
        _write_atomic(self.root / "snapshot.json", canonical_json_bytes(snapshot) + b"\n")


def copy_project(source: ReviewProject, destination: Path) -> ReviewProject:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source.root, destination)
    return ReviewProject.open(destination)
