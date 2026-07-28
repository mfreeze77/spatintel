from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SPEC_SHA256 = "84b570464b98b1baf3107789af22edad2a14086e5420df35a961f5fb16980bb8"


@pytest.mark.contract
def test_authoritative_specification_and_requirement_index_are_complete() -> None:
    """REQ: GOVDOC-001 authoritative specification bytes and every normative requirement remain indexed."""
    archive = ROOT / "spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == EXPECTED_SPEC_SHA256
    markdown = list((ROOT / "spec/Spatial-Intelligence-Platform-Spec-v1.1").rglob("*.md"))
    assert len(markdown) == 164
    ledger = json.loads((ROOT / "requirements/requirements-ledger.json").read_text(encoding="utf-8"))
    requirements = ledger["requirements"]
    assert len(requirements) == 1028
    identifiers = [item["requirement_id"] for item in requirements]
    assert len(identifiers) == len(set(identifiers))
    assert all(item["source_document"] and item["source_line"] > 0 for item in requirements)
