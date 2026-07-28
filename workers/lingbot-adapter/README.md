# lingbot-adapter

Capability-scoped SIP durable worker.

Capabilities: `lingbot.reconstruct`

The runtime leases an operation, checks cancellation, writes checkpoints, retains an audited terminal result, and rejects operation types outside this manifest.

This adapter is intentionally deny-by-default: source presence never authorizes a checkpoint, dataset, purpose, or commercial execution.
