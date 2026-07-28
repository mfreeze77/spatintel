# change-detection

Capability-scoped SIP durable worker.

Capabilities: `change.detect`

The runtime leases an operation, checks cancellation, writes checkpoints, retains an audited terminal result, and rejects operation types outside this manifest.
