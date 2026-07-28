import { AuthorityBadge } from "../../components/AuthorityBadge";
import { EvidencePanel, type EvidenceItem } from "../../components/EvidencePanel";
import { HybridViewer } from "../../components/HybridViewer";

const evidence: readonly EvidenceItem[] = [
  { assetId: "asset-photo-001", name: "Panel east-wall photograph", mediaType: "image/jpeg", authority: "authoritative", confidence: 1, immutableHash: "9f3b05d44b31db54b89fba835f563d9b3a40dd9976cf77bd70ae8f07a360e34a", capturedAt: "2026-07-27T14:00:00Z" },
  { assetId: "asset-depth-001", name: "LiDAR depth observation", mediaType: "image/png", authority: "observed", confidence: 0.91, immutableHash: "1f4fbe7ab7199bac72618fde6d613151af01d877088db44aa8d7cb622d8e019b", capturedAt: "2026-07-27T14:00:00Z" }
];

export default function ConstructionPage(): React.ReactNode {
  return (
    <>
      <section className="hero compact"><p className="eyebrow">Construction Spatial Reference</p><h1>Observed conditions with explicit authority.</h1><p className="warning-banner">Phone-derived geometry is not survey-grade, fabrication-ready, contract-authoritative, code-compliant, or verified as-built without independent verification.</p></section>
      <section className="cards">
        <article><h2>Fire alarm</h2><p>EST4 panel, annunciator, SLC circuit, six devices, programming record, deficiency and retest.</p><AuthorityBadge authority="observed" confidence={0.92} /></article>
        <article><h2>Access control</h2><p>Opening, reader, electrified lock, door contact, REX, controller, sequence and functional test.</p><AuthorityBadge authority="measured" confidence={0.84} /></article>
        <article><h2>BAS / MEP</h2><p>Air-handling unit, points, nameplate, duct/sensor links and design-versus-observed comparison.</p><AuthorityBadge authority="inferred" confidence={0.74} /></article>
      </section>
      <HybridViewer />
      <div className="two-column"><EvidencePanel items={evidence} /><section className="panel"><h2>Field-verified measurement</h2><dl><dt>Value</dt><dd>2.438 m</dd><dt>Uncertainty</dt><dd>±0.006 m</dd><dt>Calibration</dt><dd>Certified laser reference, certificate CAL-2026-004</dd><dt>Verifier</dt><dd>synthetic-verifier-01</dd><dt>Verification date</dt><dd>July 27, 2026</dd><dt>Status</dt><dd><AuthorityBadge authority="verified" confidence={1} /></dd></dl></section></div>
    </>
  );
}
