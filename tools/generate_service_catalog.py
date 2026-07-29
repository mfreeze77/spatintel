from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "governance" / "service-catalog.json"

SERVICE_METADATA: dict[str, dict[str, Any]] = {
    "control-api": {"owner": "platform-control", "stores": ["postgresql"], "tables": ["tenants", "projects", "identities", "role_bindings"], "dependencies": ["identity-policy", "workflow-service", "scene-service"]},
    "identity-policy": {"owner": "security-privacy", "stores": ["postgresql"], "tables": ["identities", "role_bindings", "consent_grants"], "dependencies": ["audit-service"]},
    "capture-service": {"owner": "capture", "stores": ["postgresql", "object-store"], "tables": ["assets", "asset_refs", "multipart_uploads"], "dependencies": ["identity-policy", "workflow-service", "evidence-service"]},
    "workflow-service": {"owner": "platform-runtime", "stores": ["postgresql", "valkey"], "tables": ["operations", "outbox_events", "worker_candidate_receipts"], "dependencies": ["identity-policy", "audit-service"]},
    "scene-service": {"owner": "scene-core", "stores": ["postgresql", "postgis"], "tables": ["coordinate_frames", "spatial_transforms", "scenes", "scene_entities", "scene_commits", "scene_branches", "scene_tags", "spatial_annotations", "anchor_remaps", "measurements"], "dependencies": ["identity-policy", "evidence-service", "representation-publisher"]},
    "evidence-service": {"owner": "evidence-trust", "stores": ["postgresql", "object-store"], "tables": ["assets", "asset_refs", "geometry_asset_manifests", "evidence_records", "assertions", "derivation_events", "audit_events", "retention_rules", "legal_holds", "deletion_requests", "deletion_evidence"], "dependencies": ["identity-policy", "audit-service"]},
    "search-service": {"owner": "platform-intelligence", "stores": ["postgresql", "derived-search-index"], "tables": ["search_documents", "saved_queries", "agent_proposals"], "dependencies": ["identity-policy", "scene-service", "evidence-service"]},
    "export-service": {"owner": "preservation", "stores": ["postgresql", "object-store"], "tables": ["export_manifests", "backup_runs"], "dependencies": ["identity-policy", "evidence-service", "scene-service"]},
    "notification-service": {"owner": "platform-runtime", "stores": ["postgresql"], "tables": ["notification_preferences", "notification_deliveries", "collaboration_tasks"], "dependencies": ["identity-policy", "audit-service"]},
    "audit-service": {"owner": "security-assurance", "stores": ["postgresql", "immutable-audit-export"], "tables": ["audit_events"], "dependencies": []},
    "representation-api": {"owner": "hybrid-representations", "stores": ["postgresql", "object-store"], "tables": ["representations", "representation_bindings", "provider_manifests"], "dependencies": ["identity-policy", "workflow-service", "provider-registry"]},
    "provider-registry": {"owner": "model-provider-governance", "stores": ["postgresql", "source-control-manifests"], "tables": ["provider_manifests", "model_manifests"], "dependencies": ["audit-service"]},
    "representation-publisher": {"owner": "scene-core", "stores": ["postgresql"], "tables": [], "dependencies": ["identity-policy", "representation-api", "scene-service", "audit-service"]},
    "construction": {
        "owner": "construction-vertical",
        "stores": ["postgresql", "postgis", "object-store"],
        "tables": [
            "construction_records", "construction_deficiencies", "construction_document_links",
            "construction_surveys", "construction_visits", "construction_document_revisions",
            "construction_issues", "construction_commissioning_runs", "construction_interchanges",
            "construction_handoffs",
        ],
        "dependencies": ["identity-policy", "scene-service", "evidence-service", "export-service", "audit-service"],
    },
    "liveforever": {
        "owner": "liveforever-vertical",
        "stores": ["postgresql", "postgis", "object-store"],
        "tables": [
            "consent_grants", "memory_records", "narrative_editions",
            "liveforever_governance", "liveforever_interviews", "liveforever_transcript_segments",
            "liveforever_editions", "liveforever_derivatives", "liveforever_preservation_releases",
        ],
        "dependencies": ["identity-policy", "scene-service", "evidence-service", "export-service", "audit-service"],
    },
}

SHARED_KERNEL_EXCEPTIONS = {
    "assets": ["capture-service", "evidence-service"],
    "asset_refs": ["capture-service", "evidence-service"],
    "audit_events": ["audit-service", "evidence-service"],
    "identities": ["control-api", "identity-policy"],
    "role_bindings": ["control-api", "identity-policy"],
    "provider_manifests": ["provider-registry", "representation-api"],
    "consent_grants": ["identity-policy", "liveforever"],
}

