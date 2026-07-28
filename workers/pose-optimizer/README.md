# pose-optimizer

Capability-scoped SIP durable worker.

Capabilities: `pose.optimize`, `pose.anomaly.detect`

The runtime leases an operation, checks cancellation, writes checkpoints, retains an audited terminal result, and rejects operation types outside this manifest.
