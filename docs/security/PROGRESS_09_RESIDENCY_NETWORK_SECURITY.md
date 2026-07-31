# Progress 09 Residency and Network Security

Residency is enforced before upload, transfer, provider execution, or worker scheduling. Rules bind tenant, project, asset class or worker class, mode, region, purpose, and approval state. Default action is deny.

Deployment profiles require default-deny ingress and egress. Only declared DNS, database, queue, and object-store endpoints are permitted. Edge workload credentials are short-lived and audience, workload, tenant, project, purpose, and scope bound.

Unauthorized regions, cross-tenant bindings, caller-supplied decisions, raw secret material, public raw origins, unpinned images, and incomplete production evidence fail closed.
