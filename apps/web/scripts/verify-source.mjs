import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const required = [
  "app/layout.tsx", "app/page.tsx", "app/construction/page.tsx", "app/liveforever/page.tsx",
  "components/HybridViewer.tsx", "components/EvidencePanel.tsx", "components/SafeExperienceControls.tsx",
  "lib/spatial-runtime.ts", "lib/renderer.ts", "next.config.ts"
];
for (const relative of required) assert.equal((await stat(path.join(root, relative))).isFile(), true, relative);
const runtime = await readFile(path.join(root, "lib/spatial-runtime.ts"), "utf8");
for (const invariant of ["directProxyMeasurement", "resolveProxyHit", "reprojectAnchors", "derived_non_authoritative", "sourceAssetIds"]) assert.ok(runtime.includes(invariant), invariant);
const live = await readFile(path.join(root, "app/liveforever/page.tsx"), "utf8");
for (const invariant of ["GENERATED RECONSTRUCTION", "Conflicting recollections", "Revoked"]) assert.ok(live.includes(invariant), invariant);
const construction = await readFile(path.join(root, "app/construction/page.tsx"), "utf8");
for (const invariant of ["not survey-grade", "Uncertainty", "Verification date"]) assert.ok(construction.includes(invariant), invariant);
console.log(JSON.stringify({ status: "passed", checkedFiles: required.length, invariantChecks: 11 }));
