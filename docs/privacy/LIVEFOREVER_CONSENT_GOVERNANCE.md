# LiveForever Consent, Family Governance, and Privacy

## Consent dimensions

Every grant or governance record must identify the grantor and authority basis, subject/data scope, purposes, modalities, audiences, providers, geography, effective time, expiration, posthumous rules, evidence, successor or executor roles, and revocation behavior. A project membership or client-side hidden control is never sufficient authorization.

## Applicable-policy evaluation

The service evaluates the subject, contributor, living third party, minor/guardian, executor/successor, audience, purpose, modality, provider, geography, retention, classification, and dispute state. The most restrictive applicable rule wins. Unknown or conflicting authority fails closed for high-risk actions.

## Family corrections

A transcription correction creates an edited reading layer and retains original audio/video and original transcript. Factual correction, contributor retraction, consent restriction, and alternate interpretation create attributed revisions. Original testimony is not overwritten. Conflict is presented neutrally with source attribution; majority vote is not proof.

## Revocation propagation

Revocation stops new processing and updates affected records, editions, indexes, derivatives, exports, and caches according to policy. Derivatives become withdrawn or restricted and are queued for deletion/review when required. Static exports cannot be recalled from an unauthorized recipient; therefore audience and consent must be verified before release, and release records must identify that residual limitation.

## Minors, guardians, executors, and successors

Authority transitions require retained evidence and cannot enable a prohibited purpose or modality. Successors cannot silently broaden a deceased or incapacitated subject’s prior permissions. Active disputes freeze generated presence, visual reconstruction, public publication, or destructive policy changes.

## Privacy-safe demonstrations

Progress 06 uses synthetic people, places, media, and consent. It does not use private-family data, real voices, likeness cloning, or external providers. Any later human-subject pilot requires documented consent, privacy and legal review, safe exit, quiet mode, accessibility review, incident response, and explicit data-retention and deletion procedures.

## Progress 06-R1 scoped revocation

Consent revocation requires the project-scoped route and an authenticated principal authorized for that tenant and project. The service resolves a grant by the tuple `(tenant_id, project_id, grant_id)` rather than by primary key alone. The legacy unscoped endpoint always fails closed and is excluded from the generated public OpenAPI contract.
