"use client";
import { useMemo, useState } from "react";
import { AuthorityBadge } from "./AuthorityBadge";
import { LayerControls } from "./LayerControls";
import { HybridCanvas } from "./HybridCanvas";
import {
  defaultLayers,
  directProxyMeasurement,
  reprojectAnchors,
  resolveProxyHit,
  updateLayer,
  type LayerState,
  type MetricSurface,
  type RepresentationKind,
  type StableAnchor
} from "../lib/spatial-runtime";

const surfaces: readonly MetricSurface[] = [
  { surfaceId: "surface-room-wall", entityId: "room-101", coordinateFrameId: "building-frame", point: [2, 1.2, -0.4], toleranceM: 0.18, uncertaintyM: 0.025, sourceAssetIds: ["asset-depth-001"] }
];
const anchors: readonly StableAnchor[] = [
  { anchorId: "anchor-panel", entityId: "room-101", coordinateFrameId: "building-frame", worldPoint: [2.02, 1.19, -0.39] },
  { anchorId: "anchor-unresolved", entityId: "door-102", coordinateFrameId: "building-frame", worldPoint: [8, 0, 0] }
];

export function HybridViewer(): React.ReactNode {
  const [layers, setLayers] = useState<readonly LayerState[]>(() => defaultLayers());
  const [message, setMessage] = useState("Select an entity or proxy surface to inspect its evidence.");
  const [reducedMotion, setReducedMotion] = useState(true);
  const [highContrast, setHighContrast] = useState(false);
  const [clippingEnabled, setClippingEnabled] = useState(false);
  const reprojection = useMemo(() => reprojectAnchors(anchors, surfaces), []);

  const patchLayer = (kind: RepresentationKind, patch: Partial<Pick<LayerState, "visible" | "opacity">>): void => {
    setLayers((current) => updateLayer(current, kind, patch));
  };
  const inspectProxy = (): void => {
    const result = resolveProxyHit({ proxyRepresentationId: "proxy-v2", proxyElementId: "face-17", coordinateFrameId: "building-frame", point: [2.04, 1.21, -0.38] }, surfaces);
    setMessage(result.eligible ? `${result.reason} Uncertainty ±${result.uncertaintyM?.toFixed(3)} m.` : result.reason);
  };
  const tryDirectMeasurement = (): void => {
    try { directProxyMeasurement(); } catch (error) { setMessage(error instanceof Error ? error.message : "Measurement denied"); }
  };

  return (
    <section className="viewer-shell" aria-labelledby="viewer-heading">
      <div className="viewer-toolbar">
        <div><h2 id="viewer-heading">Hybrid spatial viewer</h2><p>Scene commit <code>demo-main-0007</code></p></div>
        <div className="toolbar-actions"><button type="button" onClick={inspectProxy}>Inspect proxy hit</button><button type="button" onClick={tryDirectMeasurement}>Attempt direct measurement</button></div>
      </div>
      <div className="viewer-grid">
        <LayerControls layers={layers} onToggle={(kind, visible) => patchLayer(kind, { visible })} onOpacity={(kind, opacity) => patchLayer(kind, { opacity })} />
        <div className="viewport" tabIndex={0} role="application" aria-label="Hybrid spatial scene. Arrow keys or W A S D navigate; Home restores the saved view; the semantic scene tree remains available.">
          <HybridCanvas layers={layers} reducedMotion={reducedMotion} highContrast={highContrast} clippingEnabled={clippingEnabled} comparisonSplit={0.72} onSemanticPick={(entityId) => { inspectProxy(); setMessage(`Interaction proxy selected ${entityId}. Metric re-resolution is required before measurement.`); }} />
          <div className="truth-overlay" aria-label="Persistent truth labels">
            <AuthorityBadge authority="observed" confidence={0.91} />
            <AuthorityBadge authority="generated" />
            <AuthorityBadge authority="derived_non_authoritative" />
          </div>
        </div>
      </div>
      <fieldset className="accessibility-controls"><legend>Viewer accessibility and safety</legend><label><input type="checkbox" checked={reducedMotion} onChange={(event) => setReducedMotion(event.target.checked)} /> Reduced motion</label><label><input type="checkbox" checked={highContrast} onChange={(event) => setHighContrast(event.target.checked)} /> High contrast</label><label><input type="checkbox" checked={clippingEnabled} onChange={(event) => setClippingEnabled(event.target.checked)} /> Section clipping</label><span>Captions and semantic alternatives enabled</span></fieldset>
      <p className="status-message" role="status" aria-live="polite">{message}</p>
      <details><summary>Proxy replacement and anchor reprojection report</summary><p>{reprojection.resolved.length} anchor resolved; {reprojection.unresolved.length} unresolved.</p>{reprojection.unresolved.map((item) => <p key={item.anchorId}><code>{item.anchorId}</code>: {item.reason}</p>)}</details>
      <nav aria-label="Semantic scene tree"><ul className="scene-tree"><li><button type="button" onClick={() => setMessage("Room 101 selected. Observed geometry; not independently verified.")}>Room 101</button><ul><li>Fire alarm panel</li><li>Door 102</li><li>Supply diffuser</li></ul></li></ul></nav>
    </section>
  );
}
