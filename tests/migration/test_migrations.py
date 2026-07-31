from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

from sip.database import Base

ROOT = Path(__file__).parents[2]


def _sqlite_schema_snapshot(database: Path) -> dict[str, object]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        tables = sorted(
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        )
        snapshot: dict[str, object] = {}
        for table in tables:
            quoted = table.replace('"', '""')
            columns = [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "notnull": int(row["notnull"]),
                    "default": row["dflt_value"],
                    "pk": int(row["pk"]),
                }
                for row in connection.execute(f'PRAGMA table_info("{quoted}")')
            ]
            indexes: list[dict[str, object]] = []
            for index in connection.execute(f'PRAGMA index_list("{quoted}")'):
                index_name = index["name"]
                index_columns = [
                    row["name"]
                    for row in connection.execute(
                        f'PRAGMA index_info("{index_name.replace(chr(34), chr(34) * 2)}")'
                    )
                ]
                indexes.append(
                    {
                        "name": index_name if index["origin"] == "c" else "<automatic>",
                        "unique": int(index["unique"]),
                        "origin": index["origin"],
                        "partial": int(index["partial"]),
                        "columns": index_columns,
                    }
                )
            foreign_keys = [
                {
                    "table": row["table"],
                    "from": row["from"],
                    "to": row["to"],
                    "on_update": row["on_update"],
                    "on_delete": row["on_delete"],
                    "match": row["match"],
                }
                for row in connection.execute(f'PRAGMA foreign_key_list("{quoted}")')
            ]
            snapshot[table] = {
                "columns": columns,
                "indexes": sorted(indexes, key=lambda item: (str(item["name"]), str(item["columns"]))),
                "foreign_keys": sorted(
                    foreign_keys,
                    key=lambda item: (str(item["table"]), str(item["from"]), str(item["to"])),
                ),
            }
        return snapshot
    finally:
        connection.close()


