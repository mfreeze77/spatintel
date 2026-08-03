export type Vector3 = readonly [number, number, number];
export type Triangle = readonly [number, number, number];

export interface LocalViewerBundle {
  readonly schema: "spatintel.viewer-bundle/v1";
  readonly bundle_hash: string;
  readonly metric: {
    readonly vertices: readonly Vector3[];
    readonly faces: readonly Triangle[];
    readonly colors: readonly Vector3[];
    readonly authority: "metric_unverified";
  };
  readonly visual: {
    readonly positions: readonly Vector3[];
    readonly colors: readonly Vector3[];
    readonly authority: "visual_non_metric";
  };
  readonly interaction: {
    readonly vertices: readonly Vector3[];
    readonly faces: readonly Triangle[];
    readonly authority: "derived_non_authoritative";
  };
  readonly quality: Readonly<Record<string, unknown>>;
  readonly provenance: Readonly<Record<string, unknown>>;
}

export function parseLocalViewerBundle(value: unknown): LocalViewerBundle {
  if (!isRecord(value) || value.schema !== "spatintel.viewer-bundle/v1") throw new Error("VIEWER_BUNDLE_SCHEMA_INVALID");
  const metric = geometry(value.metric, true);
  const visual = points(value.visual);
  const interaction = geometry(value.interaction, false);
  if (metric.authority !== "metric_unverified") throw new Error("VIEWER_BUNDLE_METRIC_AUTHORITY_INVALID");
  if (visual.authority !== "visual_non_metric") throw new Error("VIEWER_BUNDLE_VISUAL_AUTHORITY_INVALID");
  if (interaction.authority !== "derived_non_authoritative") throw new Error("VIEWER_BUNDLE_INTERACTION_AUTHORITY_INVALID");
  return {
    schema: "spatintel.viewer-bundle/v1",
    bundle_hash: text(value.bundle_hash, "VIEWER_BUNDLE_HASH_INVALID"),
    metric: { ...metric, authority: "metric_unverified" },
    visual: { ...visual, authority: "visual_non_metric" },
    interaction: { ...interaction, authority: "derived_non_authoritative" },
    quality: isRecord(value.quality) ? value.quality : {},
    provenance: isRecord(value.provenance) ? value.provenance : {}
  };
}

function geometry(value: unknown, colorsRequired: boolean): { vertices: Vector3[]; faces: Triangle[]; colors: Vector3[]; authority: string } {
  if (!isRecord(value)) throw new Error("VIEWER_BUNDLE_GEOMETRY_INVALID");
  const vertices = vectors(value.vertices, "VIEWER_BUNDLE_VERTICES_INVALID");
  const faces = triangles(value.faces, vertices.length);
  const colors = value.colors === undefined ? [] : vectors(value.colors, "VIEWER_BUNDLE_COLORS_INVALID");
  if (colorsRequired && colors.length !== 0 && colors.length !== vertices.length) throw new Error("VIEWER_BUNDLE_COLORS_INVALID");
  return { vertices, faces, colors, authority: text(value.authority, "VIEWER_BUNDLE_AUTHORITY_INVALID") };
}

function points(value: unknown): { positions: Vector3[]; colors: Vector3[]; authority: string } {
  if (!isRecord(value)) throw new Error("VIEWER_BUNDLE_VISUAL_INVALID");
  const positions = vectors(value.positions, "VIEWER_BUNDLE_POSITIONS_INVALID");
  const colors = vectors(value.colors, "VIEWER_BUNDLE_COLORS_INVALID");
  if (colors.length !== 0 && colors.length !== positions.length) throw new Error("VIEWER_BUNDLE_COLORS_INVALID");
  return { positions, colors, authority: text(value.authority, "VIEWER_BUNDLE_AUTHORITY_INVALID") };
}

function vectors(value: unknown, code: string): Vector3[] {
  if (!Array.isArray(value)) throw new Error(code);
  return value.map((item) => {
    if (!Array.isArray(item) || item.length !== 3 || item.some((entry) => typeof entry !== "number" || !Number.isFinite(entry))) throw new Error(code);
    return [item[0], item[1], item[2]] as const;
  });
}

function triangles(value: unknown, vertexCount: number): Triangle[] {
  if (!Array.isArray(value)) throw new Error("VIEWER_BUNDLE_FACES_INVALID");
  return value.map((item) => {
    if (!Array.isArray(item) || item.length !== 3 || item.some((entry) => !Number.isInteger(entry) || entry < 0 || entry >= vertexCount)) throw new Error("VIEWER_BUNDLE_FACES_INVALID");
    return [item[0], item[1], item[2]] as const;
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, code: string): string {
  if (typeof value !== "string" || value.length === 0) throw new Error(code);
  return value;
}
