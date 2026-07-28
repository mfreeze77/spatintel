import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Spatial Intelligence Platform",
  description: "Evidence-aware hybrid spatial review for Construction and LiveForever"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>): React.ReactNode {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">Skip to main content</a>
        <header className="site-header">
          <div><span className="eyebrow">SIP v1.1.0</span><strong>Spatial Intelligence Platform</strong></div>
          <nav aria-label="Primary"><Link href="/">Overview</Link><Link href="/construction">Construction</Link><Link href="/liveforever">LiveForever</Link></nav>
        </header>
        <main id="main-content">{children}</main>
        <footer><p>Metric, visual, interaction, design, and evidence representations remain distinct.</p></footer>
      </body>
    </html>
  );
}
