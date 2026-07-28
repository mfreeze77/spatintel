export const REPRESENTATION_KINDS = ["metric", "visual", "design", "interaction", "evidence"];
const warnings = {
  metric: "Metric geometry is not verified unless its evidence and verification state say so.",
  visual: "Photorealistic appearance is not a measurement source.",
  design: "Design geometry expresses intent, not observed as-built conditions.",
  interaction: "Interaction proxies are disposable and non-authoritative.",
  evidence: null
};
const authority = { metric: "observed", visual: "generated", design: "derived_non_authoritative", interaction: "derived_non_authoritative", evidence: "authoritative" };
export function defaultLayers() {
  return REPRESENTATION_KINDS.map((kind) => ({ kind, visible: kind !== "design", opacity: kind === "visual" ? 0.82 : 1, authority: authority[kind], warning: warnings[kind] }));
}
export function updateLayer(layers, kind, patch) {
  if (patch.opacity !== undefined && (!Number.isFinite(patch.opacity) || patch.opacity < 0 || patch.opacity > 1)) throw new RangeError("opacity must be between zero and one");
  return layers.map((layer) => layer.kind === kind ? { ...layer, ...patch } : layer);
}
function distance(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
export function resolveProxyHit(hit, surfaces) {
  const candidates = surfaces.filter((surface) => surface.coordinateFrameId === hit.coordinateFrameId)
    .map((surface) => ({ surface, distanceM: distance(hit.point, surface.point) }))
    .filter(({ surface, distanceM }) => distanceM <= surface.toleranceM)
    .sort((left, right) => left.distanceM - right.distanceM || left.surface.surfaceId.localeCompare(right.surface.surfaceId));
  const closest = candidates[0];
  if (!closest) return { eligible: false, reason: "No eligible metric evidence supports this proxy hit." };
  return { eligible: true, reason: "Resolved against eligible metric evidence; independent verification is still required for verified status.", metricSurfaceId: closest.surface.surfaceId, entityId: closest.surface.entityId, resolvedPoint: closest.surface.point, uncertaintyM: closest.surface.uncertaintyM, sourceAssetIds: closest.surface.sourceAssetIds };
}
export function directProxyMeasurement() { throw new Error("PROXY_MEASUREMENT_DENIED: a proxy hit cannot directly create an authoritative measurement"); }
export function reprojectAnchors(anchors, replacementSurfaces, maximumDistanceM = 0.25) {
  if (!Number.isFinite(maximumDistanceM) || maximumDistanceM <= 0) throw new RangeError("maximumDistanceM must be positive");
  const resolved = []; const unresolved = [];
  for (const anchor of anchors) {
    const candidates = replacementSurfaces.filter((surface) => surface.entityId === anchor.entityId && surface.coordinateFrameId === anchor.coordinateFrameId)
      .map((surface) => ({ surface, distanceM: distance(anchor.worldPoint, surface.point) }))
      .sort((left, right) => left.distanceM - right.distanceM || left.surface.surfaceId.localeCompare(right.surface.surfaceId));
    const closest = candidates[0];
    if (!closest || closest.distanceM > maximumDistanceM) unresolved.push({ anchorId: anchor.anchorId, reason: "No same-entity metric support within reprojection tolerance." });
    else resolved.push({ ...anchor, worldPoint: closest.surface.point });
  }
  return { resolved, unresolved };
}
export function serializeViewerSnapshot(snapshot) {
  return JSON.stringify({ ...snapshot, layers: [...snapshot.layers].sort((a, b) => a.kind.localeCompare(b.kind)), clippingPlanes: [...snapshot.clippingPlanes] });
}

const ROLE_ORDER = ["metric", "visual", "design", "interaction", "evidence"];
const CAPABILITY_KEYS = new Set(["token", "access_token", "refresh_token", "authorization", "bearer", "signed_url", "presigned_url", "credential", "secret", "password", "storage_key", "provider_key"]);
function assertNoCapabilities(value, path = "root") {
  if (Array.isArray(value)) return value.forEach((item, index) => assertNoCapabilities(item, `${path}[${index}]`));
  if (!value || typeof value !== "object") return;
  for (const [key, item] of Object.entries(value)) {
    const normalized = key.toLowerCase().replaceAll("-", "_");
    if (CAPABILITY_KEYS.has(normalized)) throw new Error(`VIEWER_CAPABILITY_MATERIAL_DENIED:${path}.${key}`);
    assertNoCapabilities(item, `${path}.${key}`);
  }
}
export function validateViewerSessionState(state) {
  assertNoCapabilities(state);
  if (!Array.isArray(state.sceneCommitIds) || state.sceneCommitIds.length < 1 || state.sceneCommitIds.length > 2) throw new Error("VIEWER_COMMIT_SET_INVALID");
  if (new Set(state.sceneCommitIds).size !== state.sceneCommitIds.length) throw new Error("VIEWER_COMMIT_SET_DUPLICATE");
  if (state.redaction?.serverEnforced !== true) throw new Error("VIEWER_REDACTION_NOT_SERVER_ENFORCED");
  for (const key of ["reducedMotion", "highContrast", "captions"]) if (typeof state.accessibility?.[key] !== "boolean") throw new Error(`VIEWER_ACCESSIBILITY_MISSING:${key}`);
  if (state.sceneCommitIds.length === 2 && !state.comparison?.secondaryCommitId) throw new Error("VIEWER_COMPARISON_STATE_REQUIRED");
  return true;
}
export function selectDeterministicLod(levels, targetScreenError, budget) {
  if (!Number.isFinite(targetScreenError) || targetScreenError < 0) throw new RangeError("targetScreenError must be non-negative");
  const ordered = [...levels].sort((a, b) => b.level - a.level || a.representationId.localeCompare(b.representationId));
  const admitted = ordered.find((item) => item.maximumScreenError <= targetScreenError && item.triangles <= budget.maxTriangles && item.splats <= budget.maxSplats && item.gpuBytes <= budget.maxGpuBytes);
  return admitted ?? [...levels].sort((a, b) => a.level - b.level || a.representationId.localeCompare(b.representationId))[0] ?? null;
}
export function planResourceAdmission(resources, budget) {
  const totals = { triangles: 0, splats: 0, gpuBytes: 0, drawCalls: 0 };
  const admitted = []; const rejected = [];
  const ordered = [...resources].sort((a, b) => (a.priority - b.priority) || ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role) || a.id.localeCompare(b.id));
  for (const resource of ordered) {
    const next = { triangles: totals.triangles + (resource.triangles ?? 0), splats: totals.splats + (resource.splats ?? 0), gpuBytes: totals.gpuBytes + (resource.gpuBytes ?? 0), drawCalls: totals.drawCalls + (resource.drawCalls ?? 1) };
    const allowed = next.triangles <= budget.maxTriangles && next.splats <= budget.maxSplats && next.gpuBytes <= budget.maxGpuBytes && next.drawCalls <= budget.maxDrawCalls;
    if (allowed) { admitted.push(resource); Object.assign(totals, next); } else rejected.push({ id: resource.id, reason: "resource_budget_exceeded" });
  }
  return { admitted, rejected, totals };
}
export function buildHybridRenderPlan(bindings, budget) {
  const resources = bindings.map((binding) => ({
    id: binding.bindingId,
    role: binding.role,
    representation: binding.representation,
    primitive: binding.role === "visual" && binding.representation === "gaussian_splat" ? "native_points_splat" : "mesh_or_semantic",
    interactive: binding.role === "interaction",
    authority: binding.authority,
    triangles: binding.triangles ?? 0,
    splats: binding.splats ?? 0,
    gpuBytes: binding.gpuBytes ?? 0,
    drawCalls: binding.drawCalls ?? 1,
    priority: ROLE_ORDER.indexOf(binding.role)
  }));
  const admission = planResourceAdmission(resources, budget);
  return { ...admission, roles: ROLE_ORDER.filter((role) => admission.admitted.some((item) => item.role === role)), nativeSplat: admission.admitted.some((item) => item.primitive === "native_points_splat") };
}
export function pickInteractionOnly(hits) {
  const accepted = hits.filter((hit) => hit.role === "interaction" && hit.interactive === true).sort((a, b) => a.distance - b.distance || a.stableEntityId.localeCompare(b.stableEntityId));
  return accepted[0] ?? null;
}
export function pointPassesClipping(point, planes = [], sectionBox = null) {
  if (sectionBox && point.some((value, index) => value < sectionBox.min[index] || value > sectionBox.max[index])) return false;
  return planes.every((plane) => plane.normal[0] * point[0] + plane.normal[1] * point[1] + plane.normal[2] * point[2] + plane.constant >= 0);
}
export function synchronizedComparison(primary, secondary, split = 0.5) {
  if (!Number.isFinite(split) || split < 0 || split > 1) throw new RangeError("comparison split must be between zero and one");
  return { primary: { ...primary, opacity: 1 - split }, secondary: { ...secondary, opacity: split }, synchronizedCameraId: primary.cameraId === secondary.cameraId ? primary.cameraId : null };
}
export function interactionDiagnostics(sources) {
  const required = ["collision", "navigation", "occlusion", "clipping", "spatial_audio"];
  const missing = required.filter((key) => !sources[key]?.sourceId);
  const identifiers = required.map((key) => sources[key]?.sourceId).filter(Boolean);
  const duplicate = identifiers.length !== new Set(identifiers).size;
  return { healthy: missing.length === 0 && !duplicate, missing, duplicateSourceIds: duplicate };
}
export function semanticFallback(entities, capabilities) {
  const renderAvailable = capabilities.webgl || capabilities.webgpu;
  return { mode: renderAvailable ? "hybrid" : "semantic", entities: entities.map((entity) => ({ stableEntityId: entity.stableEntityId, label: entity.label, authorityLabel: entity.authorityLabel, evidenceCount: entity.evidenceIds?.length ?? 0 })), renderUnavailableReason: renderAvailable ? null : "WebGL/WebGPU unavailable; semantic scene tree retained." };
}
export function navigationFromKey(state, key) {
  const step = state.reducedMotion ? 0.1 : 0.25;
  const position = [...state.position];
  if (["ArrowUp", "w", "W"].includes(key)) position[2] -= step;
  else if (["ArrowDown", "s", "S"].includes(key)) position[2] += step;
  else if (["ArrowLeft", "a", "A"].includes(key)) position[0] -= step;
  else if (["ArrowRight", "d", "D"].includes(key)) position[0] += step;
  else if (key === "Home") return { ...state, position: [...state.savedPosition] };
  else return state;
  return { ...state, position };
}
