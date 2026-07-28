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
