# Progress 11 Roadmap Evidence

Progress 11 implements only the bounded **QA-002 dual-vertical acceptance and release-gate** milestone. The governing roadmap is machine-readable in `requirements/PROGRESS_11_ROADMAP.json`; this document explains its evidence posture without expanding scope.

## Dependency order

1. **Local release qualification** depends on accepted Progress 10, a frozen QA-002 scope, synthetic/non-sensitive fixtures, and exact-commit evidence. It adds one governed release-assurance control plane rather than a parallel product fork.
2. **External evidence closure** depends on approved frozen web tooling, physical-device/GPU/cloud environments, and independent reviewers. Local and synthetic evidence never substitutes for those controls.
3. **Future pilot readiness** requires separate True North authorization, customer or subject consent, external security/privacy/legal review, an operating envelope, support, and rollback. Progress 11 does not authorize a pilot.

## Reversibility and open paths

Every roadmap item names prerequisites, customer outcome, architecture impact, risks, acceptance, and deprecation or migration implications. The current checkpoint remains reversible through append-only migration `0021`, retained Progress 10 recovery evidence, open preservation exports, and an independently verified rollback rehearsal. Local CPU/reference providers, semantic fallback, static/offline viewers, and open export remain available when external providers or runtimes are unavailable.

## Evidence used for roadmap decisions

Future changes must be justified by retained evidence, including benchmark results, capacity and cost reports, support burden, consent incidents, security/privacy incidents, and separately authorized pilot evidence. Research spikes are time-bounded and must produce a decision; they may not become permanent forks by default.

## Known limits and governing posture

The roadmap does not claim completion of mounted-browser accessibility, physical iOS/LiDAR validation, approved LingBot/GPU execution, credentialed cloud deployment or disaster recovery, independent penetration/privacy/legal review, or customer/human-subject pilots. These remain explicit external gaps.

```text
Progress 11: delivered only after exact-commit acceptance and independent package verification
Progress 12: unauthorized
Production promotion: NO-GO
Production authorized: false
```
