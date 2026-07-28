# depth-normalizer

Capability-scoped SIP durable worker.

Capabilities: `depth.normalize`, `depth.unproject`

The runtime leases an operation, checks cancellation, writes checkpoints, retains an audited terminal result, and rejects operation types outside this manifest.
