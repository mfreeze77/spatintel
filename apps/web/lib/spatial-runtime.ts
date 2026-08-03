export const REPRESENTATION_KINDS = ["metric", "visual", "design", "interaction", "evidence"] as const;
export type RepresentationKind = (typeof REPRESENTATION_KINDS)[number];
export type AuthorityClass = "authoritative" | "verified" | "measured" | "observed" | "inferred" | "generated" | "derived_non_authoritative";

export interface LayerState {
  readonly kind: RepresentationKind;
  readonly visible: boolean;
  readonly opacity: number;
  readonly authorized: boolean;
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
    authorized: true,
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
  const current = layers.find((layer) => layer.kind === kind);
  if (!current) throw new Error(`unknown representation layer: ${kind}`);
  if (patch.visible === true && current.authorized !== true) {
    throw new Error(`LAYER_AUTHORIZATION_DENIED:${kind}`);
  }
  return layers.map((layer) => (layer.kind === kind ? { ...layer, ...patch } : layer));
}

export interface RenderLayerDirective {
  readonly role: RepresentationKind;
  readonly visible: boolean;
  readonly opacity: number;
  readonly pickable: boolean;
  readonly authority: AuthorityClass;
  readonly authorityLabel: string;
}

const BASE_RENDER_OPACITY: Readonly<Record<RepresentationKind, number>> = {
  metric: 0.42,
  visual: 0.58,
  design: 0.85,
  interaction: 0.03,
  evidence: 0.95
};

const ROLE_LABELS: Readonly<Record<RepresentationKind, string>> = {
  metric: "metric / observed evidence",
  visual: "visual / generated reconstruction",
  design: "design / intent only",
  interaction: "interaction / disposable non-authoritative proxy",
  evidence: "evidence / immutable source record"
};

export function buildLayerRenderDirectives(
  layers: readonly LayerState[],
  comparisonSplit = 1
): readonly RenderLayerDirective[] {
  if (!Number.isFinite(comparisonSplit) || comparisonSplit < 0 || comparisonSplit > 1) {
    throw new RangeError("comparison split must be between zero and one");
  }
  const byRole = new Map(layers.map((layer) => [layer.kind, layer] as const));
  return REPRESENTATION_KINDS.map((role) => {
    const layer = byRole.get(role);
    if (!layer) throw new Error(`missing representation layer: ${role}`);
    const comparisonOpacity = role === "visual" ? comparisonSplit : 1;
    const opacity = BASE_RENDER_OPACITY[role] * layer.opacity * comparisonOpacity;
    const visible = layer.authorized === true && layer.visible === true && opacity > 0;
    return {
      role,
      visible,
      opacity,
      pickable: role === "interaction" && visible,
      authority: layer.authority,
      authorityLabel: ROLE_LABELS[role]
    };
  });
}