WORKER_OWNER: dict[str, str] = {
    "capture-normalizer": "capture",
    "depth-normalizer": "reconstruction-metric",
    "pose-optimizer": "reconstruction-metric",
    "fusion-tsdf": "reconstruction-metric",
    "geometry-cleanup": "hybrid-representations",
    "mesh-lod": "hybrid-representations",
    "collision-navigation": "hybrid-representations",
    "splat": "reconstruction-visual",
    "splat-normalizer": "reconstruction-visual",
    "splat-surface": "hybrid-representations",
    "change-detection": "reconstruction-temporal",
    "representation-quality": "hybrid-representations",
    "document-media": "platform-intelligence",
    "semantics": "platform-intelligence",
    "report-export": "preservation",
    "lingbot-adapter": "reconstruction-learned",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def generate() -> dict[str, Any]:
    event_catalog = _load(ROOT / "schemas/events/event-catalog.json")
    produced: dict[str, list[str]] = {}
    for event in event_catalog["events"]:
        produced.setdefault(event["owner"], []).append(event["type"])

    services: list[dict[str, Any]] = []
    for directory in sorted((ROOT / "services").iterdir()):
        if not directory.is_dir() or not (directory / "service.json").is_file():
            continue
        manifest = _load(directory / "service.json")
        name = manifest["service_name"]
        meta = SERVICE_METADATA[name]
        services.append({
            "kind": "service",
            "name": name,
            "owner": meta["owner"],
            "repository_path": f"services/{name}",
            "data_stores": meta["stores"],
            "owned_tables": sorted(meta["tables"]),
            "shared_kernel_exceptions": sorted(table for table in meta["tables"] if table in SHARED_KERNEL_EXCEPTIONS),
            "inbound_apis": manifest["operations"],
            "outbound_dependencies": sorted(meta["dependencies"]),
            "events_produced": sorted(produced.get(name, [])),
            "events_consumed": [],
            "secret_references": ["sip-runtime-secrets/SIP_DATABASE_URL", "sip-runtime-secrets/SIP_WORKLOAD_IDENTITY"],
            "slo": {"availability_target": "99.9%", "latency_budget": "p95 <= 1000ms for bounded control operations", "error_budget_window_days": 30},
            "shutdown": {"drain_seconds": 30, "in_flight_behavior": "finish committed transaction; return or requeue uncommitted work"},
            "recovery_strategy": "restart from durable database/outbox state; verify audit and object hashes before readiness",
            "blast_radius": f"tenant/project scoped requests handled by {name}; no cross-tenant fail-open behavior",
            "retry_safety": "idempotency key or immutable command identifier required for mutations",
            "rpo": "0 for committed transactional state; object writes verified before publication",
            "rto": "15 minutes local/hybrid target; profile-specific production objective requires deployment validation",
            "degraded_behavior": "fail closed for authorization/publication; expose bounded read-only metadata where explicitly safe",
            "dependency_controls": {"connect_timeout_seconds": 3, "request_timeout_seconds": 15, "circuit_breaker": "open after bounded consecutive failures; half-open probe", "cross_region_failover": "deny unless pre-approved"},
        })

    workers: list[dict[str, Any]] = []
    for directory in sorted((ROOT / "workers").iterdir()):
        if not directory.is_dir() or not (directory / "worker-manifest.json").is_file():
            continue
        manifest = _load(directory / "worker-manifest.json")
        name = manifest["name"]
        workers.append({
            "kind": "worker",
            "name": name,
            "owner": WORKER_OWNER[name],
            "repository_path": f"workers/{name}",
            "data_stores": ["immutable-input-handles", "write-only-quarantine-staging"],
            "owned_tables": [],
            "shared_kernel_exceptions": [],
            "inbound_apis": [{"protocol": manifest["input_contract"], "capability": capability} for capability in manifest["capabilities"]],
            "outbound_dependencies": ["workflow-service"],
            "events_produced": [],
            "events_consumed": ["operation.leased", "operation.cancel_requested"],
            "secret_references": ["workload-identity-token", "lease-verification-key"],
            "slo": {"queue_start_budget": "p95 <= 60s for admitted reference jobs", "checkpoint_budget": "at each declared safe stage", "error_budget_window_days": 30},
            "shutdown": {"drain_seconds": 60, "in_flight_behavior": "checkpoint at safe point, relinquish lease, never publish partial output"},
            "recovery_strategy": "new attempt from verified checkpoint; unsafe expiry quarantines the operation",
            "blast_radius": "single operation attempt in one tenant/project; resource exhaustion cannot terminate control-plane services",
            "retry_safety": "signed lease, immutable input hash, deterministic idempotent candidate hash, exactly-once publication outside worker",
            "rpo": "last verified checkpoint",
            "rto": "bounded by lease reconciliation and queue admission",
            "degraded_behavior": "retain source/prior accepted representations and deny publication of partial output",
            "dependency_controls": {"connect_timeout_seconds": 3, "request_timeout_seconds": 15, "circuit_breaker": "workflow-gateway bounded retry", "network_policy": "deny compute network; trusted control gateway only"},
            "workload_identity": manifest["workload_identity"],
            "publication_permission": manifest["publication_permission"],
            "resource_limits": manifest["resource_limits"],
            "manifest_sha256": manifest["manifest_sha256"],
        })

    return {
        "schema": "sip.service-catalog/v1",
        "catalog_version": "1.1.0",
        "generated_from": ["services/*/service.json", "workers/*/worker-manifest.json", "schemas/events/event-catalog.json"],
        "ownership_policy": "Only the owning service may write an owned table. Listed shared-kernel exceptions are temporary, explicit, and must be removed as physical service isolation matures.",
        "shared_kernel_exceptions": SHARED_KERNEL_EXCEPTIONS,
        "components": services + workers,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(generate(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != content:
            raise SystemExit("service catalog drift")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(content, encoding="utf-8")
    print(json.dumps({"path": str(OUTPUT.relative_to(ROOT)), "check": args.check}, sort_keys=True))


if __name__ == "__main__":
    main()
