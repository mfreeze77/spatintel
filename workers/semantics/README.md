# semantics

Capability-scoped SIP durable worker.

Capabilities: `semantics.suggest`

The runtime leases an operation, checks cancellation, writes checkpoints, retains an audited terminal result, and rejects operation types outside this manifest.