export function layerDirective(
  directives: readonly RenderLayerDirective[],
  role: RepresentationKind
): RenderLayerDirective {
  const directive = directives.find((item) => item.role === role);
  if (!directive) throw new Error(`missing render directive: ${role}`);
  return directive;
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

export type HybridRole = "metric" | "visual" | "design" | "interaction" | "evidence";
export interface LodLevel { readonly level: number; readonly representationId: string; readonly maximumScreenError: number; readonly triangles: number; readonly splats: number; readonly gpuBytes: number; }
export interface ResourceBudget { readonly maxTriangles: number; readonly maxSplats: number; readonly maxGpuBytes: number; readonly maxDrawCalls: number; }
export interface RenderResource { readonly id: string; readonly role: HybridRole; readonly priority: number; readonly triangles?: number; readonly splats?: number; readonly gpuBytes?: number; readonly drawCalls?: number; }

const ROLE_ORDER: readonly HybridRole[] = ["metric", "visual", "design", "interaction", "evidence"];
const CAPABILITY_KEYS = new Set(["token", "access_token", "refresh_token", "authorization", "bearer", "signed_url", "presigned_url", "credential", "secret", "password", "storage_key", "provider_key"]);
function assertNoCapabilities(value: unknown, path = "root"): void {
  if (Array.isArray(value)) { value.forEach((item, index) => assertNoCapabilities(item, `${path}[${index}]`)); return; }
  if (!value || typeof value !== "object") return;
  for (const [key, item] of Object.entries(value)) {
    const normalized = key.toLowerCase().replaceAll("-", "_");
    if (CAPABILITY_KEYS.has(normalized)) throw new Error(`VIEWER_CAPABILITY_MATERIAL_DENIED:${path}.${key}`);
    assertNoCapabilities(item, `${path}.${key}`);
  }
}
type ViewerSessionState = Readonly<{
  sceneCommitIds?: unknown;
  redaction?: Readonly<{ serverEnforced?: unknown }>;
  accessibility?: Readonly<Record<string, unknown>>;
  comparison?: Readonly<{ secondaryCommitId?: unknown }>;
  [key: string]: unknown;
}>;

export function validateViewerSessionState(state: ViewerSessionState): true {
  assertNoCapabilities(state);
  if (!Array.isArray(state.sceneCommitIds) || state.sceneCommitIds.length < 1 || state.sceneCommitIds.length > 2) throw new Error("VIEWER_COMMIT_SET_INVALID");
  if (new Set(state.sceneCommitIds).size !== state.sceneCommitIds.length) throw new Error("VIEWER_COMMIT_SET_DUPLICATE");
  if (state.redaction?.serverEnforced !== true) throw new Error("VIEWER_REDACTION_NOT_SERVER_ENFORCED");
  for (const key of ["reducedMotion", "highContrast", "captions"]) if (typeof state.accessibility?.[key] !== "boolean") throw new Error(`VIEWER_ACCESSIBILITY_MISSING:${key}`);
  if (state.sceneCommitIds.length === 2 && !state.comparison?.secondaryCommitId) throw new Error("VIEWER_COMPARISON_STATE_REQUIRED");
  return true;
}
export function selectDeterministicLod(levels: readonly LodLevel[], targetScreenError: number, budget: ResourceBudget): LodLevel | null {
  if (!Number.isFinite(targetScreenError) || targetScreenError < 0) throw new RangeError("targetScreenError must be non-negative");
  const ordered = [...levels].sort((a, b) => b.level - a.level || a.representationId.localeCompare(b.representationId));
  return ordered.find((item) => item.maximumScreenError <= targetScreenError && item.triangles <= budget.maxTriangles && item.splats <= budget.maxSplats && item.gpuBytes <= budget.maxGpuBytes)
    ?? [...levels].sort((a, b) => a.level - b.level || a.representationId.localeCompare(b.representationId))[0] ?? null;
}
export function planResourceAdmission(resources: readonly RenderResource[], budget: ResourceBudget): { admitted: readonly RenderResource[]; rejected: readonly { id: string; reason: string }[]; totals: { triangles: number; splats: number; gpuBytes: number; drawCalls: number } } {
  const totals = { triangles: 0, splats: 0, gpuBytes: 0, drawCalls: 0 }; const admitted: RenderResource[] = []; const rejected: { id: string; reason: string }[] = [];
  const ordered = [...resources].sort((a, b) => a.priority - b.priority || ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role) || a.id.localeCompare(b.id));
  for (const resource of ordered) {
    const next = { triangles: totals.triangles + (resource.triangles ?? 0), splats: totals.splats + (resource.splats ?? 0), gpuBytes: totals.gpuBytes + (resource.gpuBytes ?? 0), drawCalls: totals.drawCalls + (resource.drawCalls ?? 1) };
    if (next.triangles <= budget.maxTriangles && next.splats <= budget.maxSplats && next.gpuBytes <= budget.maxGpuBytes && next.drawCalls <= budget.maxDrawCalls) { admitted.push(resource); Object.assign(totals, next); }
    else rejected.push({ id: resource.id, reason: "resource_budget_exceeded" });
  }
  return { admitted, rejected, totals };
}
export function pickInteractionOnly<T extends { role: HybridRole; interactive: boolean; distance: number; stableEntityId: string }>(hits: readonly T[]): T | null {
  return [...hits].filter((hit) => hit.role === "interaction" && hit.interactive).sort((a, b) => a.distance - b.distance || a.stableEntityId.localeCompare(b.stableEntityId))[0] ?? null;
}
export function pointPassesClipping(point: readonly [number, number, number], planes: readonly { normal: readonly [number, number, number]; constant: number }[] = [], sectionBox: { min: readonly [number, number, number]; max: readonly [number, number, number] } | null = null): boolean {
  if (sectionBox && point.some((value, index) => value < sectionBox.min[index]! || value > sectionBox.max[index]!)) return false;
  return planes.every((plane) => plane.normal[0] * point[0] + plane.normal[1] * point[1] + plane.normal[2] * point[2] + plane.constant >= 0);
}
export function synchronizedComparison<T extends { cameraId: string }>(primary: T, secondary: T, split = 0.5): { primary: T & { opacity: number }; secondary: T & { opacity: number }; synchronizedCameraId: string | null } {
  if (!Number.isFinite(split) || split < 0 || split > 1) throw new RangeError("comparison split must be between zero and one");
  return { primary: { ...primary, opacity: 1 - split }, secondary: { ...secondary, opacity: split }, synchronizedCameraId: primary.cameraId === secondary.cameraId ? primary.cameraId : null };
}
export function interactionDiagnostics(sources: Readonly<Record<string, { sourceId?: string }>>): { healthy: boolean; missing: readonly string[]; duplicateSourceIds: boolean } {
  const required = ["collision", "navigation", "occlusion", "clipping", "spatial_audio"];
  const missing = required.filter((key) => !sources[key]?.sourceId); const identifiers = required.map((key) => sources[key]?.sourceId).filter((value): value is string => Boolean(value)); const duplicate = identifiers.length !== new Set(identifiers).size;
  return { healthy: missing.length === 0 && !duplicate, missing, duplicateSourceIds: duplicate };
}
export function semanticFallback(entities: readonly { stableEntityId: string; label: string; authorityLabel: string; evidenceIds?: readonly string[] }[], capabilities: { webgl: boolean; webgpu: boolean }): { mode: "hybrid" | "semantic"; entities: readonly { stableEntityId: string; label: string; authorityLabel: string; evidenceCount: number }[]; renderUnavailableReason: string | null } {
  const renderAvailable = capabilities.webgl || capabilities.webgpu;
  return { mode: renderAvailable ? "hybrid" : "semantic", entities: entities.map((entity) => ({ stableEntityId: entity.stableEntityId, label: entity.label, authorityLabel: entity.authorityLabel, evidenceCount: entity.evidenceIds?.length ?? 0 })), renderUnavailableReason: renderAvailable ? null : "WebGL/WebGPU unavailable; semantic scene tree retained." };
}
export function navigationFromKey<T extends { position: readonly [number, number, number]; savedPosition: readonly [number, number, number]; reducedMotion: boolean }>(state: T, key: string): T {
  const step = state.reducedMotion ? 0.1 : 0.25; const position: [number, number, number] = [...state.position];
  if (["ArrowUp", "w", "W"].includes(key)) position[2] -= step; else if (["ArrowDown", "s", "S"].includes(key)) position[2] += step; else if (["ArrowLeft", "a", "A"].includes(key)) position[0] -= step; else if (["ArrowRight", "d", "D"].includes(key)) position[0] += step; else if (key === "Home") return { ...state, position: [...state.savedPosition] } as T; else return state;
  return { ...state, position } as T;
}
