from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from sip.api import create_app
from sip.context import PlatformContext, temporary_settings

ROOT = Path(__file__).parents[2]


@pytest.mark.contract
def test_json_schemas_are_valid_draft_2020_12() -> None:
    schemas = list((ROOT / "schemas" / "jsonschema").glob("*.json")) + list((ROOT / "schemas" / "events").glob("**/*.schema.json"))
    assert len(schemas) >= 30
    for path in schemas:
        schema = json.loads(path.read_text())
        jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.contract
def test_generated_openapi_matches_runtime_and_has_unique_operations(tmp_path: Path) -> None:
    generated = json.loads((ROOT / "schemas" / "openapi" / "all.openapi.json").read_text())
    context = PlatformContext.create(temporary_settings(tmp_path))
    try:
        runtime = create_app(context=context, service_name="all").openapi()
    finally:
        context.database.dispose()
    assert generated == runtime
    operation_ids = [
        operation["operationId"]
        for path_item in generated["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operation_ids) == len(set(operation_ids))



@pytest.mark.contract
def test_protobuf_contracts_are_versioned_and_never_reuse_field_numbers() -> None:
    for path in (ROOT / "schemas" / "protobuf").glob("*.proto"):
        text = path.read_text()
        assert 'syntax = "proto3";' in text
        assert "package sip.v1;" in text
        for block in text.split("message ")[1:]:
            body = block.split("}", 1)[0]
            numbers = []
            for line in body.splitlines():
                if "=" in line and ";" in line:
                    value = line.split("=", 1)[1].split(";", 1)[0].strip()
                    if value.isdigit():
                        numbers.append(int(value))
            assert len(numbers) == len(set(numbers)), f"duplicate field number in {path}"

@pytest.mark.contract
def test_worker_contracts_are_exposed_in_protobuf_typescript_and_python() -> None:
    """REQ: PLTGRPC-001, PLTSDK-003, HYBAPI-003, HYBAPI-004."""
    proto = (ROOT / "schemas/protobuf/worker.proto").read_text()
    for required in (
        "rpc AcquireLeaseV1",
        "rpc ReportProgressV1",
        "rpc CompleteCandidateV1",
        "message WorkerLeaseV1",
        "message WorkerProgressRecordV1",
        "message RepresentationCandidateSummaryV1",
        "message WorkerReceiptSummaryV1",
    ):
        assert required in proto
    assert "geometry" not in proto.lower()
    assert "media_bytes" not in proto

    typescript = (ROOT / "packages/contracts/typescript/src/index.ts").read_text()
    for required in (
        "export interface WorkerManifest",
        "export interface WorkerLease",
        "export interface WorkerProgressRecord",
        "export interface RepresentationCandidatePackage",
        "export interface WorkerReceipt",
        'publication_permission: false;',
        'state: "quarantined";',
    ):
        assert required in typescript

    python_contracts = (ROOT / "packages/contracts/python/__init__.py").read_text()
    for required in ("WorkerManifest", "WorkerLease", "CandidatePackage", "WorkerReceipt"):
        assert required in python_contracts

@pytest.mark.contract
def test_representation_contract_rejects_authority_drift_for_interaction_proxies() -> None:
    """REQ: RECHYB-002, DATHYB-004 public contracts require exact proxy authority and disposability."""
    from pydantic import ValidationError as PydanticValidationError

    from sip.contracts import RepresentationAssetContract

    base = {
        "representation_id": "rep-proxy",
        "scene_id": "scene",
        "asset_id": "asset",
        "kind": "interaction",
        "provider_id": "local-proxy",
        "provider_version": "1.0.0",
        "coordinate_frame_id": "world",
        "source_class": "generated",
        "authority_class": "derived_non_authoritative",
        "authority_ceiling": "derived_non_authoritative",
        "disposable": True,
        "lossy": True,
        "intended_uses": ["picking"],
        "prohibited_uses": ["verified_measurement"],
        "quality": {},
        "provenance": {"source_ids": ["metric-representation"]},
        "support_map": {},
        "state": "quarantined",
    }
    accepted = RepresentationAssetContract.model_validate(base)
    assert accepted.authority_class.value == "derived_non_authoritative"
    assert accepted.authority_ceiling.value == "derived_non_authoritative"
    assert accepted.disposable is True

    for patch in (
        {"authority_class": "visual"},
        {"authority_ceiling": "metric"},
        {"disposable": False},
        {"authority_class": "interaction"},
    ):
        with pytest.raises(PydanticValidationError):
            RepresentationAssetContract.model_validate({**base, **patch})
