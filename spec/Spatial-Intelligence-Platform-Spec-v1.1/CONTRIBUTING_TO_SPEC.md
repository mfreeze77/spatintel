---
spec_id: SIP-CONTRIB
title: "Contributing to the Specification"
version: 1.1.0
status: "Build-ready engineering baseline"
last_updated: 2026-07-27
category: governance
normative: false
---
# Contributing to the Specification

Changes to this specification follow the same evidence discipline expected of the product.

## Change classes

- **Editorial:** wording or formatting only; no behavior change.
- **Clarification:** makes existing intent testable without changing scope.
- **Compatible extension:** adds optional fields, events, adapters, or workflows.
- **Breaking change:** modifies required behavior, identifiers, coordinate conventions, security, consent, or canonical schemas.
- **Safety correction:** immediately tightens a control to prevent incorrect authority, privacy exposure, data loss, or unlicensed use.

## Required change record

Every non-editorial change states the problem, affected requirements, alternatives, migration, security/privacy impact, data compatibility, tests, and owner. Breaking changes increment the relevant schema major version and include an executable migration or explicit unsupported-path decision.

## Writing requirements

Use “shall” for mandatory behavior, “should” for recommended behavior with justified exceptions, and “may” for optional behavior. Avoid “accurate,” “fast,” “secure,” or “easy” without a measurable operating envelope. Every requirement has one primary owner and a defined verification method.

## Source updates

Current external projects change rapidly. When updating a fact, record the source URL, retrieval date, commit/tag/checkpoint, observed license, and whether the fact affects design or only implementation guidance. Never infer a model-weight license from a repository code license.
