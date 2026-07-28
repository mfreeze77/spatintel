"use client";
import type { LayerState, RepresentationKind } from "../lib/spatial-runtime";

export function LayerControls({ layers, onToggle, onOpacity }: {
  layers: readonly LayerState[];
  onToggle: (kind: RepresentationKind, visible: boolean) => void;
  onOpacity: (kind: RepresentationKind, opacity: number) => void;
}): React.ReactNode {
  return (
    <fieldset className="layer-controls">
      <legend>Representation layers</legend>
      {layers.map((layer) => (
        <div className="layer-control" key={layer.kind}>
          <label>
            <input type="checkbox" checked={layer.visible} disabled={!layer.authorized} aria-label={`${layer.kind} representation visibility`} onChange={(event) => onToggle(layer.kind, event.currentTarget.checked)} />
            <span>{layer.kind}</span> <small>{layer.authority}</small>
          </label>
          <label className="opacity-label">
            <span className="sr-only">{layer.kind} opacity</span>
            <input type="range" min="0" max="1" step="0.05" value={layer.opacity} disabled={!layer.visible || !layer.authorized} onChange={(event) => onOpacity(layer.kind, Number(event.currentTarget.value))} />
          </label>
          {!layer.authorized ? <p className="layer-warning">This representation is not authorized for the current view.</p> : layer.warning ? <p className="layer-warning">{layer.warning}</p> : null}
        </div>
      ))}
    </fieldset>
  );
}
