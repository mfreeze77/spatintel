# Construction Spatial Reference Vertical

This vertical composes the canonical SIP scene, evidence, spatial-truth, collaboration, hybrid-representation, search, export, and policy services into a construction/facility reference product.

It preserves the distinction between design intent, observed conditions, inferred conditions, proposed work, measurements, field verification, disputes, and superseded records. Phone/LiDAR-derived geometry is never labeled survey-grade, fabrication-ready, code-compliant, contract-authoritative, or verified as-built without independent evidence.

## Entry points

- Domain implementation: `src/sip/construction.py`
- HTTP surface: `src/sip/api.py`
- User guide: `docs/user/CONSTRUCTION.md`
- Deterministic demonstration: `make demo-construction`
- Synthetic corpus: `tests/fixtures/construction/synthetic-project.json`
- Preservation/export implementation: `src/sip/exporting.py`

The manifest in this directory records the vertical's required platform capabilities and fail-closed authority rules.
