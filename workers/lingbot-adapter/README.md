# lingbot-adapter

Capability-scoped SIP durable worker.

Capabilities: `lingbot.reconstruct`

The runtime leases an operation, checks cancellation, writes checkpoints, retains an audited terminal result, and rejects operation types outside this manifest.

This adapter is intentionally inactive until a local checkpoint is configured with an exact hash, source, supported purpose, and input/output terms.
