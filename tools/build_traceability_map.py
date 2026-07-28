#!/usr/bin/env python3
"""Build conservative requirement evidence overlays from explicitly tagged tests."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "requirements/spec-index.json"
DESTINATION = ROOT / "requirements/implementation-map.json"
REQ_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]+-\d{3}\b")

VERIFIED = {
    "APPFAIL-001", "APPFAIL-002", "APPFAIL-003", "APPFAIL-004", "APPFAIL-005",
    "APPFAIL-006", "APPFAIL-007", "APPFAIL-008", "APPFAIL-009", "APPFAIL-010",
    "ARCADR-001", "ARCADR-002", "ARCADR-003", "ARCADR-005",
    "ARCEVT-001", "ARCEVT-002", "ARCEVT-003", "ARCEVT-004", "ARCEVT-005",
    "ARCIAM-001",
    "ARCSVC-001", "ARCSVC-003", "ARCSVC-004", "ARCSVC-005",
    "ARCOBS-001", "ARCOBS-002", "ARCOBS-003", "ARCOBS-004",
    "ARCSYNC-002",
    "CONDEMO-004", "CONDEMO-005",
    "DATASSET-001", "DATASSET-002", "DATASSET-003",
    "DATSEARC-001", "DATSEARC-002", "DATSEARC-003", "DATSEARC-004", "DATSEARC-005", "DATSEARC-006",
    "DELDEV-006", "GOVDOC-001",
    "GOVOPEN-001", "GOVOPEN-002", "GOVOPEN-004", "GOVOPEN-005",
    "GOVRISK-006", "GOVRISK-007", "GOVRISK-008", "GOVRISK-009",
    "HYBAPI-003", "HYBAPI-004", "HYBAPI-005", "HYBAPI-009", "HYBAPI-010",
    "HYBRUN-003", "HYBTEST-015", "HYBTEST-016",
    "LIFDEMO-004", "LIFDEMO-005",
    "OPSCOST-006", "OPSSRE-001", "OPSSRE-002", "OPSTHR-007", "OPSTHREA-001",
    "PLTGRPC-001", "PLTGRPC-003", "PLTGRPC-004", "PLTGRPC-005", "PLTGRPC-006",
    "PLTAGENT-001", "PLTAGENT-002", "PLTAGENT-003", "PLTAGENT-004", "PLTAGENT-005", "PLTAGENT-006",
    "PLTIO-003", "PLTIO-006", "PLTIO-012", "PLTSDK-003",
    "PLTSQL-001", "PLTSQL-002", "PLTSQL-003", "PLTSQL-006", "PLTVIEW-007",
    "DATHYB-004", "RECALIGN-001", "RECHYB-002", "RECHYB-005",
    "RECMESH-010", "RECPROV-007", "RECPROV-013",
}
IN_PROGRESS = {
    "ARCDEP-002", "CONDEMO-001", "DELDEV-004", "DELDOD-001",
    "ARCSVC-002", "GOVLIC-001", "GOVLIC-002", "GOVLIC-003", "GOVOPEN-003", "LIFCONS-002", "LIFTEST-005",
    "OPSCICD-001", "OPSCICD-002", "OPSCICD-003",
    "RECBIDI-003", "RECBIDI-008",
    "TSTGATE-001", "TSTGATE-003", "TSTLAY-002", "TSTLAY-004", "TSTSEC-003",
    "TSTSTRAT-001", "TSTSTRAT-002",
}
EXTERNAL = {"DATDB-004", "DELDEV-005", "OPSDR-002", "OPSSEC-005"}

IMPLEMENTATION_GROUPS: dict[str, list[str]] = {
    "APPFAIL": ["src/sip/failures.py", "governance/failure-catalog.json", "docs/adr/ADR-0007-versioned-failure-catalog-and-new-lineage-recovery.md"],
    "ARCADR": ["docs/adr", "docs/adr/index.json", "governance/risk-register.json"],
    "ARCEVT": ["src/sip/events.py", "src/sip/operations.py", "src/sip/database.py", "schemas/events", "migrations/versions/0008_complete_event_envelope.py"],
    "ARCSVC": ["governance/service-catalog.json", "tools/generate_service_catalog.py", "services", "workers"],
    "ARCSYNC": ["src/sip/assets.py", "src/sip/api.py", "src/sip/database.py"],
    "ARCDEP": ["infrastructure/compose/docker-compose.yml", "infrastructure/kubernetes/base", "infrastructure/terraform", "tools/validate_infrastructure.py"],
    "ARCIAM": ["src/sip/auth.py", "src/sip/policy.py", "src/sip/api.py", "src/sip/tenancy.py"],
    "ARCHHYB": ["src/sip/hybrid.py", "src/sip/representations.py", "src/sip/operations.py", "src/sip/api.py", "src/sip/database.py", "services/provider-registry", "services/representation-api", "migrations/versions/0011_governed_hybrid_representation.py"],
    "ARCOBS": ["src/sip/observability.py", "src/sip/api.py", "src/sip/operations.py", "infrastructure/observability"],
    "CAPIOS": ["apps/ios-capture/Sources", "apps/ios-capture/Tests", "schemas/jsonschema"],
    "CAPREC": ["apps/ios-capture/Sources/CaptureCore", "apps/ios-capture/Tests/CaptureCoreTests"],
    "CAPSENS": ["apps/ios-capture/Sources/CaptureSensors", "apps/ios-capture/Tests/CaptureCoreTests"],
    "CAPQUAL": ["apps/ios-capture/Sources/CaptureQuality", "apps/ios-capture/Tests/CaptureCoreTests"],
    "CAPPRIV": ["apps/ios-capture/Sources", "apps/ios-capture/Tests/CaptureCoreTests"],
    "CAPSTRAT": ["apps/ios-capture/Sources", "apps/ios-capture/Tests/CaptureCoreTests"],
    "CAPSOP": ["apps/ios-capture/Sources", "apps/ios-capture/Tests/CaptureCoreTests"],
    "CAPCSCP": ["apps/ios-capture/Sources/CapturePackage", "apps/ios-capture/Tests/CaptureCoreTests", "src/sip/capture.py"],
    "CONHYB": ["src/sip/construction.py", "src/sip/collaboration.py", "src/sip/scene.py"],
    "CONMEAS": ["src/sip/construction.py", "src/sip/database.py", "src/sip/models.py"],
    "CONDEMO": ["src/sip/construction.py", "tools/run_demo.py", "docs/user/CONSTRUCTION.md", "verticals/construction"],
    "DATDB": ["src/sip/database.py", "migrations", "tools/rehearse_migrations.py"],
    "DATFRAME": ["src/sip/spatial_data.py", "src/sip/contracts.py", "src/sip/database.py", "schemas/jsonschema/coordinate-frame.schema.json", "migrations/versions/0010_spatial_truth_and_twin_controls.py"],
    "DATGEOM": ["src/sip/spatial_data.py", "src/sip/contracts.py", "src/sip/database.py", "schemas/jsonschema/representation-asset.schema.json", "migrations/versions/0010_spatial_truth_and_twin_controls.py"],
    "DATEVID": ["src/sip/spatial_data.py", "src/sip/contracts.py", "src/sip/database.py", "src/sip/exporting.py", "migrations/versions/0010_spatial_truth_and_twin_controls.py"],
    "DATANCH": ["src/sip/spatial_data.py", "src/sip/contracts.py", "src/sip/database.py", "src/sip/representations.py", "migrations/versions/0010_spatial_truth_and_twin_controls.py"],
    "DATTWIN": ["src/sip/spatial_data.py", "src/sip/scene.py", "src/sip/database.py", "src/sip/exporting.py", "migrations/versions/0010_spatial_truth_and_twin_controls.py"],
    "GOVETH": ["src/sip/spatial_data.py", "src/sip/models.py", "src/sip/policy.py", "docs/security/THREAT_MODEL.md"],
    "DATGIT": ["src/sip/scene.py", "src/sip/spatial_data.py", "src/sip/database.py", "migrations/versions/0010_spatial_truth_and_twin_controls.py"],
    "DATHYB": ["src/sip/representations.py", "src/sip/scene.py", "src/sip/database.py"],
    "DATRET": ["src/sip/lifecycle.py", "src/sip/database.py", "docs/runbooks/CONTROLLED_DELETION.md"],
    "DATSCENE": ["src/sip/scene.py", "src/sip/database.py", "src/sip/models.py"],
    "DATASSET": ["src/sip/assets.py", "src/sip/database.py", "src/sip/models.py"],
    "DATSEARC": ["src/sip/search.py", "src/sip/spatial_query.py", "src/sip/database.py", "schemas/jsonschema/spatial-query.schema.json", "migrations/versions/0009_authorized_spatial_search_and_agents.py"],
    "DELDEV": ["Makefile", "justfile", "tools/static_checks.py", "tools/typecheck.py", "docs/developer/GETTING_STARTED.md", "CONTRIBUTING.md"],
    "DELDOD": ["docs/developer", "docs/operator", "docs/user", "docs/release", "src/sip/errors.py", "src/sip/audit.py"],
    "GOVDOC": ["src/sip/spec_lint.py", "tools/update_requirements.py", "requirements/spec-index.json", "requirements/requirements-ledger.json"],
    "GOVOPEN": ["governance/open-questions.json", "tools/check_governance.py", "requirements/blockers.md"],
    "GOVRISK": ["governance/risk-register.json", "governance/service-catalog.json", "tools/check_governance.py", "docs/runbooks/OPERATIONS_INCIDENTS.md"],
    "GOVLIC": ["src/sip/model_governance.py", "tools/check_governance.py", "tools/license_check.py", "tools/generate_third_party_lock.py", "tools/release.py", "third_party/manifest.lock.json"],
    "HYBAPI": ["src/sip/worker_manifest.py", "src/sip/worker_protocol.py", "src/sip/worker_runtime.py", "src/sip/operations.py", "src/sip/representations.py", "schemas/protobuf/worker.proto"],
    "HYBRUN": ["src/sip/hybrid.py", "src/sip/representations.py", "src/sip/scene.py", "src/sip/api.py", "apps/web", "tools/run_demo.py"],
    "HYBTEST": ["src/sip/geometry.py", "src/sip/representations.py", "src/sip/worker_sandbox.py", "tools/run_demo.py"],
    "LIFHYB": ["src/sip/liveforever.py", "src/sip/policy.py", "apps/web"],
    "LIFOVR": ["src/sip/liveforever.py", "src/sip/models.py", "src/sip/scene.py"],
    "LIFCONS": ["src/sip/liveforever.py", "src/sip/policy.py", "src/sip/search.py", "src/sip/exporting.py"],
    "LIFDEMO": ["src/sip/liveforever.py", "tools/run_demo.py", "docs/user/LIVEFOREVER.md", "verticals/liveforever"],
    "LIFTEST": ["src/sip/liveforever.py", "src/sip/exporting.py", "tools/run_demo.py", "verticals/liveforever"],
    "OPSCOST": ["src/sip/lifecycle.py", "src/sip/operations.py", "src/sip/database.py"],
    "OPSAUDIT": [
        "src/sip/audit.py",
        "src/sip/spatial_data.py",
        "src/sip/database.py",
        "src/sip/model_governance.py",
        "src/sip/lifecycle.py",
        "src/sip/exporting.py",
        "migrations",
    ],
    "OPSKEY": ["src/sip/lifecycle.py", "src/sip/assets.py", "docs/runbooks/KEY_ROTATION.md"],
    "OPSCICD": [".github/workflows/ci.yml", ".github/workflows/release.yml", "tools/release.py", "tools/security_check.py", "tools/license_check.py"],
    "OPSDR": ["src/sip/lifecycle.py", "src/sip/exporting.py", "docs/operator/BACKUP_RESTORE.md", "tools/run_demo.py"],
    "OPSSEC": ["infrastructure/containers", "infrastructure/kubernetes/base", "tools/security_check.py", "docs/security/THREAT_MODEL.md"],
    "OPSSRE": ["docs/operator/INCIDENT_RESPONSE.md", "docs/runbooks/OPERATIONS_INCIDENTS.md", "docs/runbooks/OBSERVABILITY_INCIDENTS.md"],
    "OPSTHR": ["docs/security/THREAT_MODEL.md", "src/sip/security.py", "src/sip/worker_sandbox.py"],
    "OPSTHREA": ["docs/security/THREAT_MODEL.md", "src/sip/security.py", "src/sip/worker_sandbox.py"],
    "PLTAPI": ["src/sip/api.py", "schemas/openapi", "services"],
    "PLTGRPC": ["src/sip/worker_protocol.py", "src/sip/worker_runtime.py", "schemas/protobuf/worker.proto", "schemas/jsonschema/worker-lease.schema.json"],
    "PLTREST": ["src/sip/assets.py", "src/sip/api.py", "src/sip/audit.py", "src/sip/security.py"],
    "PLTAGENT": ["src/sip/agents.py", "src/sip/search.py", "src/sip/policy.py", "schemas/jsonschema/agent-tool.schema.json", "schemas/jsonschema/agent-answer.schema.json", "migrations/versions/0009_authorized_spatial_search_and_agents.py"],
    "PLTIO": ["src/sip/exporting.py", "src/sip/lifecycle.py", "tools/run_demo.py", "apps/web"],
    "PLTJOB": ["src/sip/operations.py", "src/sip/database.py", "migrations/versions/0005_worker_candidate_idempotency.py", "migrations/versions/0006_operation_trace_context.py"],
    "PLTMODEL": [
        "src/sip/model_governance.py",
        "src/sip/contracts.py",
        "src/sip/database.py",
        "governance/models",
        "schemas/jsonschema/model-manifest.schema.json",
        "migrations",
    ],
    "PLTSDK": ["src/sip/worker_manifest.py", "src/sip/worker_sandbox.py", "src/sip/worker_runtime.py", "workers", "infrastructure/kubernetes/base/deployments"],
    "PLTSQL": ["src/sip/spatial_query.py", "src/sip/search.py", "schemas/jsonschema/spatial-query.schema.json", "schemas/jsonschema/saved-query.schema.json", "schemas/openapi/search-service.openapi.json"],
    "PLTVIEW": ["apps/web", "src/sip/representations.py", "tools/run_demo.py"],
    "RECALIGN": ["src/sip/geometry.py", "src/sip/provider_sdk.py", "tools/run_benchmarks.py"],
    "RECBIDI": ["src/sip/geometry.py", "src/sip/provider_sdk.py", "src/sip/representations.py", "tools/run_demo.py"],
    "RECCLEAN": ["src/sip/hybrid.py", "src/sip/representations.py", "src/sip/geometry.py"],
    "SECEXT": ["src/sip/hybrid.py", "src/sip/contracts.py", "src/sip/model_governance.py", "src/sip/security.py", "src/sip/audit.py", "docs/security/THREAT_MODEL.md", "migrations/versions/0011_governed_hybrid_representation.py"],
    "RECHYB": ["src/sip/representations.py", "src/sip/scene.py", "apps/web", "tools/run_demo.py"],
    "RECMESH": ["src/sip/geometry.py", "src/sip/representations.py", "src/sip/scene.py", "tools/run_demo.py"],
    "RECPROV": ["src/sip/hybrid.py", "src/sip/contracts.py", "src/sip/worker_runtime.py", "src/sip/representations.py", "src/sip/database.py", "schemas/jsonschema/provider-capability.schema.json", "migrations/versions/0011_governed_hybrid_representation.py"],
    "SIPMIG": ["migrations", "src/sip/database.py", "src/sip/scene.py", "src/sip/assets.py"],
    "TSTGATE": ["src/sip/spec_lint.py", "tools/release.py", ".github/workflows/release.yml"],
    "TSTLAY": ["src/sip/capture.py", "src/sip/worker_sandbox.py", "tools/run_test_matrix.py", "tests/fixtures"],
    "TSTSEC": ["src/sip/capture.py", "src/sip/security.py", "src/sip/worker_sandbox.py", "tests/fixtures"],
    "TSTSTRAT": ["tools/run_test_matrix.py", "tools/update_requirements.py", "src/sip/spec_lint.py", "requirements/requirements-ledger.json"],
}

EXTERNAL_DETAILS = {
    "DELDEV-005": (
        "ML Platform / Release Engineering",
        "Run the documented GPU doctor on each supported NVIDIA driver/CUDA/container profile with an approved local checkpoint hash; retain driver, runtime, device, image, checkpoint, and pass/fail evidence.",
    ),
    "DATDB-004": (
        "Database Reliability Engineering",
        "Rehearse forward migration and recovery against a sanitized production-sized PostgreSQL/PostGIS copy, measure duration/locks/storage, validate rollback or forward-fix behavior, and retain environment and database integrity evidence.",
    ),
    "OPSDR-002": (
        "Site Reliability Engineering",
        "Configure production PostgreSQL point-in-time recovery and object-version backup, execute an isolated account-backed restore to a matched recovery point, measure RPO/RTO, and retain manifests, hashes, and reconciliation evidence.",
    ),
    "OPSSEC-005": (
        "Security Engineering / Mobile Release Engineering",
        "Build signed production containers and Apple mobile artifacts, execute vulnerability and hardening scans against their final digests, verify patch-SLA tracking, and retain scanner databases, signatures, and review evidence.",
    ),
}

CANONICAL_PYTHON_SUITES = (
    "contract",
    "integration",
    "migration",
    "security",
    "unit",
    "property",
    "privacy",
    "e2e",
    "acceptance",
    "spec",
)

SUPPLEMENTAL_EVIDENCE: dict[str, list[str]] = {
    "APPFAIL": ["build/reports/governance-check.json", "governance/failure-catalog.json"],
    "ARCADR": ["docs/adr/index.json", "build/reports/governance-check.json"],
    "ARCEVT": ["schemas/events/event-catalog.json", "build/reports/governance-check.json"],
    "ARCSVC": ["governance/service-catalog.json", "build/reports/governance-check.json"],
    "ARCHHYB": ["build/reports/tests/contract.xml", "build/reports/tests/integration.xml", "schemas/events/event-catalog.json"],
    "GOVOPEN": ["governance/open-questions.json", "build/reports/governance-check.json"],
    "GOVRISK": ["governance/risk-register.json", "build/reports/governance-check.json"],
    "ARCSYNC": ["build/reports/tests/unit.xml"],
    "ARCDEP": ["build/reports/infrastructure-static-validation.json"],
    "ARCOBS": ["build/reports/infrastructure-static-validation.json"],
    "CAPIOS": ["build/reports/swift-test-report.json", "build/evidence/swift-test-linux.log"],
    "CAPREC": ["build/reports/swift-test-report.json", "build/evidence/swift-test-linux.log"],
    "CAPSENS": ["build/reports/swift-test-report.json", "build/evidence/swift-test-linux.log"],
    "CAPQUAL": ["build/reports/swift-test-report.json", "build/evidence/swift-test-linux.log"],
    "CAPPRIV": ["build/reports/swift-test-report.json", "build/evidence/swift-test-linux.log"],
    "CAPSTRAT": ["build/reports/swift-test-report.json", "build/evidence/swift-test-linux.log"],
    "CAPSOP": ["build/reports/swift-test-report.json", "build/evidence/swift-test-linux.log"],
    "CAPCSCP": ["build/reports/swift-test-report.json", "build/evidence/swift-test-linux.log"],
    "CONHYB": ["src/sip/construction.py", "src/sip/collaboration.py", "src/sip/scene.py"],
    "CONMEAS": ["src/sip/construction.py", "src/sip/database.py", "src/sip/models.py"],
    "CONDEMO": ["build/evidence/demos/construction.json"],
    "DATANCH": ["build/reports/tests/integration.xml", "schemas/events/event-catalog.json"],
    "DATEVID": ["build/reports/tests/integration.xml", "schemas/events/event-catalog.json"],
    "DATFRAME": ["build/reports/tests/integration.xml", "schemas/events/event-catalog.json"],
    "DATGEOM": ["build/reports/tests/integration.xml", "schemas/events/event-catalog.json"],
    "DATGIT": ["build/reports/tests/integration.xml", "schemas/events/event-catalog.json"],
    "DATHYB": ["build/reports/tests/integration.xml", "build/evidence/demos/hybrid.json"],
    "DATTWIN": ["build/reports/tests/integration.xml", "schemas/events/event-catalog.json"],
    "DATSEARC": ["build/reports/tests/integration.xml", "schemas/openapi/search-service.openapi.json"],
    "GOVLIC": ["build/reports/license-gate.json", "build/reports/release-report.json"],
    "GOVETH": ["build/reports/tests/integration.xml", "schemas/events/event-catalog.json"],
    "HYBRUN": ["build/evidence/demos/hybrid.json"],
    "HYBTEST": ["build/evidence/demos/hybrid.json"],
    "LIFHYB": ["src/sip/liveforever.py", "src/sip/policy.py", "apps/web"],
    "LIFOVR": ["src/sip/liveforever.py", "src/sip/models.py", "src/sip/scene.py"],
    "LIFCONS": ["build/evidence/demos/liveforever.json"],
    "LIFDEMO": ["build/evidence/demos/liveforever.json"],
    "LIFTEST": ["build/evidence/demos/liveforever.json"],
    "OPSCOST": ["src/sip/lifecycle.py", "src/sip/operations.py", "src/sip/database.py"],
    "OPSAUDIT": ["build/reports/tests/integration.xml", "build/reports/tests/security.xml"],
    "OPSKEY": ["src/sip/lifecycle.py", "src/sip/assets.py", "docs/runbooks/KEY_ROTATION.md"],
    "OPSCICD": ["build/reports/release-report.json", "build/reports/security-report.json", "build/reports/license-gate.json"],
    "OPSDR": ["build/evidence/demos/foundation.json"],
    "OPSSEC": ["build/reports/security-report.json", "build/reports/infrastructure-static-validation.json"],
    "PLTAGENT": ["build/reports/tests/integration.xml", "build/reports/tests/security.xml", "schemas/jsonschema/agent-tool.schema.json", "schemas/jsonschema/agent-answer.schema.json"],
    "PLTREST": ["build/reports/tests/contract.xml", "build/reports/tests/unit.xml"],
    "PLTSQL": ["build/reports/tests/integration.xml", "build/reports/tests/contract.xml", "schemas/jsonschema/spatial-query.schema.json"],
    "PLTIO": ["build/evidence/demos/foundation.json"],
    "PLTMODEL": ["build/reports/license-gate.json", "build/reports/tests/integration.xml", "build/reports/tests/security.xml"],
    "PLTVIEW": ["build/evidence/demos/hybrid.json"],
    "RECALIGN": ["build/reports/benchmark-report.json"],
    "RECBIDI": ["build/evidence/demos/hybrid.json", "build/reports/benchmark-report.json"],
    "RECHYB": ["build/evidence/demos/hybrid.json"],
    "RECMESH": ["build/evidence/demos/hybrid.json"],
    "RECPROV": ["build/reports/tests/contract.xml", "build/reports/tests/integration.xml", "schemas/events/event-catalog.json"],
    "SECEXT": ["build/reports/tests/integration.xml", "build/reports/tests/security.xml", "build/reports/license-gate.json"],
    "SIPMIG": ["migrations", "src/sip/database.py", "src/sip/scene.py", "src/sip/assets.py"],
    "TSTGATE": ["build/reports/release-report.json", "build/reports/spec-lint.json"],
    "TSTSTRAT": ["build/reports/test-matrix.json"],
}


def _prefix(requirement_id: str) -> str:
    return requirement_id.rsplit("-", 1)[0]


def _python_tests_by_requirement() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            docstring = ast.get_docstring(node) or ""
            node_id = f"{path.relative_to(ROOT).as_posix()}::{node.name}"
            for requirement_id in REQ_PATTERN.findall(docstring):
                result.setdefault(requirement_id, []).append(node_id)
    return result


def _swift_tests_by_requirement() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    pattern = re.compile(r'@Test\("([^"\n]+)"\)')
    for path in sorted((ROOT / "apps/ios-capture/Tests").rglob("*.swift")):
        source = path.read_text(encoding="utf-8")
        for index, match in enumerate(pattern.finditer(source), start=1):
            label = match.group(1)
            node_id = f"{path.relative_to(ROOT).as_posix()}::swift-test-{index}:{label}"
            for requirement_id in REQ_PATTERN.findall(label):
                result.setdefault(requirement_id, []).append(node_id)
    return result


def _tests_by_requirement() -> dict[str, list[str]]:
    result = _python_tests_by_requirement()
    for requirement_id, test_ids in _swift_tests_by_requirement().items():
        result.setdefault(requirement_id, []).extend(test_ids)
    return {key: sorted(set(value)) for key, value in sorted(result.items())}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_source_tree_root() -> str:
    """Use the matrix runner's canonical source-tree algorithm without duplicating it."""
    path = ROOT / "tools/run_test_matrix.py"
    spec = importlib.util.spec_from_file_location("sip_traceability_source_hash", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load canonical source-tree hashing implementation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    return str(module._source_tree_root())


def _suite_report_is_current(suite: str, *, current_source_root: str) -> bool:
    report_root = ROOT / "build/reports/tests"
    junit = report_root / f"{suite}.xml"
    evidence = report_root / f"{suite}.evidence.json"
    if not junit.is_file() or not evidence.is_file():
        return False
    try:
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        result = payload["result"]
    except (json.JSONDecodeError, KeyError, OSError, TypeError):
        return False
    expected_junit = f"build/reports/tests/{suite}.xml"
    return bool(
        payload.get("schema") == "sip.test-suite-evidence/v1"
        and result.get("name") == suite
        and result.get("status") == "passed"
        and result.get("exit_code") == 0
        and result.get("failures") == 0
        and result.get("errors") == 0
        and result.get("source_tree_root_sha256") == current_source_root
        and result.get("junit_path") == expected_junit
        and result.get("junit_sha256") == _sha256_file(junit)
    )


def _python_test_results() -> dict[str, str]:
    """Read only current, source-bound canonical isolated-suite reports.

    Ad-hoc, staged, stale-source, and tampered JUnit files are intentionally
    excluded. A passing XML document cannot promote a requirement unless its
    canonical sidecar proves the exact current source root and JUnit digest.
    """
    results: dict[str, str] = {}
    report_root = ROOT / "build/reports/tests"
    current_source_root = _current_source_tree_root()
    for suite in CANONICAL_PYTHON_SUITES:
        path = report_root / f"{suite}.xml"
        if not _suite_report_is_current(suite, current_source_root=current_source_root):
            continue
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for case in root.iter("testcase"):
            classname = case.attrib.get("classname", "")
            name = case.attrib.get("name", "").split("[", 1)[0]
            if not classname.startswith("tests.") or not name:
                continue
            node_id = classname.replace(".", "/") + ".py::" + name
            status = "passed"
            if case.find("failure") is not None:
                status = "failed"
            elif case.find("error") is not None:
                status = "error"
            elif case.find("skipped") is not None:
                status = "skipped"
            results[node_id] = status
    return results


def _swift_report_passed() -> bool:
    path = ROOT / "build/reports/swift-test-report.json"
    if not path.is_file():
        return False
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return (
        report.get("status") in {"passed", "passed_complete", "passed_with_external_gaps"}
        and report.get("tests_failed") == 0
        and report.get("tests_passed", 0) > 0
    )


def _tests_passed(
    test_ids: list[str],
    *,
    python_results: dict[str, str] | None = None,
    swift_ok: bool | None = None,
) -> tuple[bool, list[str]]:
    python_results = _python_test_results() if python_results is None else python_results
    swift_ok = _swift_report_passed() if swift_ok is None else swift_ok
    missing_or_failed: list[str] = []
    for test_id in test_ids:
        if test_id.startswith("apps/ios-capture/Tests/"):
            if not swift_ok:
                missing_or_failed.append(test_id)
        elif python_results.get(test_id) != "passed":
            missing_or_failed.append(test_id)
    return not missing_or_failed, missing_or_failed

def _evidence_for(test_ids: list[str], prefix: str) -> list[str]:
    """Return the deterministic evidence contract, independent of build order.

    These are declarations in the committed traceability overlay.  The
    post-commit ``--check-evidence`` gate proves that every declared path exists
    and that canonical Python/Swift results are bound to the current source
    root.  Filtering on file existence here would make packaging or test order
    change the committed source map.
    """

    suites = sorted({test_id.split("/", 2)[1] for test_id in test_ids if test_id.startswith("tests/")})
    paths = ["build/reports/test-matrix.json"]
    paths.extend(f"build/reports/tests/{suite}.xml" for suite in suites)
    paths.extend(SUPPLEMENTAL_EVIDENCE.get(prefix, []))
    return sorted(set(paths))


def _status(requirement_id: str) -> str:
    if requirement_id in VERIFIED:
        return "VERIFIED"
    if requirement_id in IN_PROGRESS:
        return "IN_PROGRESS"
    if requirement_id in EXTERNAL:
        return "EXTERNAL_VALIDATION_REQUIRED"
    return "IMPLEMENTED_UNVERIFIED"


def test_result_snapshot_from_overlay(payload: dict[str, Any]) -> tuple[dict[str, str], bool]:
    """Reconstruct the result snapshot already embedded in a generated overlay.

    Contract tests use this snapshot to validate deterministic generation without
    reading the prior contract JUnit report that the current contract run will
    replace. The CLI intentionally does *not* use this helper: post-matrix
    `--check` remains the independent evidence freshness gate against canonical
    retained reports.
    """

    python_results: dict[str, str] = {}
    swift_statuses: list[bool] = []
    for requirement_id, overlay in sorted(payload.get("requirements", {}).items()):
        failed = set(overlay.get("failed_or_missing_test_evidence", []))
        for test_id in overlay.get("test_ids", []):
            passed = test_id not in failed
            if test_id.startswith("apps/ios-capture/Tests/"):
                swift_statuses.append(passed)
                continue
            status = "passed" if passed else "missing"
            previous = python_results.get(test_id)
            if previous is not None and previous != status:
                raise ValueError(
                    f"overlay has contradictory retained result for {test_id}: "
                    f"{previous} versus {status} ({requirement_id})"
                )
            python_results[test_id] = status
    return python_results, bool(swift_statuses) and all(swift_statuses)


def _declared_passing_results(test_map: dict[str, list[str]]) -> tuple[dict[str, str], bool]:
    python_results: dict[str, str] = {}
    swift_seen = False
    for test_ids in test_map.values():
        for test_id in test_ids:
            if test_id.startswith("apps/ios-capture/Tests/"):
                swift_seen = True
            else:
                python_results[test_id] = "passed"
    return python_results, swift_seen


def build(
    *,
    python_results: dict[str, str] | None = None,
    swift_ok: bool | None = None,
    declared_source_state: bool = False,
) -> dict[str, Any]:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    known = {item["requirement_id"] for item in baseline["requirements"]}
    test_map = _tests_by_requirement()
    unknown = sorted(set(test_map) - known)
    if unknown:
        raise ValueError(f"tests reference unknown requirement IDs: {unknown}")
    if declared_source_state:
        python_results, swift_ok = _declared_passing_results(test_map)
    overlays: dict[str, Any] = {}
    for requirement_id, test_ids in test_map.items():
        prefix = _prefix(requirement_id)
        status = _status(requirement_id)
        tests_passed, failed_or_missing_tests = _tests_passed(
            test_ids,
            python_results=python_results,
            swift_ok=swift_ok,
        )
        if status == "VERIFIED" and not tests_passed:
            status = "IMPLEMENTED_UNVERIFIED"
        files = [path for path in IMPLEMENTATION_GROUPS.get(prefix, []) if (ROOT / path).exists()]
        if not files:
            raise ValueError(f"no implementation files configured for {requirement_id}")
        evidence = _evidence_for(test_ids, prefix)
        if status == "VERIFIED" and not evidence:
            raise ValueError(f"verified requirement {requirement_id} has no retained evidence")
        overlay: dict[str, Any] = {
            "implementation_status": status,
            "implementation_files": files,
            "test_ids": test_ids,
            "test_result_evidence_paths": evidence,
            "owner": "SIP Engineering",
            "last_regression_result": "build/reports/test-matrix.json",
            "linked_tests_passed": tests_passed,
        }
        if failed_or_missing_tests:
            overlay["failed_or_missing_test_evidence"] = failed_or_missing_tests
        if status == "VERIFIED":
            overlay["notes"] = "Verified in the deterministic local reference profile by the exact linked automated test(s) and retained evidence; no external hardware, cloud, GPU, legal, or customer-pilot result is inferred."
        elif status == "EXTERNAL_VALIDATION_REQUIRED":
            owner, gap = EXTERNAL_DETAILS[requirement_id]
            overlay.update({"owner": owner, "external_validation_status": "REQUIRED", "notes": gap})
        elif status == "IN_PROGRESS":
            overlay["notes"] = "A controlled implementation/test boundary exists, but the normative requirement is broader than the retained evidence and remains in progress."
        else:
            overlay["notes"] = "Implementation and automated checks exist, but production-environment or full-scope evidence is incomplete; this requirement is intentionally not marked verified."
        overlays[requirement_id] = overlay
    return {
        "schema_version": "1.0",
        "requirements": overlays,
        "epics": {},
        "notes": (
            "Generated conservatively from explicit REQ-tagged tests. The committed overlay declares the exact "
            "tests and evidence paths that a post-commit evidence run must satisfy. VERIFIED remains authoritative "
            "only when tools/build_traceability_map.py --check-evidence passes for the same commit and source root."
        ),
    }


def _load_destination() -> dict[str, Any]:
    if not DESTINATION.is_file():
        raise ValueError("implementation traceability map is missing")
    return json.loads(DESTINATION.read_text(encoding="utf-8"))


def _missing_declared_evidence(payload: dict[str, Any]) -> list[str]:
    missing: set[str] = set()
    for overlay in payload.get("requirements", {}).values():
        for relative in overlay.get("test_result_evidence_paths", []):
            if not (ROOT / relative).exists():
                missing.add(relative)
    return sorted(missing)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="check deterministic source declarations without requiring post-commit evidence",
    )
    mode.add_argument(
        "--check-evidence",
        action="store_true",
        help="require current-source canonical test reports and every declared evidence artifact",
    )
    args = parser.parse_args()

    if args.check_evidence:
        payload = build()
        missing = _missing_declared_evidence(payload)
        if missing:
            raise SystemExit(
                "traceability evidence is incomplete; missing declared paths: " + ", ".join(missing)
            )
        status = "evidence_passed"
    else:
        payload = build(declared_source_state=True)
        status = "source_structure_passed" if args.check else "generated"

    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.check or args.check_evidence:
        if not DESTINATION.is_file() or DESTINATION.read_text(encoding="utf-8") != serialized:
            command = "tools/build_traceability_map.py"
            raise SystemExit(f"implementation traceability map drift detected; run {command}")
        print(json.dumps({"status": status, "requirements": len(payload["requirements"])}, sort_keys=True))
        return
    DESTINATION.write_text(serialized, encoding="utf-8")
    print(json.dumps({"status": status, "requirements": len(payload["requirements"])}, sort_keys=True))


if __name__ == "__main__":
    main()
