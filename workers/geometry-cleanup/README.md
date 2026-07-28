# geometry-cleanup

Capability-scoped SIP durable worker.

Capabilities: `geometry.cleanup`

The runtime leases an operation, checks cancellation, writes checkpoints, retains an audited terminal result, and rejects operation types outside this manifest.
