import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const required = [
  "app/layout.tsx", "app/page.tsx", "app/construction/page.tsx", "app/liveforever/page.tsx",
  "components/HybridViewer.tsx", "components/HybridCanvas.tsx", "components/EvidencePanel.tsx", "components/SafeExperienceControls.tsx",
  "lib/spatial-runtime.ts", "lib/renderer.ts", "lib/hybrid-renderer.ts", "lib/cost-planner.ts", "lib/cost-planner-runtime.mjs", "components/CostEstimatePanel.tsx", "next.config.ts"
];
for (const relative of required) assert.equal((await stat(path.join(root, relative))).isFile(), true, relative);
const files = Object.fromEntries(await Promise.all(required.map(async (relative) => [relative, await readFile(path.join(root, relative), "utf8")])));
const checks = [
  ["lib/spatial-runtime.ts", "directProxyMeasurement"], ["lib/spatial-runtime.ts", "resolveProxyHit"], ["lib/spatial-runtime.ts", "reprojectAnchors"],
  ["lib/spatial-runtime.ts", "derived_non_authoritative"], ["lib/spatial-runtime.ts", "sourceAssetIds"], ["lib/spatial-runtime.ts", "validateViewerSessionState"],
  ["lib/spatial-runtime.ts", "selectDeterministicLod"], ["lib/spatial-runtime.ts", "planResourceAdmission"], ["lib/spatial-runtime.ts", "pickInteractionOnly"],
  ["lib/spatial-runtime.ts", "pointPassesClipping"], ["lib/spatial-runtime.ts", "synchronizedComparison"], ["lib/spatial-runtime.ts", "interactionDiagnostics"],
  ["lib/spatial-runtime.ts", "semanticFallback"], ["lib/spatial-runtime.ts", "navigationFromKey"], ["lib/hybrid-renderer.ts", "loadGaussianSplat"],
  ["lib/hybrid-renderer.ts", "role === \"interaction\""], ["components/HybridCanvas.tsx", "THREE.Points"], ["components/HybridCanvas.tsx", "Raycaster"],
  ["components/HybridCanvas.tsx", "ResizeObserver"], ["components/HybridCanvas.tsx", "observer?.disconnect()"],
  ["components/HybridCanvas.tsx", "removeEventListener(\"pointerdown\""], ["components/HybridCanvas.tsx", "buildLayerRenderDirectives(layers, comparisonSplit)"],
  ["components/HybridCanvas.tsx", "interactionDirective.pickable"], ["components/HybridCanvas.tsx", "evidence:asset-depth-001"],
  ["components/HybridCanvas.tsx", "re-resolved against metric evidence"], ["components/HybridViewer.tsx", "layers={layers}"], ["components/HybridViewer.tsx", "Reduced motion"],
  ["components/HybridViewer.tsx", "High contrast"], ["components/HybridViewer.tsx", "Captions and semantic alternatives enabled"], ["app/liveforever/page.tsx", "GENERATED RECONSTRUCTION"],
  ["app/construction/page.tsx", "not survey-grade"], ["app/construction/page.tsx", "Verification date"],
  ["components/CostEstimatePanel.tsx", "Estimate—not an invoice"], ["components/CostEstimatePanel.tsx", "Server-side budget admission"],
  ["lib/cost-planner.ts", "STALE_COST_ESTIMATE"]
];
for (const [relative, invariant] of checks) assert.ok(files[relative].includes(invariant), `${relative}:${invariant}`);
console.log(JSON.stringify({ status: "passed", checkedFiles: required.length, invariantChecks: checks.length }));
