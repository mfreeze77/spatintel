# iPhone capture and local downstream pipeline

## What the iPhone produces

Each finalized session is a directory under `SpatintelCaptures/<session-id>/`.
The directory is protected by iOS file protection and contains a root
`manifest.json`, a hash-chained event journal, and immutable sensor assets.

Expected records and bytes are:

- camera frames converted off the ARSession callback path to tightly packed
  `BGRA8` (`rgb.bgra8`);
- LiDAR depth as tightly packed little-endian IEEE-754 `Float32` meters, with
  NaN and other invalid values preserved (`depth.f32`);
- ARKit confidence as one byte per depth pixel using `0=low`, `1=medium`, and
  `2=high` (`confidence.u8`);
- ARKit camera-to-world transforms, camera intrinsics, RGB/depth dimensions,
  tracking state/reason, orientation, exposure, and a monotonic timestamp;
- a motion sample in the same system-uptime clock domain when Core Motion is
  available;
- every ARMeshAnchor add/update/remove, including its transform and a
  `SIPMSH1` asset containing float32 vertices/normals, uint32 triangle indices,
  and uint8 ARKit face classifications;
- explicit tracking, relocalization, interruption, origin-change, quality, and
  dropped-observation records;
- device model, iOS version, app build, available sensors, capture policy,
  coordinate convention, segments, asset hashes/sizes/types, journal root, and
  manifest root hash.

Sensor resolution is recorded rather than assumed. Typical LiDAR depth is lower
resolution than RGB, so the workstation scales the recorded RGB calibration to
the depth grid before unprojection.

## iPhone workflow

1. Open SIP Capture on the LiDAR-capable iPhone.
2. Select **Start local capture** and move in slow, overlapping loops. Add
   oblique/detail passes around corners, doors, openings, thin objects, glossy
   surfaces, and any area showing weak coverage.
3. If tracking is limited, stop moving and return to a previously observed,
   textured area.
4. Select **Finalize package** before disconnecting or copying files.
5. In Files, or over a cable, copy the entire session directory. Do not copy
   only `manifest.json`.

The phone retains originals. No automatic purge or hosted upload occurs.

## Workstation workflow

From the repository root, convert the copied directory to the canonical archive:

```powershell
$env:PYTHONPATH = "src;."
python -m sip.cli import-iphone-capture `
  "D:\iPhone\SpatintelCaptures\<session-id>" `
  "runtime\captures\<session-id>.sipcapture"
```

Build all local downstream representations:

```powershell
python -m sip.cli reconstruct-capture `
  "runtime\captures\<session-id>.sipcapture" `
  "runtime\scenes\<session-id>"
```

The scene directory contains:

- `metric.ply` — ARKit mesh-anchor metric base, colored from registered RGB;
- `visual.ply` — deterministic colored point/splat preview;
- `interaction.ply` — disposable picking/collision/navigation LOD;
- `quality.json` — capture, fusion, topology, uncertainty, and limitation facts;
- `viewer-bundle.json` — bounded local file opened by the web viewer;
- `scene-manifest.json` — hashes, roles, provenance, and the rule that
  measurement resolves to `metric.ply`.

Run the local web application, open the Hybrid Viewer, and choose the generated
`viewer-bundle.json`. The browser reads the selected file locally; this workflow
does not upload it to a hosted service.

## Acceptance boundary

The implementation and deterministic fixtures prove serialization, integrity,
import, reconstruction, role separation, and export logic. They do not prove a
particular iPhone/Xcode build, physical LiDAR calibration, real-scene accuracy,
thermal endurance, or field completeness. The first device run must retain:

- the complete copied iPhone directory and canonical `.sipcapture` hash;
- Xcode/iOS/device/app-build identity;
- capture duration, frame/drop/tracking-event counts, and storage use;
- the generated quality report and screenshots of weak regions;
- independent check dimensions or control points for any claimed accuracy.

Until that evidence exists, output acceptance remains `preview` and metric
authority remains `metric_unverified`.
