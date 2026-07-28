---
spec_id: SEC-EXTERNAL-SPATIAL-PROVIDERS
title: "External Spatial Provider Security and Governance"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: operations
normative: true
---

# External Spatial Provider Security and Governance

## 1. Purpose

Spatial conversion and editing services can receive unusually sensitive data: complete building layouts, control and life-safety systems, access-control paths, private homes, valuables, faces, voices, family relationships, memory evidence, location, and biometric signals. A textureless mesh, collision hull, or navigation graph can remain sensitive even after photographs are removed.

This specification governs any provider outside the directly controlled SIP trust boundary, including hosted websites, SaaS APIs, remote GPU endpoints, manually operated web tools, contractors, third-party desktop applications with cloud synchronization, and research services.

## 2. Core rule

No external provider may receive source or derived bytes merely because it is free, convenient, public, well regarded, or usable without an account. Data access requires an approved provider record, permitted purpose, matching data classification, documented processing location and retention, commercial/license rights, security assessment, contract where required, and auditable operation.

When information is unknown, the provider is treated as external, retaining data, unsuitable for confidential content, and blocked from production until evidence changes that classification.

## 3. Provider trust categories

| Category | Description | Default data eligibility |
|---|---|---|
| `first_party_local` | signed code executed on an operator-controlled device without network access | according to device/project policy |
| `first_party_private` | SIP-controlled service in an approved private environment | according to environment approval |
| `contracted_private_provider` | third party with documented API, agreement, private tenancy, security controls, and retention | approved classes and purposes only |
| `public_hosted_provider` | public web/API service with shared processing | public/synthetic unless specifically approved |
| `manual_external_tool` | operator manually exports/imports through a third-party tool | public/synthetic by default |
| `research_provider` | code/model with incomplete production, license, security, or support posture | isolated fixtures only |
| `unknown_provider` | insufficient evidence | no data access |

A provider may be categorized differently by deployment mode. Open-source code self-hosted in a controlled environment can receive a different security approval from the same project's public hosted demo.

## 4. Data classes

| Class | Examples | External default |
|---|---|---|
| `public_demo` | published sample scene, synthetic fixtures | allowed to approved public tools |
| `internal_non_sensitive` | test building without restricted details | approved providers only |
| `confidential_construction` | client rooms, drawings, equipment, field conditions | local/private providers |
| `restricted_building_systems` | access control, life-safety network, security rooms, protected routes | local/private explicitly approved |
| `critical_infrastructure` | SCIF, government, utility, laboratory, high-risk facility | local-only or contract-specific isolated environment |
| `private_residential` | home interiors, valuables, floor plans | local/private with explicit owner consent |
| `liveforever_sensitive` | family memories, relationship data, interviews, photos | local/private with purpose-specific consent |
| `biometric_or_intimate` | faces, voices, health, minors, intimate memories | highest restriction and explicit legal/consent review |

A derivative is classified by content and inference risk, not only texture. For example, a navigation mesh of a protected facility can remain `restricted_building_systems`.

## 5. Approval dossier

The provider record includes:

- legal entity, product, deployment mode, and service endpoint;
- source repository and exact revision where applicable;
- code, model, weight, dataset, and transitive licenses;
- commercial-use and redistribution rights;
- data ownership, processing purpose, subprocessors, regions, and transfer mechanisms;
- retention, deletion, backup, logging, telemetry, and model-training behavior;
- authentication, authorization, encryption, tenant isolation, key management, and incident response;
- vulnerability management, dependency/SBOM posture, and update process;
- local file access, network behavior, crash-reporting, and cloud synchronization;
- supported classifications, purposes, project restrictions, and expiration;
- benchmark and reproducibility evidence;
- contract/DPA/security-review references where required;
- responsible owner and next review date.

A checkbox asserting “we respect privacy” is not sufficient evidence.

## 6. SplatEdit posture in this baseline

SplatEdit is useful as a research/manual comparison for splat-to-proxy conversion. Under this specification it is classified `manual_external_tool` and `research_isolated` because the available public material does not establish a production API, self-hosting package, source repository for the service, processing/retention model, enterprise controls, or commercial integration terms sufficient for confidential SIP data.

Permitted baseline use:

- synthetic scenes;
- public benchmark splats;
- scenes specifically cleared for public demonstration;
- manual algorithm comparison with documented inputs, options, outputs, and operator.

Blocked baseline use:

- client construction scans;
- fire-alarm, access-control, network, or protected building details;
- private residences;
- LiveForever source or family scenes;
- faces, voices, minors, intimate content, or biometric data;
- critical infrastructure;
- automatic production dependency.

This posture can change only through the normal provider approval process. The specification does not claim the service is unsafe; it records that production-relevant facts are not yet established.

## 7. Controlled manual-export workflow

The manual export service:

1. validates project, data class, consent, purpose, and provider approval;
2. minimizes the outbound asset and removes unneeded metadata;
3. applies spatial crop/redaction and strips unrelated evidence;
4. creates a one-time operation manifest, coordinate witnesses, hashes, and expiry;
5. records the human operator and outbound custody event;
6. requires use in the approved account/device/network context;
7. records tool version, options, execution time, and processing declaration;
8. imports through malware/media validation and hash registration;
9. independently registers and validates the result;
10. records provider-side deletion or cleanup evidence where applicable;
11. quarantines the result until review and publication.

An operator cannot bypass the workflow by copying a project asset to personal storage or a browser upload control.

## 8. Technical controls

For approved external execution, use controls proportionate to classification:

