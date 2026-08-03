# capture-normalizer

Capability-scoped SIP durable worker.

`capture.reconstruct` validates a canonical iPhone capture, normalizes normally
tracked depth/confidence observations, fuses metric samples, prefers ARKit mesh
anchors for the metric surface, and writes separate metric, visual, interaction,
quality, and viewer artifacts. It never upgrades the preview result to verified
measurement authority.

Capabilities: `capture.validate`, `capture.normalize`, `capture.polyform.normalize`

The runtime leases an operation, checks cancellation, writes checkpoints, retains an audited terminal result, and rejects operation types outside this manifest.
