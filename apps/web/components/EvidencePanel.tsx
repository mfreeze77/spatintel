import { AuthorityBadge } from "./AuthorityBadge";
import type { AuthorityClass } from "../lib/spatial-runtime";

export interface EvidenceItem {
  readonly assetId: string;
  readonly name: string;
  readonly mediaType: string;
  readonly authority: AuthorityClass;
  readonly confidence: number;
  readonly immutableHash: string;
  readonly capturedAt: string;
}

export function EvidencePanel({ items }: { items: readonly EvidenceItem[] }): React.ReactNode {
  return (
    <section className="panel" aria-labelledby="evidence-title">
      <h2 id="evidence-title">Evidence and provenance</h2>
      {items.length === 0 ? <p>No evidence is authorized for this view.</p> : (
        <ol className="evidence-list">
          {items.map((item) => (
            <li key={item.assetId}>
              <div className="evidence-heading"><strong>{item.name}</strong><AuthorityBadge authority={item.authority} confidence={item.confidence} /></div>
              <dl>
                <dt>Media type</dt><dd>{item.mediaType}</dd>
                <dt>Captured</dt><dd>{item.capturedAt}</dd>
                <dt>Immutable SHA-256</dt><dd><code>{item.immutableHash}</code></dd>
              </dl>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
