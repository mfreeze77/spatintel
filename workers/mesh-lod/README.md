# mesh-lod

Capability-scoped SIP durable worker.

Capabilities: `mesh.lod`, `mesh.compose`

`mesh.compose` cleans the metric mesh without changing face winding, derives a
colored visual splat lane when vertex colors are available, creates a bounded
interaction LOD, and reports topology/appearance coverage. The three lanes
remain separate so a visually attractive result cannot silently become metric
evidence.
