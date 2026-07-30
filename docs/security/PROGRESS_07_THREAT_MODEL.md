# Progress 07 threat model and misuse analysis

This document is the human-readable companion to the versioned `ThreatManifest` contract. It covers the bounded `OPS-001` milestone only and does not authorize production.

## Critical threat catalog

| Threat | Preventative control | Detective control | Recovery control | Owner | Retained test |
|---|---|---|---|---|---|
| Capture-device compromise | local encryption, signed finalization, bounded queues | finalization identity/hash audit | revoke device/session; re-capture | Mobile security | `test_progress07_transport_capture_provider_output_and_immersive_routes` |
| Upload tampering | chunk/root hashes and signed principals | package and archive hash verification | quarantine and restart resumable upload | Capture platform | same |
| Archive bomb | bounded archive parser | malicious corpus and expansion metrics | reject before persistence/publication | Ingestion security | `test_progress07_supply_chain_contracts_are_pinned_and_fail_closed` plus existing archive tests |
| Parser exploit | isolated parsing and allowed media types | format validation receipts | quarantine output and disable provider | Reconstruction security | `test_untrusted_provider_outputs_remain_quarantined_and_immersive_failures_degrade_safely` |
| GPU escape | isolated worker identity and default-deny egress | workload/audience audit | revoke workload and provider | Worker security | `test_progress07_workload_and_jit_access_fail_closed` |
| Cross-tenant access | server-side tenant/project policy | cross-tenant adversarial tests | revoke credentials and invalidate caches | Identity security | same |
| Signed-URL leakage | short-lived scoped references | access audit and cache invalidation | revoke links and purge derivatives | Asset security | provider/cache tests |
| Viewer scraping | hostile-client assumption, no embedded secrets | rate and watermark telemetry | revoke share and purge caches | Web security | threat manifest contract |
| Model exfiltration | runtime downloads and public egress denied | network-policy verification | revoke workload/provider | ML security | infrastructure security tests |
| Prompt injection | allowlisted agent tools and evidence-bound output | agent audit and refusal codes | disable tool/provider | Agent security | existing agent abuse tests |
| Insider abuse | phishing-resistant JIT with independent approval | immutable privileged-access audit | immediate revocation and incident workflow | Security operations | JIT API/security tests |
| Destructive deletion | legal holds, verified backup, two-person approval | deletion evidence and audit | independent restore | Data governance | lifecycle deletion test |
| Geometry payload parsing | quarantine and bounded parser | format/transform receipts | reject and retain evidence | Reconstruction security | provider-output validation test |
| Provider egress | approved dossier, exact purpose/classification/region | provider authorization audit | provider incident withdrawal | Provider governance | provider policy tests |
| Topology disclosure | geometry derivatives remain authorized | unauthorized-discovery tests | invalidate caches/exports | Spatial security | hybrid and search security tests |
| Derivative redaction | policy propagation to every derivative | cache/index/export checks | invalidate all derivative surfaces | Privacy operations | consent/cache tests |
| Authority spoofing | immutable authority ceiling and metric re-resolution | adversarial proxy/design tests | quarantine and supersede | Scene authority | hybrid measurement guard |
| Immersive safety failure | scale/walkability/opening/fall/spawn/exit checks | safety decision audit | disable affected modes, preserve orbit/static fallback | Viewer safety | immersive fault-injection test |

## Misuse cases beyond confidentiality

Sensitive facilities are treated as vulnerable to topology inference, system-pathway inference, credential association, and device-location correlation even when obvious labels are removed. Private family collections are treated as vulnerable to relationship inference, living-person exposure, sensitive-event reconstruction, likeness misuse, and audience escalation even when source media is withheld.

## Hostile public viewer

The viewer is untrusted client code. It receives no durable secrets, provider credentials, storage keys, unrestricted URLs, or authorization decisions. Server policy controls every binding; client hiding is never authorization. Scraping controls, watermarking, rate limits, short-lived bindings, and policy-versioned cache invalidation are required.

## Review triggers

A new manifest version is required for a new sensor, model/provider, sharing mode, plugin, data purpose, material incident, or scheduled review. Prior versions remain immutable and superseded rather than overwritten.

## Residual risks

Screen capture, shoulder surfing, authorized-user misuse, inference from permitted views, physical sensor compromise, zero-day parser/driver defects, and provider legal/process failures cannot be eliminated by this reference implementation. Owners and release dispositions are retained in each versioned threat manifest. Production remains blocked pending independent penetration, privacy, accessibility, legal, device, GPU/model, and deployed-infrastructure validation.
