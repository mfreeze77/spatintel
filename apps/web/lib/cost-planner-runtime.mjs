const expensiveTiers = new Set(["photorealistic", "gpu-high", "final-splat"]);
const SHA256 = /^[a-f0-9]{64}$/;
const CURRENCY = /^[A-Z]{3}$/;

export function summarizeCostEstimate(estimate, nowMs = Date.now()) {
  if (!Number.isFinite(estimate.totalAmount) || estimate.totalAmount < 0) throw new Error("COST_ESTIMATE_INVALID");
  const currency = String(estimate.currency).toUpperCase();
  if (!CURRENCY.test(currency)) throw new Error("COST_CURRENCY_INVALID");
  const expiresAt = new Date(estimate.expiresAt);
  if (!Number.isFinite(expiresAt.getTime())) throw new Error("COST_EXPIRY_INVALID");
  return Object.freeze({
    amount: estimate.totalAmount,
    currency,
    processingTier: estimate.processingTier,
    expensive: expensiveTiers.has(estimate.processingTier),
    priceSourceVersion: estimate.priceSourceVersion,
    expiresAt: expiresAt.toISOString(),
    requiresFreshEstimate: expiresAt.getTime() <= nowMs,
    evidenceClass: estimate.evidenceClass ?? "estimate",
  });
}

export function finalReconstructionAdmission(summary, acknowledged) {
  if (summary.requiresFreshEstimate) return Object.freeze({ allowed: false, reason: "STALE_COST_ESTIMATE" });
  if (summary.expensive && !acknowledged) return Object.freeze({ allowed: false, reason: "COST_ACKNOWLEDGEMENT_REQUIRED" });
  return Object.freeze({ allowed: true, reason: null });
}

export function validateCostEstimate(estimate, now = new Date()) {
  if (!estimate.estimateId || !estimate.processingTier || !estimate.priceSourceVersion) throw new Error("COST_ESTIMATE_IDENTITY_INCOMPLETE");
  if (!Number.isFinite(estimate.totalAmount) || estimate.totalAmount < 0) throw new Error("COST_ESTIMATE_AMOUNT_INVALID");
  if (!CURRENCY.test(estimate.currency) || !SHA256.test(estimate.priceSourceHash)) throw new Error("COST_ESTIMATE_PRICE_SOURCE_INVALID");
  const expiration = new Date(estimate.expiresAt);
  if (Number.isNaN(expiration.getTime())) throw new Error("COST_ESTIMATE_EXPIRATION_INVALID");
  const stale = expiration.getTime() <= now.getTime();
  if (stale) return Object.freeze({ canStart: false, reason: "Estimate expired—refresh pricing before admission.", stale: true });
  if (estimate.state !== "active") return Object.freeze({ canStart: false, reason: `Estimate is ${estimate.state}.`, stale: false });
  return Object.freeze({ canStart: true, reason: "Current governed estimate is eligible for server-side budget admission.", stale: false });
}

export function formatCost(amount, currency) {
  if (!Number.isFinite(amount) || amount < 0 || !CURRENCY.test(currency)) throw new Error("COST_DISPLAY_INVALID");
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 2 }).format(amount);
}

export function orderedCostStages(stages) {
  return [...stages].map((stage) => {
    if (!stage.stage || !Number.isFinite(stage.amount) || stage.amount < 0 || !Number.isFinite(stage.weight) || stage.weight < 0) throw new Error("COST_STAGE_INVALID");
    return Object.freeze({ ...stage });
  }).sort((left, right) => left.stage.localeCompare(right.stage));
}
