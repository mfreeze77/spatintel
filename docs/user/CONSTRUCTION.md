# Construction Spatial Reference User Guide

## Purpose

The Construction workspace links observations, design intent, evidence, systems, issues, measurements, and revisions to stable spatial entities. It supports field reference and handoff; it does not turn phone-derived geometry into survey, fabrication, code-compliance, or contract authority.

## Record states

Use the state that describes the evidence:

- `observed` — directly captured or documented;
- `inferred` — algorithmic or human inference;
- `design` — drawing/BIM intent;
- `proposed` — planned change;
- `measured` — numeric observation without independent verification;
- `verified` — reviewed measurement with required evidence;
- `disputed` — active conflict;
- `superseded` — retained historical record replaced by a later record.

Never overwrite a disputed or superseded record merely to make the current view cleaner.

## Verified measurement workflow

A field-verified value requires:

- units;
- uncertainty;
- source assets;
- calibration/instrument record;
- eligible metric representation or direct field source;
- verifier identity;
- verification date;
- intended use and limitations.

A pick on an interaction proxy first resolves to metric evidence. If that resolution fails, the UI must label the result non-authoritative.

## Systems and documents

The workspace supports fire-alarm, access-control, BAS, mechanical, and electrical entities and their tests/interconnections. Drawings, specifications, submittals, RFIs, photos, notes, cutsheets, and reports can attach to a page region, spatial anchor, semantic entity, or scene commit.

Sensitive systems may carry narrower spatial restrictions than the project around them. Redaction and permission are enforced on the server and on derivatives/exports.

## Deficiency and retest

1. Create a deficiency linked to entity and evidence.
2. Record severity and required correction.
3. Attach correction evidence.
4. Record retest procedure, result, tester, and artifacts.
5. Close only after the required result passes.
6. Preserve all prior states and timestamps.

## Handoff

BCF and IFC-oriented handoff manifests distinguish design and observed/verified state. The open preservation export includes semantic identity, evidence, scene history, policy summary, and checksums.

Run the synthetic workflow:

```bash
make demo-construction
```
