import Link from "next/link";
import { HybridViewer } from "../components/HybridViewer";

export default function HomePage(): React.ReactNode {
  return (
    <>
      <section className="hero"><p className="eyebrow">Evidence before appearance</p><h1>One scene, multiple truths—never silently collapsed.</h1><p>SIP keeps measured reality, visual reconstruction, interaction proxies, design intent, and immutable evidence in separate governed lanes.</p><div className="hero-actions"><Link className="button" href="/construction">Open Construction demo</Link><Link className="button secondary" href="/liveforever">Open LiveForever demo</Link></div></section>
      <HybridViewer />
      <section className="cards" aria-label="Platform capabilities">
        <article><h2>Metric lane</h2><p>Coordinate-aware geometry, uncertainty, calibration, and independent verification state.</p></article>
        <article><h2>Visual lane</h2><p>Gaussian and photorealistic representations that never become measurements by appearance alone.</p></article>
        <article><h2>Policy lane</h2><p>Tenant, project, purpose, consent, audience, classification, and region enforcement on the server.</p></article>
      </section>
    </>
  );
}
