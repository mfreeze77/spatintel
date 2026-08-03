# SIP first-party capture

This Swift 6.2 package contains the persisted capture state machine, append-only hash-chained journal, canonical package writer/validator, bounded observation queue, privacy and quality gates, resource handling, recovery paths, and resumable transfer contract. Apple sensor acquisition is isolated behind `SpatialSensorAdapter`; deterministic fixtures compile and test on Linux.

```bash
swift test
```

The conditional Apple target imports ARKit, RealityKit, RoomPlan (when available), AVFoundation, CoreMotion, Metal, Network.framework, and BackgroundTasks. Linux evidence does **not** satisfy physical-device, LiDAR, camera, thermal, battery, background-task, or Xcode acceptance; those remain external validation.

On iOS, **Start local capture** writes content-addressed BGRA, float-meter depth,
confidence, motion, and ARKit mesh-anchor assets under
`Documents/SpatintelCaptures/<session-id>/`. **Finalize package** verifies every
asset and writes the root manifest without deleting originals. Copy the entire
directory to the workstation and follow
`docs/developer/IPHONE_CAPTURE_PIPELINE.md`.
