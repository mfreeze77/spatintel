"use client";
import { useState } from "react";

export function SafeExperienceControls(): React.ReactNode {
  const [quiet, setQuiet] = useState(true);
  const [paused, setPaused] = useState(false);
  const [exited, setExited] = useState(false);
  if (exited) return <section className="panel safe-exit" role="status"><h2>Experience safely exited</h2><p>No immersive content is running. Return only when ready.</p><button type="button" onClick={() => setExited(false)}>Return to review</button></section>;
  return (
    <section className="panel" aria-labelledby="safety-heading">
      <h2 id="safety-heading">Experience safety</h2>
      <p>Voice, likeness, dialogue, and first-person simulation remain disabled until explicit consent and safety gates pass.</p>
      <div className="toolbar-actions">
        <button type="button" aria-pressed={quiet} onClick={() => setQuiet((value) => !value)}>Quiet mode: {quiet ? "on" : "off"}</button>
        <button type="button" aria-pressed={paused} onClick={() => setPaused((value) => !value)}>{paused ? "Resume" : "Pause"}</button>
        <button type="button" onClick={() => { setPaused(false); setQuiet(true); }}>Reset</button>
        <button type="button" className="danger" onClick={() => setExited(true)}>Safe exit</button>
      </div>
    </section>
  );
}
