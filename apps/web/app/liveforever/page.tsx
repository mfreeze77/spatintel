import { AuthorityBadge } from "../../components/AuthorityBadge";
import { EvidencePanel, type EvidenceItem } from "../../components/EvidencePanel";
import { SafeExperienceControls } from "../../components/SafeExperienceControls";

const evidence: readonly EvidenceItem[] = [
  { assetId: "interview-001", name: "Synthetic interview recording", mediaType: "audio/wav", authority: "authoritative", confidence: 1, immutableHash: "c1a7b2de089270004b5a669d606e049df73e05ef2f94a90783d6880a47fce179", capturedAt: "2026-07-27T15:00:00Z" },
  { assetId: "photo-001", name: "Synthetic porch photograph", mediaType: "image/png", authority: "authoritative", confidence: 1, immutableHash: "a59ca113f39b78f30c1e690ac20aac88ab8020557da126dcd82a787dc99712e8", capturedAt: "1989-06-10T18:00:00Z" }
];

export default function LiveForeverPage(): React.ReactNode {
  return (
    <>
      <section className="hero compact"><p className="eyebrow">LiveForever</p><h1>Memory with evidence, consent, and room for disagreement.</h1><p>Every recollection, corroboration, inference, and generated reconstruction keeps its own label and lineage.</p></section>
      <section className="timeline" aria-labelledby="timeline-heading"><h2 id="timeline-heading">Synthetic family timeline</h2><article><time dateTime="1989-06-10">June 10, 1989</time><h3>Porch gathering</h3><p>Alex recalls rain before dinner. Jordan recalls a clear evening.</p><div className="badge-row"><AuthorityBadge authority="observed" confidence={0.7} /><span className="conflict-label">Conflicting recollections preserved</span></div></article><article><time dateTime="2026-07-27">July 27, 2026</time><h3>Generated visual reconstruction</h3><p className="generated-banner">GENERATED RECONSTRUCTION — not a historical photograph or witnessed fact.</p><AuthorityBadge authority="generated" confidence={0.42} /></article></section>
      <div className="two-column"><EvidencePanel items={evidence} /><section className="panel"><h2>Audience policy</h2><table><thead><tr><th>Edition</th><th>Visible records</th><th>Generated media</th></tr></thead><tbody><tr><td>Private</td><td>Interview, letters, full transcript</td><td>Labeled, consent-bound</td></tr><tr><td>Family</td><td>Approved stories and photographs</td><td>Labeled, consent-bound</td></tr><tr><td>Public</td><td>One redacted story</td><td>Hidden</td></tr></tbody></table><p>Revoked source derivatives are removed from authorization, indexes, caches, exports, and active representations.</p></section></div>
      <SafeExperienceControls />
    </>
  );
}
