# Progress 08 Privacy-Safe Support Operations

Support access is customer-approved, exact-scope, purpose-bound, time-limited, independently approved, revocable, and audited. Support engineers do not receive unrestricted project browsing or raw-data access by default.

## Access request and approval

A request states tenant, project, resource IDs, telemetry types, classification, audience, purpose, named personnel, duration, and request hash. The requester cannot approve it. Approval creates an immutable grant; expiration or revocation fails closed. Scope and timing checks occur before querying, counting, matching, generating URLs, or building a bundle.

## Support bundle

A bundle defaults to versions, manifests, stable error codes, privacy-safe metrics, selected redacted logs, hardware/processing profile, and evidence references. It excludes raw media, unrestricted transcripts, secrets, biometrics, restricted facility data, and unrestricted signed URLs. Hardware fields use a controlled allowlist and cannot contain credentials.

Every archive member except `checksums.json` is listed exactly once with SHA-256. Required files, digest syntax, aggregate root, ZIP hash, safe paths, duplicate entries, symlinks, expansion limits, and unexpected files are independently verified. Idempotent replay reopens and revalidates current bytes.

## Ticket handling

Tickets retain tenant/project scope, correlation IDs, stable errors, severity, status, assignee, evidence references, and resolution. High-risk tickets require a specialized queue. Support actions use managed workspaces, never copy raw assets to unmanaged systems, and record incident actions rather than sensitive content.

## Revocation and expiry

Revoke a grant immediately on suspected exposure or customer request. Existing bundle access must fail after revocation or expiry. A replacement requires a new request, approval, and archive. Bundle verification alone is not authorization.
