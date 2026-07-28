# document-media

Capability-scoped SIP durable worker.

Capabilities: `document.media.index`

The runtime leases an operation, checks cancellation, writes checkpoints, retains an audited terminal result, and rejects operation types outside this manifest.
