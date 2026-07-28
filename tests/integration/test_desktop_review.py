from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import threading

import pytest

from sip.desktop_review import ReviewProject, copy_project, validate_local_request
from sip.errors import ConflictError, ValidationError


def _project(tmp_path: Path, name: str = "review") -> ReviewProject:
    source = tmp_path / f"{name}-rgb.bin"; source.write_bytes(b"deterministic rgb-depth fixture")
    return ReviewProject.create(tmp_path / name, author_id="reviewer-a", base_commit_id="commit-base", input_files=[source], purpose="construction", classification="internal", license_state="approved")


def test_desktop_project_is_local_first_and_content_addressed(tmp_path: Path) -> None:
    """REQ: PLTDESK-001 local review opens immutable content-addressed inputs with stable provenance."""
    project = _project(tmp_path)
    assert project.manifest["author_id"] == "reviewer-a"
    assert project.manifest["base_commit_id"] == "commit-base"
    assert len(project.manifest["inputs"][0]["sha256"]) == 64
    assert (project.root / project.manifest["inputs"][0]["relative_path"]).stat().st_mode & 0o222 == 0


def test_desktop_observations_synchronize_rgb_depth_trajectory_and_geometry(tmp_path: Path) -> None:
    """REQ: PLTDESK-001 synchronized observations retain time, frame, and immutable asset identity."""
    project = _project(tmp_path)
    for index, stream in enumerate(("rgb", "depth", "trajectory", "geometry")):
        project.add_observation(stream=stream, timestamp_ns=1000 + index, asset_sha256=str(index) * 64, coordinate_frame_id="frame-room", metadata={"index": index}, author_id="reviewer-a")
    snapshot = json.loads((project.root / "snapshot.json").read_text())
    assert [item["stream"] for item in snapshot["state"]["observations"]] == ["rgb", "depth", "trajectory", "geometry"]


def test_desktop_supports_all_correspondence_types(tmp_path: Path) -> None:
    """REQ: PLTDESK-001 point, line, plane, semantic, and image-to-scene correspondence tools are durable."""
    project = _project(tmp_path)
    for kind in ("point", "line", "plane", "semantic", "image_to_scene"):
        project.add_correspondence(correspondence_type=kind, source={"id": f"source-{kind}"}, target={"id": f"target-{kind}"}, uncertainty={"sigma_m": 0.01}, author_id="reviewer-a")
    snapshot = json.loads((project.root / "snapshot.json").read_text())
    assert {item["correspondence_type"] for item in snapshot["state"]["correspondences"].values()} == {"point", "line", "plane", "semantic", "image_to_scene"}


def test_desktop_undo_and_redo_append_history_instead_of_rewriting(tmp_path: Path) -> None:
    """REQ: PLTDESK-001 undo/redo retain provenance and do not delete prior actions."""
    project = _project(tmp_path)
    action = project.add_correspondence(correspondence_type="point", source={"p": [0, 0]}, target={"p": [0, 0, 0]}, uncertainty={"sigma_m": 0.01}, author_id="a")
    project.undo(action["action_hash"], author_id="a", reason="controlled correction")
    project.redo(action["action_hash"], author_id="a", reason="review restored")
    assert [item["action_type"] for item in project.actions()] == ["correspondence.added", "action.undone", "action.redone"]


def test_desktop_branch_history_preserves_base_commit_identity(tmp_path: Path) -> None:
    """REQ: PLTDESK-003 offline branches retain author and base-commit identity."""
    project = _project(tmp_path)
    project.add_correspondence(correspondence_type="semantic", source={"label": "door"}, target={"entity_id": "door-1"}, uncertainty={"confidence": 0.9}, author_id="a")
    branch = project.create_branch("alternate", author_id="a")
    assert branch["base_commit_id"] == "commit-base"
    assert project.manifest["current_branch"] == "alternate"


def test_desktop_records_factor_residuals_and_loop_constraints(tmp_path: Path) -> None:
    """REQ: PLTDESK-002 review exposes factor residuals and robust loop constraints."""
    project = _project(tmp_path)
    residual = project.record_factor_residual(factor_id="factor-1", residual=0.02, units="meter", threshold=0.05, author_id="a")
    loop = project.record_loop_constraint(from_frame="f1", to_frame="f2", transform=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]], switch_weight=0.8, author_id="a")
    assert residual["payload"]["accepted"] is True
    assert loop["payload"]["switch_weight"] == 0.8


