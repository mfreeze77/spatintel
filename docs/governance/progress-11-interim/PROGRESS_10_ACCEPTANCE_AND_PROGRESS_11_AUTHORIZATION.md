# SIP v1.1.0 Progress 10 — True North Acceptance and Progress 11 Authorization

**Decision date:** 2026-07-31  
**Authority:** True North milestone governance

## Decision

- **Progress 10 checkpoint:** accepted
- **Progress 10 milestone:** closed
- **Progress 11:** authorized as a bounded development milestone
- **Progress 12:** unauthorized
- **Production promotion:** NO-GO
- **Production authorized:** false

## Accepted identities

```text
Outer ZIP SHA-256:
1e0c962a59a55a2a6395179c98467778ff56e2e394319b0ca46367551b5027dc

Outer payload content root:
d2c359b3ac9efd9bf47d0dda99bfc64afb13a3b1e153d45cfb99e86e467c5599

Inner ZIP SHA-256:
46d850b6035d0ee86386ff256aabdc65751d49398f6ea4e4084eb4d50d6c669c

Inner content root:
5f966fc2db234858cf75403c5a70dc804fb018d5be7d53bcab4d35ff23886f67

Accepted source commit:
ab409f6ac7ca583535f69e5806b7a3bdbfe08214

Git tree:
ced38981c7f41891a9c1288b789400b597a28b44

Accepted Progress 09 ancestor:
f293d6425182ef04f5893275724e2a4bd28cf00e

Canonical source root:
0c93009874f99c72c3670d6cfca47af00ff04b762e4f4ddddffa20ab03ed8678
```

## Independent verification

Fresh dedicated verifier executions against the submitted bytes returned:

```text
Inner verifier:
passed_complete — 0 findings

Outer verifier:
passed_complete — 0 findings

Fresh nested verification:
passed_complete — 0 findings
```

The Git bundle cloned cleanly on branch `progress-10-recovery`. The cloned checkout matched the claimed commit and tree, remained clean, and proved `f293d6425182ef04f5893275724e2a4bd28cf00e` is an ancestor of the accepted Progress 10 commit.

## Exact-commit acceptance retained

```text
Python:
455 passed
0 failed
0 errors
0 skipped

Swift Linux fixtures:
13 passed

Web browser-independent runtime:
14 passed

Web source/accessibility checks:
35 passed

Desktop review:
17 passed

Required local failures:
0

Overall acceptance:
passed_with_external_gaps

Production authorized:
false

Progress 11 authorized in submitted checkpoint:
false
```

A fresh targeted Progress 10 suite was initiated during True North review but exceeded the execution window without producing a contradictory failure. It is not substituted for, or represented as stronger than, the authoritative exact-commit 455-test matrix.

## Milestone truth

Progress 10 remained bounded to:

```text
OPS-004 — Backup, restore, disaster recovery, retention, and deletion
```

Scope accounting:

```text
Included requirements: 45
Deferred requirements: 0
Traceability findings: 0
```

The checkpoint preserves all 1,028 normative requirements and leaves `PLTVIEW-007` as `IMPLEMENTED_UNVERIFIED`.

Migration `0020_progress10_recovery_retention` is append-only over `0019_progress09_deployment_profiles`; prior migrations were not rewritten.

## Basis for closure

Progress 10 is accepted because the submission demonstrates all required checkpoint-control properties:

1. exact package hashes reproduce;
2. inner and outer manifests and aggregate roots verify;
3. fresh dedicated verifiers pass with zero findings;
4. the outer verifier performs fresh nested inner verification;
5. Git ancestry from accepted Progress 09 is proven;
6. commit, tree, source archive, and source manifests reconcile;
7. acceptance is bound to a clean detached exact commit;
8. scope remains limited to authorized OPS-004 work;
9. requirement status and traceability remain conservative;
10. local and synthetic recovery evidence is not misrepresented as production disaster-recovery certification;
11. production and the next milestone remained denied throughout the submitted checkpoint.

## Progress 11 authorization

Progress 11 is authorized only for:

```text
QA-002 — Dual vertical acceptance and release gates
```

The next worker shall begin from:

```text
ab409f6ac7ca583535f69e5806b7a3bdbfe08214
```

### Authorized bounded work

Progress 11 may implement and test:

- the complete Construction hybrid-reference acceptance scenario;
- independent dimensions and measurement-authority checks;
- protected-device inventory and restricted-data handling;
- proxy replacement and design-overlay behavior;
- the complete LiveForever navigable-memory acceptance scenario;
- consented stories, conflicting recollections, generated labels, evidence view, and safe locomotion;
- offline export and independent restore;
- license and model-rights gates;
- security and privacy gates;
- accessibility gates;
- load, backup/restore, migration, and rollback gates;
- known limitations and operating-envelope documentation;
- support and escalation plans;
- release manifest, checksums, recovery instructions, and rollback instructions;
- append-only migrations required strictly for QA-002 evidence or release-control records;
- exact milestone scope, traceability, clean-detached acceptance, and independently verified packaging.

### Mandatory stop-lines

Progress 11 shall not convert unavailable external evidence into a passing release claim.

The accepted checkpoint must distinguish:

- locally executed acceptance;
- browser-independent or source-level checks;
- mounted browser/runtime execution;
- physical iOS/LiDAR/device execution;
- credentialed cloud execution;
- externally witnessed review;
- customer or human-subject pilot evidence;
- production certification.

All P0 requirements included in QA-002 must either pass with direct evidence or remain explicitly blocked/deferred with production authorization false.

### Required adversarial evidence

The Progress 11 accepted exact-commit matrix shall directly test at least:

- proxy geometry cannot satisfy authoritative measurement;
- hidden or unauthorized layers cannot be picked or queried;
- restricted construction records cannot leak through search, counts, facets, exports, or support bundles;
- LiveForever consent revocation propagates to editions, derivatives, exports, and caches;
- generated or artistic material remains visibly labeled;
- conflicting recollections remain preserved;
- quiet mode, safe exit, captions, reduced motion, and evidence mode remain available;
- rollback restores the prior release state without data loss;
- backup/restore and migration gates reconcile hashes and provenance;
- offline exports open independently without proprietary services;
- release manifests reject stale, incomplete, mismatched, or unsigned evidence;
- production promotion fails closed while any required external gate is absent.

### Explicitly unauthorized

Progress 11 does not authorize:

- production credentials;
- production traffic;
- production promotion;
- customer Construction pilots;
- human-subject or family LiveForever pilots;
- PILOT-001;
- Progress 12;
- claims of physical-device, cloud, legal, accessibility, privacy, or production acceptance not backed by executed evidence.

## Governing posture

```text
Progress 10:
ACCEPTED AND CLOSED

Progress 11:
AUTHORIZED — QA-002 ONLY

Progress 12:
UNAUTHORIZED

Production:
NO-GO

Production authorized:
false
```
