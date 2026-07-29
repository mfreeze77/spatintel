# Construction Owner Handoff

## Required package contents

A verified owner handoff identifies its scope and accepted scene commit and contains checksummed inventory, verified attributes, exact document revisions, test and commissioning records, warranties, training records, open issues, exclusions, reports, representation manifests, audience profiles, offline viewer assets, limitations, and validation results.

## Open and offline access

The package must preserve core owner records in open JSON/CSV/HTML or documented interchange formats and must remain readable without the production SIP service. The offline viewer is read-only and may not silently elevate observation to verification. Every representation carries its authority label.

## Redaction

Owner and technical audience profiles are generated independently. Restricted fire-alarm network details, access-control topology, controller settings, credential context, programming records, personal information, and security-zone relationships are removed unless the recipient is expressly authorized. Redaction occurs before packaging and is covered by the package checksums.

## Verification procedure

1. Verify the package root hash and every member hash.
2. Reject unsafe paths, duplicates, symlinks, nonregular members, size-limit violations, and compression-ratio abuse.
3. Open the offline viewer with network disabled.
4. Confirm room, equipment, issue, document, and test records can be located.
5. Confirm sensitive fields are absent from the owner profile.
6. Confirm design, observed, inferred, measured, verified, disputed, and unresolved values remain distinguishable.
7. Retain the verification report, tool version, source commit, environment, and package hash.

## Limitations

The reference IFC/BCF handoff is not certification against every BIM product. Field measurements are not survey-grade unless independently verified under the applicable procedure. The handoff does not certify code compliance, fabrication readiness, payment entitlement, or completeness of unobserved regions.

## Progress 06-R1 restricted-annex approval

`include_restricted_annex` is not authorization. A restricted export requires a current immutable approval created by a principal holding the exact `construction:restricted_export` action. The approval binds the normalized request scope, classification, audience, purpose, approver, expiry, tenant, project, and request hash. The export requester must be independent from the approver.

## Exact checksum profile and replay

`checksums.json` must declare algorithm `sha256`, a nonempty complete file map, and the deterministic root hash. Every archive member except `checksums.json` must be listed, and every listed member must exist. Unexpected or unchecked files—including scripts—cause failure. Duplicate manifest keys, partial or empty maps, malformed digests, altered bytes, and root mismatch also fail.

An idempotent handoff replay reopens the current ZIP, reruns all archive and checksum controls, and compares the current ZIP hash and package root to the retained record. Replacing the file after successful creation is detected.
