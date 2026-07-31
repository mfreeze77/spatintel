# Progress 09 Deployment-Control API

The `deployment-control` logical service owns deployment profiles, project bindings, residency and transfer policies, edge enrollment and updates, deployment-mode migrations, local upgrade rehearsals, autoscaling admission, AWS structural manifests, CDN derivative registration, provider replacement records, drift reports, and production admission.

All tenant/project routes derive scope and actor identity from authenticated headers. Callers cannot submit precomputed allow decisions. Admission denial is durable, audited, and emitted through the transactional outbox.

Generated contracts are under `schemas/openapi/deployment-control.openapi.json` and `schemas/jsonschema/`.