def test_desktop_records_source_weights_and_regional_uncertainty(tmp_path: Path) -> None:
    """REQ: PLTDESK-002 review exposes source weights and region uncertainty without hiding limitations."""
    project = _project(tmp_path)
    project.record_source_weight(source_id="lidar", weight=0.9, rationale="field observation", author_id="a")
    project.record_regional_uncertainty(region={"room_id": "101"}, sigma_m=0.04, basis="depth confidence", author_id="a")
    diagnostics = json.loads((project.root / "snapshot.json").read_text())["state"]["diagnostics"]
    assert {item["type"] for item in diagnostics} == {"source_weight.recorded", "regional_uncertainty.recorded"}


def test_desktop_authorized_local_project_requires_no_cloud_login(tmp_path: Path) -> None:
    """REQ: PLTDESK-004 authorized local-only projects open and operate without a cloud identity or login token."""
    project = _project(tmp_path)
    assert "cloud" not in project.manifest
    assert "token" not in repr(project.manifest).lower()
    reopened = ReviewProject.open(project.root)
    action = reopened.add_observation(
        stream="rgb",
        timestamp_ns=42,
        asset_sha256="f" * 64,
        coordinate_frame_id="local-frame",
        metadata={"mode": "offline"},
        author_id="local-reviewer",
    )
    assert action["author_id"] == "local-reviewer"
    assert reopened.verify_integrity()["status"] == "passed"


def test_desktop_atomic_bundle_detects_input_tampering(tmp_path: Path) -> None:
    """REQ: PLTDESK-005 crash-safe bundles fail closed on immutable-input tampering."""
    project = _project(tmp_path)
    path = project.root / project.manifest["inputs"][0]["relative_path"]
    path.chmod(0o640); path.write_bytes(b"tampered")
    with pytest.raises(ValidationError) as exc:
        ReviewProject.open(project.root)
    assert exc.value.code == "DESKTOP_INPUT_TAMPERED"


def test_desktop_action_chain_detects_tampering(tmp_path: Path) -> None:
    """REQ: PLTDESK-005 action provenance is hash chained and independently verifiable."""
    project = _project(tmp_path)
    project.add_correspondence(correspondence_type="point", source={"p": [0,0]}, target={"p": [0,0,0]}, uncertainty={"sigma": 1}, author_id="a")
    log = project.root / "actions.jsonl"; value = json.loads(log.read_text()); value["payload"]["target"] = {"p": [9,9,9]}; log.write_text(json.dumps(value) + "\n")
    with pytest.raises(ValidationError) as exc: ReviewProject.open(project.root)
    assert exc.value.code == "DESKTOP_ACTION_TAMPERED"


def test_desktop_offline_merge_preserves_conflicts(tmp_path: Path) -> None:
    """REQ: PLTDESK-003 offline merge never silently overwrites conflicting correspondence edits."""
    ours = _project(tmp_path, "ours")
    theirs = copy_project(ours, tmp_path / "theirs")
    ours.add_correspondence(correspondence_type="point", source={"p": [0,0]}, target={"p": [0,0,0]}, uncertainty={"sigma": 1}, author_id="ours", correspondence_id="corr-1")
    theirs.add_correspondence(correspondence_type="point", source={"p": [1,1]}, target={"p": [1,1,1]}, uncertainty={"sigma": 1}, author_id="theirs", correspondence_id="corr-1")
    merged = ours.merge(theirs, author_id="merger")
    assert merged["conflicts"][0]["correspondence_id"] == "corr-1"
    assert merged["conflicts"][0]["state"] == "unresolved"


def test_desktop_export_is_proposal_only_and_policy_gated(tmp_path: Path) -> None:
    """REQ: PLTDESK-006 policy-approved export remains a review proposal, never direct publication."""
    project = _project(tmp_path)
    output = tmp_path / "proposal.json"
    proposal = project.export_proposal(output, actor_id="reviewer", policy={"allowed": True, "license_state": "approved", "allowed_classifications": ["internal"], "authoritative_publish": False})
    assert proposal["proposal_only"] is True and proposal["requires_server_review"] is True
    assert json.loads(output.read_text())["proposal_hash"] == proposal["proposal_hash"]


def test_desktop_export_denies_authoritative_publish_and_bad_license(tmp_path: Path) -> None:
    """REQ: PLTDESK-006 local tools cannot bypass provider, policy, license, or publication gates."""
    project = _project(tmp_path)
    with pytest.raises(ValidationError) as authority:
        project.export_proposal(tmp_path / "bad.json", actor_id="a", policy={"allowed": True, "license_state": "approved", "allowed_classifications": ["internal"], "authoritative_publish": True})
    assert authority.value.code == "DESKTOP_AUTHORITATIVE_PUBLISH_DENIED"
    with pytest.raises(ValidationError) as license_denied:
        project.export_proposal(tmp_path / "bad-license.json", actor_id="a", policy={"allowed": True, "license_state": "unknown", "allowed_classifications": ["internal"], "authoritative_publish": False})
    assert license_denied.value.code == "DESKTOP_EXPORT_LICENSE_DENIED"


