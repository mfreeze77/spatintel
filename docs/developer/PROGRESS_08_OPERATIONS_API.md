# Progress 08 Operations Intelligence API

The `operations-intelligence` logical service owns OPS-002 telemetry, SLO, performance, cost, quota, anomaly, queue, resilience, compute-profile, support, incident, and game-day records. It may be co-located locally, but its public route set and workload identity remain distinct.

All project routes require an authenticated tenant/project principal. Tenant-level catalogs, SLOs, budgets, and capacity plans require exact operations privileges. Budget and support approvals use independent roles. Stable errors are returned for incomplete telemetry, stale estimates, quota races, scope mismatches, unsafe support metadata, incompatible compute profiles, and invalid checkpoints.

Use `schemas/openapi/operations-intelligence.openapi.json` and generated clients as the public contract. Event types are registered in `schemas/events/event-catalog.json`. Direct database writes and ad-hoc metrics with uncontrolled labels are prohibited.