- private endpoints or controlled egress proxy;
- destination allowlist and DNS/TLS policy;
- short-lived workload identity and scoped object URLs;
- customer/project-specific encryption and staging prefixes;
- minimal derivatives rather than canonical originals;
- no shared public link;
- content hashes and signed request/receipt;
- egress byte and destination monitoring;
- container or browser isolation;
- clipboard/download/screenshot restrictions where appropriate;
- data-loss-prevention scanning;
- local encrypted quarantine on return;
- verified deletion and credential revocation;
- security telemetry without raw scene content.

Network-required providers are blocked in local-only deployments unless an administrator creates a documented temporary exception that cannot increase data authority.

## 9. Supply-chain and model controls

Self-hosting source code does not remove license or model risk. The approval process separately examines:

- source-code license;
- checkpoint/weight license;
- training or reference dataset restrictions;
- noncommercial/research clauses;
- patent or field-of-use terms;
- CUDA/native binary dependencies;
- imported submodules and copied code;
- model download sources and hashes;
- pre/postprocessing packages;
- renderer and file-format libraries;
- telemetry or updater behavior;
- malicious file parsing and sandboxing.

Build artifacts are signed and accompanied by an SBOM. Unverified or expired artifacts cannot access customer data.

## 10. Privacy and consent

For private residences and LiveForever, the purpose must match consent. Consent to preserve a memory scene is not consent to send it to a public web conversion tool, train a model, publish a demo, or retain it indefinitely. A provider cannot become a processor for a new purpose through a generic terms-of-service acceptance by an operator.

For people incidentally captured in a construction or family scene, the project applies minimization, blurring/redaction, restricted access, or recapture according to policy. Geometry derived before redaction is evaluated for residual disclosure.

## 11. Incident handling

Events requiring incident review include:

- upload to an unapproved provider;
- wrong tenant/project asset exported;
- provider retention or training behavior inconsistent with approval;
- credentials or signed URL exposed;
- unexpected provider network destination;
- output containing source content that should have been removed;
- malware or malformed geometry on return;
- provider breach or material terms change;
- deletion confirmation failure;
- use after approval expiration;
- public link or screenshot exposure.

The response preserves logs and manifests, revokes access, stops related providers, identifies affected derivatives and audiences, evaluates notification duties, and records corrective actions. The platform avoids deleting evidence needed for an investigation while withdrawing user access.

## 12. Provider change monitoring

A terms, ownership, hosting, privacy, source, license, model, dependency, endpoint, or security-control change can invalidate approval. Providers have review dates and automated/operational monitoring where practical. A changed version enters shadow evaluation rather than inheriting active approval.

## 13. Exceptions

An exception states provider, exact data set, purpose, classification, minimization, controls, owner, approvers, start/end, deletion obligation, and residual risk. It expires automatically and cannot waive truth labels, consent rights, legal holds, or authority ceilings. Emergency convenience is not a standing exception.

## 14. Normative requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| SECEXT-001 | P0 | An external or unknown provider shall not access source or derived scene bytes before an approved provider dossier and matching data/purpose policy exist. | Egress and admission test |
| SECEXT-002 | P0 | Unknown data processing, retention, training, region, license, or security facts shall default to no production data access. | Governance policy test |
| SECEXT-003 | P0 | Data classification shall account for geometry, layout, inference, relationships, and security context even when textures or obvious identifiers are removed. | Classification review test |
| SECEXT-004 | P0 | Manual external use shall follow controlled minimization, export, custody, receipt, import validation, independent review, and deletion/cleanup recording. | Procedure and audit test |
| SECEXT-005 | P0 | Private residential, restricted building-system, critical-infrastructure, biometric, intimate, and LiveForever-sensitive data shall be blocked from public hosted providers unless a specific higher-order approval permits it. | Negative security tests |
| SECEXT-006 | P0 | Provider approval shall separately cover source code, weights, datasets, dependencies, commercial rights, deployment mode, and execution artifact hashes. | License/model gate test |
| SECEXT-007 | P0 | Provider credentials and object access shall be short-lived, least-privilege, operation-scoped, and revoked at completion or incident. | IAM integration test |
| SECEXT-008 | P0 | A consented preservation or construction purpose shall not be expanded to provider training, public demonstration, or unrelated retention without separate authorization. | Consent-purpose test |
| SECEXT-009 | P1 | Approved external execution shall use destination controls, egress monitoring, content hashes, signed receipts, quarantine, and return validation appropriate to the data class. | Security integration test |
| SECEXT-010 | P1 | A provider version or material terms/control change shall enter review or shadow state and shall not inherit approval automatically. | Change-management test |
| SECEXT-011 | P1 | Provider exceptions shall be scoped, approved, audited, automatically expiring, and unable to waive truth, consent, legal-hold, or authority rules. | Exception lifecycle test |
| SECEXT-012 | P1 | Incidents shall identify and withdraw affected source, derivative, publication, cache, and export assets while preserving investigation evidence. | Incident exercise |
| SECEXT-013 | P1 | Local-only deployments shall deny network-required providers by default and expose the attempted egress in audit. | Local deployment test |
| SECEXT-014 | P1 | SplatEdit shall remain limited to synthetic, public, or explicitly public-cleared fixtures until its production-relevant processing and permission posture is approved. | Provider registry test |
| SECEXT-015 | P1 | Output from an external provider shall be treated as untrusted content and parsed, scanned, registered, and validated in isolation. | Malformed asset test |
| SECEXT-016 | P1 | Operational telemetry about provider use shall not contain raw geometry, media, transcripts, secrets, or unnecessary precise locations. | Logging privacy test |

## 15. Acceptance

Acceptance requires a policy matrix and automated test suite demonstrating: public fixture export to an approved manual tool; denial of confidential construction and private family scenes; minimization and custody receipt; short-lived access; isolated return parsing; deletion dependency tracking; provider approval expiration; changed-version shadowing; local-only egress denial; and incident withdrawal of all affected derivatives and views.
