import test from "node:test";
import assert from "node:assert/strict";
import { finalReconstructionAdmission, orderedCostStages, summarizeCostEstimate, validateCostEstimate } from "../lib/cost-planner-runtime.mjs";
import { buildHybridRenderPlan, buildLayerRenderDirectives, defaultLayers, directProxyMeasurement, interactionDiagnostics, layerDirective, navigationFromKey, pickInteractionOnly, planResourceAdmission, pointPassesClipping, reprojectAnchors, resolveProxyHit, selectDeterministicLod, semanticFallback, serializeViewerSnapshot, synchronizedComparison, updateLayer, validateViewerSessionState } from "../lib/spatial-runtime.mjs";

test("representation layers remain distinct and bounded", () => {
  const layers = defaultLayers();
  assert.deepEqual(layers.map((layer) => layer.kind), ["metric", "visual", "design", "interaction", "evidence"]);
  assert.equal(layers.find((layer) => layer.kind === "interaction").authority, "derived_non_authoritative");
  assert.equal(updateLayer(layers, "visual", { opacity: 0.4 }).find((layer) => layer.kind === "visual").opacity, 0.4);
  assert.throws(() => updateLayer(layers, "visual", { opacity: 2 }), /opacity/);
});



test("PLTVIEW-007 reference layer directives cover visibility opacity labels and pickability", () => {
  let layers = defaultLayers();
  let directives = buildLayerRenderDirectives(layers, 0.72);
  assert.equal(layerDirective(directives, "metric").visible, true);
  assert.equal(layerDirective(directives, "design").visible, false);
  assert.equal(layerDirective(directives, "evidence").visible, true);
  assert.equal(layerDirective(directives, "interaction").pickable, true);
  assert.match(layerDirective(directives, "visual").authorityLabel, /generated reconstruction/);
  assert.match(layerDirective(directives, "evidence").authorityLabel, /immutable source record/);

  layers = updateLayer(layers, "metric", { visible: false });
  layers = updateLayer(layers, "visual", { opacity: 0.4 });
  layers = updateLayer(layers, "interaction", { visible: false });
  layers = updateLayer(layers, "design", { visible: true, opacity: 0.5 });
  layers = updateLayer(layers, "evidence", { visible: false });
  directives = buildLayerRenderDirectives(layers, 0.72);
  assert.equal(layerDirective(directives, "metric").visible, false);
  assert.equal(layerDirective(directives, "visual").opacity, 0.58 * 0.4 * 0.72);
  assert.equal(layerDirective(directives, "interaction").pickable, false);
  assert.equal(layerDirective(directives, "design").visible, true);
  assert.equal(layerDirective(directives, "design").opacity, 0.85 * 0.5);
  assert.equal(layerDirective(directives, "evidence").visible, false);

  const unauthorized = defaultLayers().map((layer) => layer.kind === "interaction" ? { ...layer, authorized: false, visible: true } : layer);
  assert.equal(layerDirective(buildLayerRenderDirectives(unauthorized), "interaction").pickable, false);
  assert.throws(() => updateLayer(unauthorized, "interaction", { visible: true }), /LAYER_AUTHORIZATION_DENIED/);
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


test("viewer sessions reject capabilities and require server redaction and accessibility", () => {
  const state = { sceneCommitIds: ["c1", "c2"], redaction: { serverEnforced: true }, accessibility: { reducedMotion: true, highContrast: true, captions: true }, comparison: { secondaryCommitId: "c2" } };
  assert.equal(validateViewerSessionState(state), true);
  assert.throws(() => validateViewerSessionState({ ...state, camera: { access_token: "secret" } }), /CAPABILITY_MATERIAL_DENIED/);
  assert.throws(() => validateViewerSessionState({ ...state, redaction: {} }), /REDACTION/);
});

test("LOD selection is deterministic and resource bounded", () => {
  const levels = [
    { level: 0, representationId: "coarse", maximumScreenError: 8, triangles: 100, splats: 0, gpuBytes: 1000 },
    { level: 1, representationId: "medium", maximumScreenError: 3, triangles: 1000, splats: 0, gpuBytes: 4000 },
    { level: 2, representationId: "fine", maximumScreenError: 1, triangles: 10000, splats: 0, gpuBytes: 40000 }
  ];
  assert.equal(selectDeterministicLod(levels, 4, { maxTriangles: 2000, maxSplats: 0, maxGpuBytes: 5000, maxDrawCalls: 10 }).representationId, "medium");
  assert.equal(selectDeterministicLod(levels.toReversed(), 4, { maxTriangles: 2000, maxSplats: 0, maxGpuBytes: 5000, maxDrawCalls: 10 }).representationId, "medium");
});

test("hybrid render plan keeps native splats and representation roles distinct", () => {
  const plan = buildHybridRenderPlan([
    { bindingId: "m", role: "metric", representation: "mesh", authority: "observed", triangles: 100, gpuBytes: 1000 },
    { bindingId: "v", role: "visual", representation: "gaussian_splat", authority: "generated", splats: 500, gpuBytes: 2000 },
    { bindingId: "i", role: "interaction", representation: "mesh", authority: "derived_non_authoritative", triangles: 20, gpuBytes: 200 }
  ], { maxTriangles: 200, maxSplats: 1000, maxGpuBytes: 5000, maxDrawCalls: 5 });
  assert.deepEqual(plan.roles, ["metric", "visual", "interaction"]);
  assert.equal(plan.nativeSplat, true);
  assert.equal(plan.admitted.find((item) => item.id === "i").interactive, true);
});

test("resource admission rejects overflow without evicting higher priority truth layers", () => {
  const result = planResourceAdmission([
    { id: "metric", role: "metric", priority: 0, triangles: 80, gpuBytes: 100, drawCalls: 1 },
    { id: "visual", role: "visual", priority: 2, splats: 1000, gpuBytes: 1000, drawCalls: 1 }
  ], { maxTriangles: 100, maxSplats: 500, maxGpuBytes: 500, maxDrawCalls: 2 });
  assert.deepEqual(result.admitted.map((item) => item.id), ["metric"]);
  assert.deepEqual(result.rejected, [{ id: "visual", reason: "resource_budget_exceeded" }]);
});

test("picking accepts only interaction geometry and uses stable semantic identity", () => {
  const hit = pickInteractionOnly([
    { role: "visual", interactive: false, distance: 0.1, stableEntityId: "visual" },
    { role: "interaction", interactive: true, distance: 0.2, stableEntityId: "door-2" },
    { role: "interaction", interactive: true, distance: 0.2, stableEntityId: "door-1" }
  ]);
  assert.equal(hit.stableEntityId, "door-1");
});

test("clipping and synchronized comparisons are deterministic", () => {
  assert.equal(pointPassesClipping([1, 1, 1], [{ normal: [1, 0, 0], constant: -0.5 }], { min: [0, 0, 0], max: [2, 2, 2] }), true);
  assert.equal(pointPassesClipping([0.1, 1, 1], [{ normal: [1, 0, 0], constant: -0.5 }], null), false);
  const compared = synchronizedComparison({ cameraId: "cam", commit: "a" }, { cameraId: "cam", commit: "b" }, 0.25);
  assert.equal(compared.primary.opacity, 0.75); assert.equal(compared.secondary.opacity, 0.25); assert.equal(compared.synchronizedCameraId, "cam");
});

test("interaction diagnostics keep collision navigation occlusion clipping and audio independently diagnosable", () => {
  const healthy = interactionDiagnostics({ collision: { sourceId: "c" }, navigation: { sourceId: "n" }, occlusion: { sourceId: "o" }, clipping: { sourceId: "p" }, spatial_audio: { sourceId: "a" } });
  assert.equal(healthy.healthy, true);
  assert.equal(interactionDiagnostics({ collision: { sourceId: "same" }, navigation: { sourceId: "same" } }).healthy, false);
});

test("semantic fallback and keyboard navigation preserve accessible scene access", () => {
  const fallback = semanticFallback([{ stableEntityId: "room-101", label: "Room 101", authorityLabel: "observed", evidenceIds: ["e1"] }], { webgl: false, webgpu: false });
  assert.equal(fallback.mode, "semantic"); assert.equal(fallback.entities[0].stableEntityId, "room-101"); assert.equal(fallback.entities[0].evidenceCount, 1);
  const moved = navigationFromKey({ position: [0, 0, 0], savedPosition: [5, 5, 5], reducedMotion: true }, "ArrowUp");
  assert.deepEqual(moved.position, [0, 0, -0.1]);
  assert.deepEqual(navigationFromKey(moved, "Home").position, [5, 5, 5]);
});


test("governed cost estimates reject stale pricing and require acknowledgement for expensive processing", () => {
  const now = Date.parse("2030-01-01T00:00:00Z");
  const expensive = summarizeCostEstimate({ totalAmount: 12.5, currency: "usd", processingTier: "gpu-high", priceSourceVersion: "catalog-v1", expiresAt: "2030-01-02T00:00:00Z" }, now);
  assert.equal(expensive.currency, "USD");
  assert.deepEqual(finalReconstructionAdmission(expensive, false), { allowed: false, reason: "COST_ACKNOWLEDGEMENT_REQUIRED" });
  assert.deepEqual(finalReconstructionAdmission(expensive, true), { allowed: true, reason: null });

  const stale = summarizeCostEstimate({ totalAmount: 1, currency: "USD", processingTier: "CPU reference", priceSourceVersion: "catalog-v1", expiresAt: "2029-12-31T23:59:59Z" }, now);
  assert.deepEqual(finalReconstructionAdmission(stale, true), { allowed: false, reason: "STALE_COST_ESTIMATE" });

  const view = { estimateId: "estimate-1", processingTier: "CPU reference", totalAmount: 4.25, currency: "USD", stageEstimates: [], priceSourceVersion: "catalog-v1", priceSourceHash: "1".repeat(64), expiresAt: "2030-01-02T00:00:00Z", state: "active" };
  assert.equal(validateCostEstimate(view, new Date(now)).canStart, true);
  assert.deepEqual(orderedCostStages([{ stage: "zeta", amount: 2, weight: 1 }, { stage: "alpha", amount: 1, weight: 1 }]).map((stage) => stage.stage), ["alpha", "zeta"]);
});