def test_desktop_lock_has_explicit_owner(tmp_path: Path) -> None:
    """REQ: PLTDESK-005 concurrent local edits require an explicit lock owner."""
    project = _project(tmp_path)
    project.acquire_lock("owner-a")
    with pytest.raises(ConflictError): project.acquire_lock("owner-b")
    with pytest.raises(ConflictError): project.release_lock("owner-b")
    project.release_lock("owner-a")


def test_desktop_http_profile_is_loopback_host_origin_and_csrf_safe() -> None:
    """REQ: TSTSEC-001 local HTTP rejects DNS rebinding, cross-site mutation, and non-JSON requests."""
    allowed = validate_local_request(bind_host="127.0.0.1", host_header="127.0.0.1:8765", origin="http://127.0.0.1:8765", method="POST", content_type="application/json", csrf_header="same", csrf_cookie="same")
    assert allowed.allowed is True and "Content-Security-Policy" in allowed.security_headers
    assert validate_local_request(bind_host="0.0.0.0", host_header="127.0.0.1", origin=None, method="GET", content_type=None, csrf_header=None, csrf_cookie=None).code == "DESKTOP_LOOPBACK_BIND_REQUIRED"
    assert validate_local_request(bind_host="127.0.0.1", host_header="evil.example", origin=None, method="GET", content_type=None, csrf_header=None, csrf_cookie=None).code == "DESKTOP_HOST_DENIED"
    assert validate_local_request(bind_host="127.0.0.1", host_header="localhost:8765", origin="https://evil.example", method="POST", content_type="application/json", csrf_header="x", csrf_cookie="x").code == "DESKTOP_ORIGIN_DENIED"
    assert validate_local_request(bind_host="127.0.0.1", host_header="localhost:8765", origin="http://localhost:8765", method="POST", content_type="text/plain", csrf_header="x", csrf_cookie="x").code == "DESKTOP_JSON_REQUIRED"
    assert validate_local_request(bind_host="127.0.0.1", host_header="localhost:8765", origin="http://localhost:8765", method="POST", content_type="application/json", csrf_header="a", csrf_cookie="b").code == "DESKTOP_CSRF_DENIED"


def test_desktop_reopen_is_deterministic_and_crash_safe(tmp_path: Path) -> None:
    """REQ: PLTDESK-005 atomic snapshots reopen with the same manifest and action head."""
    project = _project(tmp_path)
    project.add_observation(stream="rgb", timestamp_ns=1, asset_sha256="a"*64, coordinate_frame_id="frame", metadata={}, author_id="a")
    before = project.verify_integrity(); reopened = ReviewProject.open(project.root); after = reopened.verify_integrity()
    assert before == after
    assert reopened.manifest["manifest_hash"] == project.manifest["manifest_hash"]


def _load_desktop_server_module():
    path = Path(__file__).resolve().parents[2] / "apps" / "desktop-review" / "server.py"
    spec = importlib.util.spec_from_file_location("sip_desktop_review_server", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _raw_http_response(host: str, port: int, request: bytes) -> bytes:
    with socket.create_connection((host, port), timeout=5) as connection:
        connection.sendall(request)
        connection.shutdown(socket.SHUT_WR)
        chunks: list[bytes] = []
        while True:
            chunk = connection.recv(65536)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)


def test_desktop_live_http_authorizes_before_emitting_exactly_one_status(tmp_path: Path) -> None:
    """REQ: TSTSEC-001 live desktop HTTP denial emits one 403 and never begins a 200 response."""
    module = _load_desktop_server_module()
    server = module.create_server(_project(tmp_path), host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        denied = _raw_http_response(
            str(host),
            int(port),
            b"GET /api/project HTTP/1.1\r\nHost: evil.example\r\nConnection: close\r\n\r\n",
        )
        status_lines = [line for line in denied.split(b"\r\n") if line.startswith(b"HTTP/")]
        assert len(status_lines) == 1
        assert b" 403 " in status_lines[0]
        assert b" 200 " not in denied
        assert b"DESKTOP_HOST_DENIED" in denied

        allowed = _raw_http_response(
            str(host),
            int(port),
            f"GET /api/project HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n".encode("ascii"),
        )
        allowed_status_lines = [line for line in allowed.split(b"\r\n") if line.startswith(b"HTTP/")]
        assert len(allowed_status_lines) == 1
        assert b" 200 " in allowed_status_lines[0]
        assert b'"status":"passed"' in allowed
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