def _alembic(database: Path, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["alembic", "-c", "alembic.ini", *args],
        cwd=ROOT,
        env={
            **os.environ,
            "PYTHONPATH": "src",
            "SIP_DATABASE_URL": f"sqlite:///{database}",
            **(extra_env or {}),
        },
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.migration
def test_clean_install_reaches_head_and_matches_canonical_tables(tmp_path: Path) -> None:
    """REQ: DATDB-004, DELDOD-002 clean installation reaches the append-only schema head."""
    database = tmp_path / "clean.sqlite3"
    result = _alembic(database, "upgrade", "head")
    assert result.returncode == 0, result.stdout + result.stderr
    connection = sqlite3.connect(database)
    actual = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = set(Base.metadata.tables)
    assert expected <= actual
    assert actual - expected == {"alembic_version"}
    assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0019_progress09_deployment_profiles"


@pytest.mark.migration
def test_upgrade_from_foundation_preserves_immutable_identifiers_and_hashes(tmp_path: Path) -> None:
    """REQ: SIPMIG-001, SIPMIG-006 additive upgrade preserves source hashes and stable identifiers."""
    database = tmp_path / "upgrade.sqlite3"
    assert _alembic(database, "upgrade", "0001_foundation_control_plane").returncode == 0
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("INSERT INTO tenants(tenant_id,name,status,created_at) VALUES (?,?,?,CURRENT_TIMESTAMP)", ("tenant-upgrade", "Upgrade", "active"))
    connection.execute(
        "INSERT INTO projects(project_id,tenant_id,name,vertical,classification,status,created_at) VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        ("project-upgrade", "tenant-upgrade", "Upgrade", "platform", "internal", "active"),
    )
    digest = "a" * 64
    connection.execute(
        "INSERT INTO assets(sha256,byte_count,media_type,storage_key,encryption_metadata,created_at) VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
        (digest, 5, "application/octet-stream", digest, "{}"),
    )
    connection.execute(
        "INSERT INTO asset_refs(asset_id,tenant_id,project_id,sha256,original_name,classification,retention_class,source_class,authority_class,provenance_json,legal_hold,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        ("asset-upgrade", "tenant-upgrade", "project-upgrade", digest, "source.bin", "internal", "preservation", "direct_capture", "evidence", "{}", 0, "fixture"),
    )
    connection.commit()
    connection.close()
    result = _alembic(database, "upgrade", "head")
    assert result.returncode == 0, result.stdout + result.stderr
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT sha256 FROM asset_refs WHERE asset_id='asset-upgrade'").fetchone()[0] == digest
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


@pytest.mark.migration
def test_upgrade_reclassifies_legacy_interaction_representations_without_promoting_others(tmp_path: Path) -> None:
    """REQ: RECHYB-002, DATHYB-004 migration applies the exact proxy authority ceiling and disposable marker."""
    database = tmp_path / "authority-upgrade.sqlite3"
    assert _alembic(database, "upgrade", "0006_operation_trace_context").returncode == 0
    connection = sqlite3.connect(database)
    common = (
        "tenant", "project", "scene", "asset", None, "provider", "frame",
        "generated", 1, "[]", "[]", "{}", "{}", "{}", "quarantined",
    )
    connection.execute(
        "INSERT INTO representations("
        "representation_id,tenant_id,project_id,scene_id,asset_id,operation_id,kind,provider_id,"
        "coordinate_frame_id,source_class,authority_class,lossy,intended_uses_json,prohibited_uses_json,"
        "quality_json,provenance_json,support_map_json,state,created_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        ("proxy-legacy", *common[:5], "interaction", *common[5:7], common[7], "interaction", *common[8:]),
    )
    connection.execute(
        "INSERT INTO representations("
        "representation_id,tenant_id,project_id,scene_id,asset_id,operation_id,kind,provider_id,"
        "coordinate_frame_id,source_class,authority_class,lossy,intended_uses_json,prohibited_uses_json,"
        "quality_json,provenance_json,support_map_json,state,created_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        ("metric-existing", *common[:5], "metric", *common[5:7], "inferred", "metric", *common[8:]),
    )
    connection.commit()
    connection.close()

    result = _alembic(database, "upgrade", "head")
    assert result.returncode == 0, result.stdout + result.stderr
    connection = sqlite3.connect(database)
    proxy = connection.execute(
        "SELECT authority_class,authority_ceiling,disposable FROM representations WHERE representation_id='proxy-legacy'"
    ).fetchone()
    metric = connection.execute(
        "SELECT authority_class,authority_ceiling,disposable FROM representations WHERE representation_id='metric-existing'"
    ).fetchone()
    assert proxy == ("derived_non_authoritative", "derived_non_authoritative", 1)
    assert metric == ("metric", "metric", 0)


@pytest.mark.migration
def test_destructive_downgrade_is_denied_without_evidence_and_exactly_restores_prior_schema(tmp_path: Path) -> None:
    """REQ: DATDB-004 destructive rollback requires retained evidence and exactly restores the prior schema."""
    expected_database = tmp_path / "expected-0012.sqlite3"
    assert _alembic(expected_database, "upgrade", "0012_scene_runtime_review").returncode == 0
    expected_schema = _sqlite_schema_snapshot(expected_database)

    database = tmp_path / "downgrade.sqlite3"
    assert _alembic(database, "upgrade", "head").returncode == 0
    denied = _alembic(database, "downgrade", "-1")
    assert denied.returncode != 0
    assert "destructive downgrade denied" in denied.stderr

    missing_evidence = _alembic(
        database,
        "downgrade",
        "0012_scene_runtime_review",
        extra_env={"SIP_ALLOW_DESTRUCTIVE_DOWNGRADE": "1"},
    )
    assert missing_evidence.returncode != 0
    assert "verified backup" in missing_evidence.stderr

    evidence = {
        "SIP_ALLOW_DESTRUCTIVE_DOWNGRADE": "1",
        "SIP_VERIFIED_BACKUP_REFERENCE": "sha256:" + "1" * 64,
        "SIP_DOWNGRADE_DRY_RUN_REFERENCE": "sha256:" + "2" * 64,
        "SIP_DOWNGRADE_AUDIT_REFERENCE": "sha256:" + "3" * 64,
        "SIP_DOWNGRADE_REHEARSAL_ID": "rehearsal:0013-to-0012",
    }
    rehearsed = _alembic(
        database,
        "downgrade",
        "0012_scene_runtime_review",
        extra_env=evidence,
    )
    assert rehearsed.returncode == 0, rehearsed.stdout + rehearsed.stderr
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0012_scene_runtime_review"
    connection.close()
    assert _sqlite_schema_snapshot(database) == expected_schema

    # Earlier migrations remain reversible only in this same explicitly evidenced,
    # isolated rehearsal; this confirms the 0013 through 0010 gates do not corrupt the chain.
    to_base = _alembic(database, "downgrade", "base", extra_env=evidence)
    assert to_base.returncode == 0, to_base.stdout + to_base.stderr


@pytest.mark.migration
def test_append_only_migration_manifest_matches_bytes() -> None:
    """REQ: SIPMIG-001 migration history is append-only and every retained migration byte is integrity-locked."""
    manifest = json.loads((ROOT / "migrations" / "manifest.json").read_text())
    assert manifest["append_only"] is True
    revisions = []
    for item in manifest["migrations"]:
        path = ROOT / item["path"]
        payload = path.read_bytes()
        assert len(payload) == item["byte_count"]
        assert hashlib.sha256(payload).hexdigest() == item["sha256"]
        revisions.append(path.stem.split("_", 1)[0])
    assert revisions == ["0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009", "0010", "0011", "0012", "0013", "0014", "0015", "0016", "0017", "0018", "0019"]
