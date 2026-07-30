# Progress 07 security operations runbook

## Privileged access

Use phishing-resistant MFA, request only explicit actions and resource scope, require an independent `jit_approver`, and limit grants to 60–3600 seconds. Revoke immediately when the incident or maintenance purpose ends. Wildcard actions are rejected.

## Workload identities

Issue 30–900 second credentials bound to tenant, project, audience, purpose, and explicit scopes. Validate every use. Revoke the grant rather than relying only on token expiry. Production workers have default-deny arbitrary egress and cannot download models at runtime.

## Provider incident withdrawal

Record the provider, sources, derivatives, publications, caches, exports, investigation evidence, and notification decision. Disable the provider, block publication, invalidate derivative surfaces, withdraw exports, and preserve investigation evidence. The workflow must not embed raw customer content in the incident summary.

## Immersive safety

Failure of accepted scale, walkability, openings, stairs/falls, safe spawn, or safe exit disables affected locomotion. Orbit or a static semantic view remains available as the safe fallback.

## Release posture

A candidate release record binds mobile, web, services, workers, infrastructure, models, schemas, and database manifests to test, security, privacy, license, SBOM, benchmark, migration, backup/restore, and acceptance evidence. Promotion remains denied unless the production control plane, signatures, environment policy, and all production-blocking controls pass.
