# Threat Model

## Security objectives

SIP protects tenant isolation, source confidentiality, consent, provenance, authority labels, chain of custody, availability, safe interaction, and independent recovery. A valid visual output is not sufficient if the system cannot prove who accessed the source, which approved code/model ran, and why the result was allowed.

## Trust boundaries

1. Mobile capture device and local encrypted storage.
2. Public API and identity/policy boundary.
3. Transactional database and audit chain.
4. Encrypted object store and signed-read mechanism.
5. Workflow queue and operation leases.
6. Isolated CPU/GPU workers and geometry/splat parsers.
7. External providers, plugins, hosted tools, and manual processors.
8. Web/desktop/immersive viewers.
9. Search, vector, graph, cache, notification, and export derivatives.
10. Export recipients and offline preservation packages.
11. Cloud control plane, workload identity, secret manager, KMS, telemetry, and backup systems.

## Enumerated threats and primary controls

| Threat | Primary controls |
|---|---|
| Capture-device compromise | local encryption, app/workload identity, append-only journal, immutable package hashing, verified receipt before purge, device-security and physical-device validation plan |
| Upload tampering or replay | chunk and root hashes, authenticated encryption, idempotency, optimistic concurrency, signed scopes, immutable original bytes |
| Archive bomb, traversal, malformed/future schema, or parser exploit | bounded entry/size/ratio limits, canonical paths, isolated no-network parser, typed schemas, quarantine, no publication side effect |
| Geometry or splat payload exploit | bounded parser processes, resource limits, immutable input hash, quarantined candidates, provider/version governance |
| GPU escape or worker privilege escalation | unique workload identity, signed lease, manifest/protocol/sandbox hash, no shell, compute-network denial, read-only input, write-only private staging, container/pod hardening |
| Cross-tenant object/search/cache/export access | tenant/project-scoped references, object authorization on every read, current-policy evaluation, negative leakage tests, pseudonymous telemetry |
| Signed-URL, notification-link, or credential leakage | short lifetime, audience/scope binding, current-policy reauthorization, revocation, rotation, generic external notification bodies, audit |
| Viewer scraping or topology disclosure | server-side authorization, restricted-region filtering, tiling/export policy, watermark/label options, rate limits, sensitive-system redaction, no client-side-only hiding |
| Model or source-data exfiltration | deny-by-default provider/model registry, exact hashes, approved purpose/classification/region/retention, no runtime download, egress allowlist, kill switch |
| External-provider egress beyond approval | manifest-bound data class/purpose/region/retention, gateway enforcement, encrypted transport, audit, revocation and derivative invalidation |
| Prompt injection or malicious document/media instructions | treat ingested text/media as untrusted data, tool allowlists, structured outputs, review-required semantic candidates, no agent authority to publish/certify/alter consent |
| Insider abuse or support impersonation | least privilege, workload identities, purpose binding, two-person destructive approval, immutable audit, no impersonating escalation, break-glass review |
| Authority spoofing or false verified measurement | separate metric/visual/interaction/design/evidence representations, source/authority labels, independent validation, proxy-to-metric re-resolution, verifier/date/uncertainty requirements |
| Derivative redaction, privacy, or consent failure | policy propagation to every derivative/index/cache/export/representation, dependency graph, invalidation, current-policy checks, preservation of policy history |
| Audit tampering or chain-of-custody break | append-only hash chain, restricted modification, signed receipts, backup/restore verification, retained roots |
| Destructive deletion error | dry run, dependency graph, legal-hold check, verified backup, independent two-person approval, unchanged snapshot, tombstone and key-destruction evidence |
| Supply-chain compromise | exact dependency/action/image/model pins, generated drift gates, SBOM, notices, signatures, vulnerability/secret scans, patch policy |
| Immersive collision/navigation failure | disposable interaction proxy, quality gates, metric separation, safe-navigation surfaces, unresolved-anchor reporting, quiet mode, pause/reset/safe exit, reduced motion |

## Abuse cases

- An operator tries to label a proxy-derived distance as field verified.
- A provider upgrade tries to receive confidential data outside its approved region.
- A revoked family subject remains discoverable in vector search.
- A support agent opens a historical notification after losing project access.
- A malformed ZIP attempts traversal, resource exhaustion, parser compromise, or future-schema confusion.
- A worker retries after timeout and creates a competing accepted scene output.
- A generated first-person memory is presented without lineage or consent.
- A malicious transcript instructs an agent to export restricted evidence or change audience policy.
- A visual splat is substituted for collision geometry or a metric as-built.

## Security validation and residual evidence gaps

Local automated tests cover tenant isolation, signed scopes, consent propagation, archive rejection, worker sandboxing, candidate/publication separation, authority re-resolution, audit integrity, deletion controls, and preservation restore where implemented. Penetration testing, cloud identity review, GPU/container escape testing, Apple mobile security review, immersive-device safety review, and independent privacy/legal assessment remain separate release evidence and must not be inferred from local tests.

The threat model must be reviewed whenever a sensor, model/provider, sharing mode, plugin, external telemetry destination, new data purpose, or trust boundary is added. The review records the change, affected threats, controls, tests, and approvers in an ADR or security review artifact.

## Secret handling

No production secret belongs in source, image layers, mobile packages, logs, manifests, or test fixtures. Local generated secrets are excluded from Git and cannot be promoted. Production uses approved secret-manager references and the documented key-rotation procedure.
