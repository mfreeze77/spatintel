---
spec_id: APP-LIC
title: "Dependency and License Decision Matrix"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: appendix
normative: false
---
# Dependency and License Decision Matrix

Statuses:

- **APPROVED-CANDIDATE:** permissive or manageable license observed; still requires exact revision, notices, dependency/SBOM, security, and counsel/process approval.
- **CONDITIONAL:** usable only with a specific checkpoint, build, boundary, customer/purpose, or license condition.
- **RESEARCH-HOLD:** experimentation only; commercial output blocked.
- **EXCLUDED-DEFAULT:** not included in the default proprietary distribution.
- **VERIFY:** not enough evidence in this audit.

| Component | Artifact type | Observed license/terms | Status | Required control |
|---|---|---|---|---|
| LingBot-Map repository | code | Apache-2.0 stated | APPROVED-CANDIDATE | Pin commit; retain LICENSE/NOTICE; audit dependencies and patches. |
| LingBot-Map checkpoint | weights | clear checkpoint license not confirmed in audited model card | RESEARCH-HOLD | Obtain written terms/provenance; hash; purpose approval. |
| VGGT repository code | code | updated commercial-friendly terms with military-use restriction | CONDITIONAL | Review exact license and product/customer restrictions. |
| VGGT-1B original | weights | CC BY-NC 4.0 model card | EXCLUDED-DEFAULT | No commercial processing. |
| VGGT-1B-Commercial | weights | separate acceptable-use license; non-military commercial use described | CONDITIONAL | Apply/accept terms; record approval and prohibited uses. |
| PolyCam/polyform | code/format tooling | MIT | APPROVED-CANDIDATE | Pin commit, notices, fixture tests. |
| ARKit-Scanner | code reference | Apache-2.0 | APPROVED-CANDIDATE | Review dependencies and Apple SDK use. |
| SwiftUI-LiDAR | code reference | MIT | APPROVED-CANDIDATE | Treat as scaffold; security/quality rewrite as needed. |
| Area-Target-Scanner | code reference | Apache-2.0 | APPROVED-CANDIDATE | Audit dependencies, supported platforms, and data flow. |
| ReScan/noncommercial scanners | code | noncommercial variants observed | EXCLUDED-DEFAULT | Ideas only; no code reuse without separate permission. |
| Open3D | code/library | MIT | APPROVED-CANDIDATE | Pin build; audit optional dependencies. |
| GTSAM | code/library | BSD family | APPROVED-CANDIDATE | Pin stable release and dependencies. |
| Ceres Solver | code/library | Apache-2.0 | APPROVED-CANDIDATE | Retain notices; pin numerical stack. |
| RTAB-Map | code/library/service | BSD; optional nonfree build caveats | CONDITIONAL | Build without nonfree components; retain full build manifest. |
| COLMAP | code/tool | BSD; third-party licenses | CONDITIONAL | Audit feature libraries and redistribution. |
| ORB-SLAM3 | code | GPLv3 unless commercial arrangement | EXCLUDED-DEFAULT | Separate licensed service/product decision only. |
| gsplat | code/library | Apache-2.0 | APPROVED-CANDIDATE | Preferred splat core after dependency audit. |
| Nerfstudio | code/tooling | Apache-2.0 | APPROVED-CANDIDATE | Optional tooling; audit included methods/models. |
| Graphdeco Gaussian Splatting | code | custom/research restrictions | EXCLUDED-DEFAULT | Do not ship in commercial core without permission. |
| IfcOpenShell | code/library | LGPL-3.0-or-later | CONDITIONAL | Counsel review; dynamic/service boundary; source/notice obligations. |
| OpenUSD | code/library | exact official license file and third parties must be reviewed | VERIFY | Pin release; retain license/notice; audit build options. |
| PostgreSQL | database | PostgreSQL License | APPROVED-CANDIDATE | Standard notice/security lifecycle. |
| PostGIS | extension | verify exact code license and packaged dependencies | CONDITIONAL | Use stable release; record GEOS/PROJ/SFCGAL build. |
| Three.js/React/Next.js/FastAPI | application frameworks | commonly permissive; exact lockfile required | APPROVED-CANDIDATE | SBOM, lock, notices, vulnerability policy. |
| Apple ARKit/RoomPlan/RealityKit | platform SDK | Apple SDK/platform terms | CONDITIONAL | Comply with SDK, App Store/distribution, privacy manifests. |
| Hosted OCR/LLM/speech/voice APIs | service | provider-specific terms | VERIFY | DPA, no-training setting, region, retention/deletion, output rights, subprocessors. |

## CI gate logic

A build or production job fails when any included executable, model, auxiliary asset, or service has:

- no manifest;
- missing source/revision/hash;
- status `RESEARCH-HOLD`, `EXCLUDED-DEFAULT`, expired, or revoked;
- purpose/customer/region mismatch;
- missing required attribution/notice;
- unknown runtime download;
- license change not reviewed;
- unapproved training or output-use term.

## Model manifest minimum

```yaml
model_id: robbyant-lingbot-map-long
revision: exact-provider-revision
checkpoint_sha256: REQUIRED
source_repository: https://github.com/Robbyant/lingbot-map
source_commit: "{LINGBOT_COMMIT}"
license_evidence:
  code: licenses/lingbot-code-apache-2.0.txt
  checkpoint: REQUIRED
  upstream_weights: REQUIRED
permitted_purposes: []
prohibited_purposes: []
approved_data_classes: []
approved_deployments: []
approval_status: research_hold
approved_by: null
review_expires_at: null
container_digest: REQUIRED
preprocessor_hashes: []
benchmark_report: null
```

## Version 1.1 candidate additions

The matrix shall track exact revisions and independent posture for PlayCanvas SplatTransform, Spark, MILo, FastGS/Fast-PGSR, Mesh2Splat, SuGaR, 2DGS, PGSR, and any manual web tool. The current evidence snapshot and provisional status are in [`989_splat_surface_research_and_dependency_audit.md`](989_splat_surface_research_and_dependency_audit.md). Top-level licenses do not settle submodule, checkpoint, dataset, patent, sample-asset, or output rights.
