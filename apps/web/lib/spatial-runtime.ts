export const REPRESENTATION_KINDS = ["metric", "visual", "design", "interaction", "evidence"] as const;
export type RepresentationKind = (typeof REPRESENTATION_KINDS)[number];
export type AuthorityClass = "authoritative" | "verified" | "measured" | "observed" | "inferred" | "generated" | "derived_non_authoritative";

export interface LayerState {
  readonly kind: RepresentationKind;
  readonly visible: boolean;
  readonly opacity: number;
  readonly authority: AuthorityClass;
  readonly warning: string | null;
}

export interface MetricSurface {
  readonly surfaceId: string;
  readonly entityId: string;
  readonly coordinateFrameId: string;
  readonly point: readonly [number, number, number];
  readonly toleranceM: number;
  readonly sourceAssetIds: readonly string[];
  readonly uncertaintyM: number;
}

export interface ProxyHit {
  readonly proxyRepresentationId: string;
  readonly proxyElementId: string;
  readonly coordinateFrameId: string;
  readonly point: readonly [number, number, number];
}

export interface MeasurementResolution {
  readonly eligible: boolean;
  readonly reason: string;
  readonly metricSurfaceId?: string;
  readonly entityId?: string;
  readonly resolvedPoint?: readonly [number, number, number];
  readonly uncertaintyM?: number;
  readonly sourceAssetIds?: readonly string[];
}

export interface StableAnchor {
  readonly anchorId: string;
  readonly entityId: string;
  readonly coordinateFrameId: string;
  readonly worldPoint: readonly [number, number, number];
}

export interface ReprojectionResult {
  readonly resolved: readonly StableAnchor[];
  readonly unresolved: readonly { anchorId: string; reason: string }[];
}

const warnings: Record<RepresentationKind, string | null> = {
  metric: "Metric geometry is not verified unless its evidence and verification state say so.",
  visual: "Photorealistic appearance is not a measurement source.",
  design: "Design geometry expresses intent, not observed as-built conditions.",
  interaction: "Interaction proxies are disposable and non-authoritative.",
  evidence: null
};

const authority: Record<RepresentationKind, AuthorityClass> = {
  metric: "observed",
  visual: "generated",
  design: "derived_non_authoritative",
  interaction: "derived_non_authoritative",
  evidence: "authoritative"
};

export function defaultLayers(): readonly LayerState[] {
  return REPRESENTATION_KINDS.map((kind) => ({
    kind,
    visible: kind !== "design",
    opacity: kind === "visual" ? 0.82 : 1,
    authority: authority[kind],
    warning: warnings[kind]
  }));
}

export function updateLayer(
  layers: readonly LayerState[],
  kind: RepresentationKind,
  patch: Readonly<Partial<Pick<LayerState, "visible" | "opacity">>>
): readonly LayerState[] {
  if (patch.opacity !== undefined && (!Number.isFinite(patch.opacity) || patch.opacity < 0 || patch.opacity > 1)) {
    throw new RangeError("opacity must be between zero and one");
  }
  return layers.map((layer) => (layer.kind === kind ? { ...layer, ...patch } : layer));
}

function distance(a: readonly number[], b: readonly number[]): number {
  return Math.hypot(a[0]! - b[0]!, a[1]! - b[1]!, a[2]! - b[2]!);
}

export function resolveProxyHit(hit: ProxyHit, surfaces: readonly MetricSurface[]): MeasurementResolution {
  const candidates = surfaces
    .filter((surface) => surface.coordinateFrameId === hit.coordinateFrameId)
    .map((surface) => ({ surface, distanceM: distance(hit.point, surface.point) }))
    .filter(({ surface, distanceM }) => distanceM <= surface.toleranceM)
    .sort((left, right) => left.distanceM - right.distanceM || left.surface.surfaceId.localeCompare(right.surface.surfaceId));

  const closest = candidates[0];
  if (!closest) {
    return { eligible: false, reason: "No eligible metric evidence supports this proxy hit." };
  }
  return {
    eligible: true,
    reason: "Resolved against eligible metric evidence; independent verification is still required for verified status.",
    metricSurfaceId: closest.surface.surfaceId,
    entityId: closest.surface.entityId,
    resolvedPoint: closest.surface.point,
    uncertaintyM: closest.surface.uncertaintyM,
    sourceAssetIds: closest.surface.sourceAssetIds
  };
}

export function directProxyMeasurement(): never {
  throw new Error("PROXY_MEASUREMENT_DENIED: a proxy hit cannot directly create an authoritative measurement");
}

export function reprojectAnchors(
  anchors: readonly StableAnchor[],
  replacementSurfaces: readonly MetricSurface[],
  maximumDistanceM = 0.25
): ReprojectionResult {
  if (!Number.isFinite(maximumDistanceM) || maximumDistanceM <= 0) {
    throw new RangeError("maximumDistanceM must be positive");
  }
  const resolved: StableAnchor[] = [];
  const unresolved: { anchorId: string; reason: string }[] = [];
  for (const anchor of anchors) {
    const candidates = replacementSurfaces
      .filter((surface) => surface.entityId === anchor.entityId && surface.coordinateFrameId === anchor.coordinateFrameId)
      .map((surface) => ({ surface, distanceM: distance(anchor.worldPoint, surface.point) }))
      .sort((left, right) => left.distanceM - right.distanceM || left.surface.surfaceId.localeCompare(right.surface.surfaceId));
    const closest = candidates[0];
    if (!closest || closest.distanceM > maximumDistanceM) {
      unresolved.push({ anchorId: anchor.anchorId, reason: "No same-entity metric support within reprojection tolerance." });
      continue;
    }
    resolved.push({ ...anchor, worldPoint: closest.surface.point });
  }
  return { resolved, unresolved };
}

export interface ViewerSnapshot {
  readonly schema: "sip.viewer-session";
  readonly schemaVersion: "1.1.0";
  readonly sceneCommitId: string;
  readonly layers: readonly LayerState[];
  readonly selectedEntityId: string | null;
  readonly clippingPlanes: readonly { normal: readonly [number, number, number]; constant: number }[];
  readonly timelineInstant: string | null;
}

export function serializeViewerSnapshot(snapshot: ViewerSnapshot): string {
  const ordered = {
    ...snapshot,
    layers: [...snapshot.layers].sort((a, b) => a.kind.localeCompare(b.kind)),
    clippingPlanes: [...snapshot.clippingPlanes]
  };
  return JSON.stringify(ordered);
}
