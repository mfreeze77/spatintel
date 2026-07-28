import test from "node:test";
import assert from "node:assert/strict";
import { defaultLayers, directProxyMeasurement, reprojectAnchors, resolveProxyHit, serializeViewerSnapshot, updateLayer } from "../lib/spatial-runtime.mjs";

test("representation layers remain distinct and bounded", () => {
  const layers = defaultLayers();
  assert.deepEqual(layers.map((layer) => layer.kind), ["metric", "visual", "design", "interaction", "evidence"]);
  assert.equal(layers.find((layer) => layer.kind === "interaction").authority, "derived_non_authoritative");
  assert.equal(updateLayer(layers, "visual", { opacity: 0.4 }).find((layer) => layer.kind === "visual").opacity, 0.4);
  assert.throws(() => updateLayer(layers, "visual", { opacity: 2 }), /opacity/);
});

test("proxy hits must resolve against metric evidence", () => {
  const hit = { proxyRepresentationId: "proxy", proxyElementId: "face", coordinateFrameId: "frame", point: [1.02, 2, 3] };
  const surfaces = [{ surfaceId: "metric", entityId: "room", coordinateFrameId: "frame", point: [1, 2, 3], toleranceM: 0.05, sourceAssetIds: ["depth"], uncertaintyM: 0.01 }];
  const result = resolveProxyHit(hit, surfaces);
  assert.equal(result.eligible, true);
  assert.equal(result.metricSurfaceId, "metric");
  assert.deepEqual(result.sourceAssetIds, ["depth"]);
  assert.throws(() => directProxyMeasurement(), /PROXY_MEASUREMENT_DENIED/);
  assert.equal(resolveProxyHit({ ...hit, point: [9, 9, 9] }, surfaces).eligible, false);
});

test("proxy replacement preserves stable anchors or reports them unresolved", () => {
  const anchors = [
    { anchorId: "a1", entityId: "room", coordinateFrameId: "frame", worldPoint: [0, 0, 0] },
    { anchorId: "a2", entityId: "door", coordinateFrameId: "frame", worldPoint: [4, 0, 0] }
  ];
  const surfaces = [{ surfaceId: "s", entityId: "room", coordinateFrameId: "frame", point: [0.01, 0, 0], toleranceM: 0.1, sourceAssetIds: ["depth"], uncertaintyM: 0.01 }];
  const result = reprojectAnchors(anchors, surfaces);
  assert.equal(result.resolved.length, 1);
  assert.deepEqual(result.resolved[0].worldPoint, [0.01, 0, 0]);
  assert.deepEqual(result.unresolved.map((item) => item.anchorId), ["a2"]);
});

test("viewer snapshot serialization is deterministic", () => {
  const snapshot = { schema: "sip.viewer-session", schemaVersion: "1.1.0", sceneCommitId: "c1", layers: defaultLayers().toReversed(), selectedEntityId: null, clippingPlanes: [], timelineInstant: null };
  assert.equal(serializeViewerSnapshot(snapshot), serializeViewerSnapshot({ ...snapshot, layers: defaultLayers() }));
});
