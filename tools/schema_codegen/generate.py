from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from sip.agents import AgentAnswer, AgentProposalContract, AgentToolSpec
from sip.api import create_app
from sip.context import PlatformContext, temporary_settings
from sip.worker_manifest import WorkerManifest
from sip.worker_protocol import CandidatePackage, CandidateRequest, WorkerLease, WorkerReceipt
from sip.spatial_query import SavedQueryContract, SearchQueryInput
from sip.contracts import (
    AssertionContract,
    CaptureAssetContract,
    CaptureFrameContract,
    CaptureRootContract,
    ConsentGrantContract,
    CoordinateFrameContract,
    DerivationEventContract,
    EvidenceRecordContract,
    EventEnvelopeContract,
    GeometryAssetManifestContract,
    SpatialConversionRequestContract,
    SpatialConversionAssetContract,
    ProviderPromotionContract,
    ProviderProgressContract,
    ProviderCapabilityDescriptorContract,
    ManualExternalReceiptContract,
    IntendedUseValidationContract,
    HybridSceneViewManifestContract,
    HybridWorkerLeaseRenewalContract,
    ProviderCleanupConfirmationContract,
    ProviderFailureContract,
    InteractionProfileManifestContract,
    MeasurementContract,
    ModelManifestContract,
    OperationContract,
    PreservationManifestContract,
    ProviderManifestContract,
    RepresentationAssetContract,
    SceneEntityContract,
    SpatialAnnotationContract,
    SpatialTransformContract,
    ViewerSessionContract,
    ViewerSessionReplayContract,
    TemporalComparisonContract,
    ChangeCandidateContract,
    ChangeReviewContract,
    ChangeBenchmarkContract,
)

MODELS = {
    "capture-asset": CaptureAssetContract,
    "capture-frame": CaptureFrameContract,
    "capture-root": CaptureRootContract,
    "consent-grant": ConsentGrantContract,
    "coordinate-frame": CoordinateFrameContract,
    "spatial-transform": SpatialTransformContract,
    "geometry-asset-manifest": GeometryAssetManifestContract,
    "evidence-record": EvidenceRecordContract,
    "assertion": AssertionContract,
    "derivation-event": DerivationEventContract,
    "spatial-annotation": SpatialAnnotationContract,
    "viewer-session": ViewerSessionContract,
    "viewer-session-replay": ViewerSessionReplayContract,
    "temporal-comparison": TemporalComparisonContract,
    "change-candidate": ChangeCandidateContract,
    "change-review": ChangeReviewContract,
    "change-benchmark": ChangeBenchmarkContract,
    "event-envelope": EventEnvelopeContract,
    "measurement": MeasurementContract,
    "model-manifest": ModelManifestContract,
    "operation": OperationContract,
    "preservation-manifest": PreservationManifestContract,
    "provider-capability": ProviderCapabilityDescriptorContract,
    "provider-promotion": ProviderPromotionContract,
    "spatial-conversion-asset": SpatialConversionAssetContract,
    "spatial-conversion-request": SpatialConversionRequestContract,
    "provider-progress": ProviderProgressContract,
    "intended-use-validation": IntendedUseValidationContract,
    "manual-external-receipt": ManualExternalReceiptContract,
    "hybrid-scene-view": HybridSceneViewManifestContract,
    "hybrid-worker-lease-renewal": HybridWorkerLeaseRenewalContract,
    "provider-cleanup-confirmation": ProviderCleanupConfirmationContract,
    "provider-failure": ProviderFailureContract,
    "interaction-profile-manifest": InteractionProfileManifestContract,
    "provider-manifest": ProviderManifestContract,
    "representation-asset": RepresentationAssetContract,
    "scene-entity": SceneEntityContract,
    "representation-candidate": CandidatePackage,
    "representation-candidate-request": CandidateRequest,
    "worker-lease": WorkerLease,
    "worker-manifest": WorkerManifest,
    "worker-receipt": WorkerReceipt,
    "spatial-query": SearchQueryInput,
    "saved-query": SavedQueryContract,
    "agent-tool": AgentToolSpec,
    "agent-answer": AgentAnswer,
    "agent-proposal": AgentProposalContract,
}
SERVICES = [
    "all",
    "control-api",
    "identity-policy",
    "capture-service",
    "workflow-service",
    "scene-service",
    "evidence-service",
    "search-service",
    "export-service",
    "notification-service",
    "audit-service",
    "representation-api",
    "provider-registry",
    "representation-publisher",
    "construction",
    "liveforever",
]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    generated: dict[Path, str] = {}
    for name, model in MODELS.items():
        schema = model.model_json_schema(mode="validation")
        schema["$id"] = f"https://schemas.sip.local/v1.1.0/{name}.schema.json"
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        generated[root / "schemas" / "jsonschema" / f"{name}.schema.json"] = json.dumps(schema, indent=2, sort_keys=True) + "\n"

    event_catalog = json.loads((root / "schemas/events/event-catalog.json").read_text(encoding="utf-8"))
    event_base = EventEnvelopeContract.model_json_schema(mode="serialization")
    event_base["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    for entry in event_catalog["events"]:
        event_schema = copy.deepcopy(event_base)
        event_type = entry["type"]
        version = entry["version"]
        event_schema["$id"] = f"https://schemas.sip.local/v1.1.0/events/{event_type}/{version}.schema.json"
        event_schema["title"] = event_type
        event_schema["properties"]["event_type"] = {"const": event_type}
        event_schema["properties"]["schema_version"] = {"const": version}
        generated[root / "schemas" / "events" / event_type / f"{version}.schema.json"] = json.dumps(
            event_schema, indent=2, sort_keys=True
        ) + "\n"

    build_root = root / "build" / "generated" / "openapi"
    for service in SERVICES:
        context = PlatformContext.create(temporary_settings(build_root / f"runtime-{service}"))
        schema = create_app(context=context, service_name=service).openapi()
        generated[root / "schemas" / "openapi" / f"{service}.openapi.json"] = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        manifest_path = root / "services" / service / "service.json"
        if service not in {"all"} and manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["operations"] = sorted(
                [
                    {"method": method.upper(), "path": route, "operation_id": operation["operationId"]}
                    for route, methods in schema.get("paths", {}).items()
                    for method, operation in methods.items()
                    if method.lower() in {"get", "post", "put", "patch", "delete"}
                ],
                key=lambda item: (item["path"], item["method"], item["operation_id"]),
            )
            generated[manifest_path] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    failures: list[str] = []
    for path, content in generated.items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                failures.append(str(path.relative_to(root)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    if failures:
        raise SystemExit("generated contract drift:\n" + "\n".join(failures))
    print(json.dumps({"generated": len(generated), "check": args.check}, sort_keys=True))


if __name__ == "__main__":
    main()
