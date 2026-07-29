#!/usr/bin/env python3
"""Audit every requirement in the authorized Progress 06 vertical-MVP epic set."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "requirements/progress-06-traceability-audit.json"
SCOPE_DESTINATION = ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_06.json"
REQ_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]+-\d{3}\b")
AUTHORIZED_EPICS = (
    "CON-001", "CON-002", "CON-003", "CON-004", "CON-005",
    "LIF-001", "LIF-002", "LIF-003", "LIF-004",
)
DIRECT_VERIFIED = {
    "CONDEMO-004": "synthetic Construction demonstration records scan-estimate and independently field-verified measurement history",
    "CONDEMO-005": "synthetic Construction demonstration produces a reviewable changed-object semantic diff",
    "LIFDEMO-004": "synthetic LiveForever demonstration preserves generated reconstruction source coverage and generated-gap labeling",
    "LIFDEMO-005": "synthetic LiveForever demonstration presents alternate recollections without collapsing either account",
}
FAMILY_RATIONALE = {
    "DATBIM": "IFC/BCF identity, alignment, unsupported constructs, mappings, and truth labels are exercised in the deterministic reference profile; vendor interoperability remains broader",
    "CONOVR": "survey-to-owner-handoff API and workflow tests exercise the integrated Construction vertical; field/customer acceptance remains broader",
    "CONHIER": "hierarchy tests exercise stable places, coordinate frames, and system zones",
    "CONSURV": "survey and return-visit tests exercise planning, visit evidence, review, coverage, and exact-prior-commit continuity",
    "CONFA": "synthetic fire-alarm entity-pack tests exercise records and restricted export behavior without confidential facility data",
    "CONAC": "synthetic access-control entity-pack tests exercise openings, devices, associations, and restricted topology controls",
    "CONMEP": "synthetic MEP/BAS tests exercise equipment, points, interconnections, pathways, operational metadata, and redaction",
    "CONDOC": "document tests exercise immutable revisions, hashes, page regions, spatial links, RFIs, and review-required extraction",
    "CONQC": "issue and commissioning tests exercise correction, retest, verified closure, procedures, instruments, and restricted reporting",
    "CONMEAS": "reference tests exercise measurement authority fields; survey/certification evidence remains external",
    "CONPROG": "temporal comparison tests exercise coverage-aware change review without payment inference",
    "CONHAND": "owner-handoff tests exercise open offline access, checksums, redaction, and package verification",
    "CONREP": "deterministic report tests exercise truth labels, source view identity, redaction state, and stable content identity",
    "CONDEMO": "synthetic non-sensitive Construction pilot exercises the implemented reference workflow; physical field pilot remains broader",
    "CONHYB": "vertical workflow tests bind issue/commissioning and progress review to scene/evidence controls",
    "LIFOVR": "synthetic memory-room APIs exercise graph, evidence, consent, and generated-content boundaries; human-subject validation remains broader",
    "LIFGRAPH": "graph and immutable-revision tests exercise stable records, uncertainty, editions, corrections, audiences, and consent-aware access",
    "LIFINT": "interview tests exercise participants, consent, time-aligned transcripts, question lineage, private marks, pacing, and corrected reading layers",
    "LIFPLACE": "synthetic graph tests exercise people, places, objects, aliases, uncertainty, relationships, and unidentified references",
    "LIFMEDIA": "policy tests exercise audience and rights enforcement for synthetic media",
    "LIFPRES": "generated-presence and kill-switch tests exercise fail-closed high-risk behavior; approved voice/likeness execution is intentionally absent",
    "LIFREC": "governance tests exercise revocation/restriction behavior while broader inheritance and legal validation remain external",
    "LIFDISP": "conflict and correction tests preserve alternatives and sources without majority-vote factual promotion",
    "LIFCONS": "consent/governance tests exercise scope, revocation, succession limits, audiences, and dispute freezes; full legal review remains external",
    "LIFLABEL": "truth-label tests exercise retained lineage and static/offline legends",
    "LIFUX": "safe-experience tests exercise quiet mode, pause, captions, reduced motion, warning controls, and safe exit in the reference profile",
    "LIFEXP": "offline fallback tests exercise a non-proprietary, non-splat preservation experience",
    "LIFPRESV": "preservation tests exercise open packages, fixity, offline access, succession, format migration records, and shutdown controls",
    "LIFDEMO": "synthetic documented-consent memory-room pilot exercises the included workflow without private-family data or likeness/voice simulation",
    "LIFHYB": "generated-presence, provider, private-place, and safe-exit controls are exercised with synthetic/local data",
}


def _tests() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(ROOT).as_posix()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                result[f"{relative}::{node.name}"] = set(REQ_PATTERN.findall(ast.get_docstring(node) or ""))
    return result


def _scope_requirements(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    epic_set = set(AUTHORIZED_EPICS)
    return sorted(
        [item for item in ledger["requirements"] if epic_set.intersection(item.get("epic_ids", []))],
        key=lambda item: item["requirement_id"],
    )


def _classification(record: dict[str, Any]) -> tuple[str, str]:
    requirement_id = record["requirement_id"]
    status = record["implementation_status"]
    if status == "NOT_STARTED":
        return "deferred", "The requirement remains explicitly NOT_STARTED in this bounded checkpoint and is not claimed by Progress 06."
    if requirement_id in DIRECT_VERIFIED:
        return "direct", DIRECT_VERIFIED[requirement_id]
    prefix = requirement_id.rsplit("-", 1)[0]
    return "partial", FAMILY_RATIONALE.get(
        prefix,
        "The linked deterministic tests exercise an applicable implementation boundary, but the normative requirement is broader than retained local evidence.",
    )


def build() -> dict[str, Any]:
    ledger = json.loads((ROOT / "requirements/requirements-ledger.json").read_text(encoding="utf-8"))
    implementation = json.loads((ROOT / "requirements/implementation-map.json").read_text(encoding="utf-8"))["requirements"]
    tests = _tests()
    findings: list[dict[str, Any]] = []
    audited: list[dict[str, Any]] = []
    scope = _scope_requirements(ledger)
    for record in scope:
        requirement_id = record["requirement_id"]
        classification, rationale = _classification(record)
        linked = list(implementation.get(requirement_id, {}).get("test_ids", []))
        declarations: list[dict[str, Any]] = []
        for test_id in linked:
            declared = tests.get(test_id)
            valid = declared is not None and requirement_id in declared
            declarations.append({
                "test_id": test_id,
                "test_exists": declared is not None,
                "declares_requirement_id": valid,
                "declared_requirement_ids": sorted(declared or []),
            })
            if declared is None:
                findings.append({"code": "LINKED_TEST_MISSING", "requirement_id": requirement_id, "test_id": test_id})
            elif requirement_id not in declared:
                findings.append({"code": "TEST_DOES_NOT_DECLARE_REQUIREMENT", "requirement_id": requirement_id, "test_id": test_id})
        status = record["implementation_status"]
        if classification == "deferred" and status != "NOT_STARTED":
            findings.append({"code": "DEFERRED_STATUS_MISMATCH", "requirement_id": requirement_id, "status": status})
        if classification == "deferred" and linked:
            findings.append({"code": "DEFERRED_REQUIREMENT_HAS_CLAIMED_TEST", "requirement_id": requirement_id})
        if classification != "deferred" and status == "NOT_STARTED":
            findings.append({"code": "IMPLEMENTED_STATUS_MISMATCH", "requirement_id": requirement_id})
        if status == "VERIFIED" and classification != "direct":
            findings.append({"code": "VERIFIED_WITHOUT_DIRECT_COVERAGE", "requirement_id": requirement_id})
        if status == "VERIFIED" and not linked:
            findings.append({"code": "VERIFIED_WITHOUT_LINKED_TEST", "requirement_id": requirement_id})
        audited.append({
            "requirement_id": requirement_id,
            "epic_ids": sorted(set(record.get("epic_ids", [])).intersection(AUTHORIZED_EPICS)),
            "status": status,
            "coverage_classification": classification,
            "semantic_rationale": rationale,
            "verification_method": record.get("verification_method"),
            "linked_tests": declarations,
            "linked_test_count": len(linked),
            "all_linked_tests_declare_requirement_id": all(item["declares_requirement_id"] for item in declarations),
        })
    return {
        "schema": "sip.progress-06-traceability-audit/v1",
        "milestone": "Progress 06 vertical MVPs",
        "authorized_epics": list(AUTHORIZED_EPICS),
        "scope_requirement_count": len(scope),
        "audited_requirements": audited,
        "findings": findings,
        "finding_count": len(findings),
        "status": "passed_complete" if not findings else "failed",
        "production_authorized": False,
        "progress_07_authorized": False,
    }


def build_scope() -> dict[str, Any]:
    ledger = json.loads((ROOT / "requirements/requirements-ledger.json").read_text(encoding="utf-8"))
    scope = _scope_requirements(ledger)
    included: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for record in scope:
        classification, rationale = _classification(record)
        item = {
            "requirement_id": record["requirement_id"],
            "priority": record["priority"],
            "epic_ids": sorted(set(record.get("epic_ids", [])).intersection(AUTHORIZED_EPICS)),
            "status": record["implementation_status"],
            "requirement": record["text"],
            "verification_method": record["verification_method"],
            "coverage_classification": classification,
            "scope_rationale": rationale,
            "implementation_files": record.get("implementation_files", []),
            "test_ids": record.get("test_ids", []),
            "evidence_paths": record.get("test_result_evidence_paths", []),
        }
        (deferred if classification == "deferred" else included).append(item)
    from collections import Counter
    return {
        "schema": "sip.milestone-scope/v1",
        "milestone": "Progress 06 vertical MVPs",
        "accepted_base_commit": "66b9a804217aa3b5814283777f5cf68424e4a4b5",
        "authorized_epics": list(AUTHORIZED_EPICS),
        "scope_statement": (
            "Progress 06 implements bounded synthetic/non-sensitive Construction Spatial Reference and "
            "LiveForever vertical MVP workflows. Requirements remain individually statused; closing this "
            "checkpoint does not promote included requirements to VERIFIED."
        ),
        "included_requirements": included,
        "deferred_requirements": deferred,
        "counts": {
            "total": len(scope),
            "included": len(included),
            "deferred": len(deferred),
            "included_by_status": dict(sorted(Counter(item["status"] for item in included).items())),
            "deferred_by_status": dict(sorted(Counter(item["status"] for item in deferred).items())),
        },
        "acceptance_criteria": [
            "all 1,028 requirements remain in the ledger",
            "every linked Progress 06 test exists and declares the linked requirement ID",
            "all locally executable final-source tests and gates pass with retained evidence",
            "Construction and LiveForever synthetic demonstrations, open export, and independent restore pass",
            "source is committed before clean-detached acceptance and packaging",
            "inner and outer checkpoint verifiers return passed_complete with zero findings",
            "external gaps remain explicit and production remains NO-GO",
        ],
        "external_gaps": [
            "frozen Node/pnpm install and production web build",
            "mounted viewer/browser accessibility audit",
            "Xcode, ARKit, LiDAR, and physical-device acceptance",
            "approved LingBot checkpoint, model rights, CUDA/GPU, and real-scene validation",
            "executable Docker, Kubernetes, Terraform, and credentialed cloud recovery",
            "independent penetration, privacy, usability, accessibility, and legal review",
            "customer construction pilot and documented-consent human-subject LiveForever pilot",
            "complete IFC/BCF vendor interoperability and field measurement/survey certification",
        ],
        "milestone_result": "implementation_checkpoint_candidate",
        "production_authorized": False,
        "progress_07_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    audit = build()
    scope = build_scope()
    audit_rendered = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    scope_rendered = json.dumps(scope, indent=2, sort_keys=True) + "\n"
    if args.check:
        drift = (
            not DESTINATION.is_file() or DESTINATION.read_text(encoding="utf-8") != audit_rendered
            or not SCOPE_DESTINATION.is_file() or SCOPE_DESTINATION.read_text(encoding="utf-8") != scope_rendered
        )
        if drift:
            raise SystemExit("Progress 06 scope/traceability drift detected; run tools/audit_progress06_traceability.py")
    else:
        DESTINATION.write_text(audit_rendered, encoding="utf-8")
        SCOPE_DESTINATION.write_text(scope_rendered, encoding="utf-8")
    print(json.dumps({
        "status": audit["status"],
        "requirements": audit["scope_requirement_count"],
        "included": scope["counts"]["included"],
        "deferred": scope["counts"]["deferred"],
        "findings": audit["finding_count"],
    }, sort_keys=True))
    raise SystemExit(0 if audit["status"] == "passed_complete" else 1)


if __name__ == "__main__":
    main()
