# Scene Runtime Review Operations

## Purpose

This runbook covers durable viewer-session replay and governed temporal-comparison review in Progress 05. It does not authorize production deployment.

## Viewer sessions

A viewer session is immutable state, not a credential. It may contain scene commit IDs, representation roles, camera/navigation state, clipping planes, section boxes, selection, timeline, filters, redaction, and accessibility preferences. It must never contain bearer tokens, signed URLs, object-store keys, provider credentials, or reusable capability material.

Replay must authenticate the principal, re-evaluate tenant/project/purpose/audience/region policy, and issue new short-lived bindings. When a required representation is unavailable or no longer authorized, replay returns an explicit degraded reason rather than fabricating success.

## Temporal comparisons

Create comparisons only from exact existing commits in the same tenant, project, scene, and coordinate context. Retain registration quality, thresholds, evidence IDs, observed coverage, executable and parameter hashes, and all active or suppressed candidates.

Unobserved regions are never reported as removed. Differences caused by LOD, lighting, exposure, dynamic objects, or missing coverage remain suppressed or review-visible. Requesters and automated providers cannot approve their own candidates. Accepted reviews create semantic events; a separate controlled operation applies them to a new scene commit.

## Incident response

On a policy or provenance mismatch, deny replay or review and retain the stable error and audit record. On partial processing failure, preserve the prior scene commit, comparison record, and all evidence. Never rewrite or delete a prior comparison to make a new result appear successful.

## Verification

```bash
make migrations
make test
make demo-scene-runtime
```

The deterministic profile is synthetic and local. Browser, GPU, deployment, penetration, privacy, accessibility, and legal acceptance remain external.
