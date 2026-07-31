export interface CostEstimateInput {
  readonly totalAmount: number;
  readonly currency: string;
  readonly processingTier: string;
  readonly priceSourceVersion: string;
  readonly expiresAt: string;
  readonly evidenceClass?: string;
}

export interface CostEstimateSummary {
  readonly amount: number;
  readonly currency: string;
  readonly processingTier: string;
  readonly expensive: boolean;
  readonly priceSourceVersion: string;
  readonly expiresAt: string;
  readonly requiresFreshEstimate: boolean;
  readonly evidenceClass: string;
}

export interface CostStageEstimate {
  readonly stage: string;
  readonly amount: number;
  readonly weight: number;
}

export interface CostEstimateView {
  readonly estimateId: string;
  readonly processingTier: string;
  readonly totalAmount: number;
  readonly currency: string;
  readonly stageEstimates: readonly CostStageEstimate[];
  readonly priceSourceVersion: string;
  readonly priceSourceHash: string;
  readonly expiresAt: string;
  readonly state: "active" | "expired" | "denied" | "consumed";
  readonly expensiveFinalReconstruction: boolean;
  readonly externalValidationRequired: boolean;
}

export interface CostEstimateDecision {
  readonly canStart: boolean;
  readonly reason: string;
  readonly stale: boolean;
}

const expensiveTiers = new Set(["photorealistic", "gpu-high", "final-splat"]);
const SHA256 = /^[a-f0-9]{64}$/;
const CURRENCY = /^[A-Z]{3}$/;

export function summarizeCostEstimate(estimate: CostEstimateInput, nowMs = Date.now()): CostEstimateSummary {
  if (!Number.isFinite(estimate.totalAmount) || estimate.totalAmount < 0) throw new Error("COST_ESTIMATE_INVALID");
  const currency = estimate.currency.toUpperCase();
  if (!CURRENCY.test(currency)) throw new Error("COST_CURRENCY_INVALID");
  const expiresAt = new Date(estimate.expiresAt);
  if (!Number.isFinite(expiresAt.getTime())) throw new Error("COST_EXPIRY_INVALID");
  return {
    amount: estimate.totalAmount,
    currency,
    processingTier: estimate.processingTier,
    expensive: expensiveTiers.has(estimate.processingTier),
    priceSourceVersion: estimate.priceSourceVersion,
    expiresAt: expiresAt.toISOString(),
    requiresFreshEstimate: expiresAt.getTime() <= nowMs,
    evidenceClass: estimate.evidenceClass ?? "estimate",
  };
}

export function finalReconstructionAdmission(summary: CostEstimateSummary, acknowledged: boolean): { readonly allowed: boolean; readonly reason: string | null } {
  if (summary.requiresFreshEstimate) return { allowed: false, reason: "STALE_COST_ESTIMATE" };
  if (summary.expensive && !acknowledged) return { allowed: false, reason: "COST_ACKNOWLEDGEMENT_REQUIRED" };
  return { allowed: true, reason: null };
}

export function validateCostEstimate(estimate: CostEstimateView, now: Date = new Date()): CostEstimateDecision {
  if (!estimate.estimateId || !estimate.processingTier || !estimate.priceSourceVersion) throw new Error("COST_ESTIMATE_IDENTITY_INCOMPLETE");
  if (!Number.isFinite(estimate.totalAmount) || estimate.totalAmount < 0) throw new Error("COST_ESTIMATE_AMOUNT_INVALID");
  if (!CURRENCY.test(estimate.currency) || !SHA256.test(estimate.priceSourceHash)) throw new Error("COST_ESTIMATE_PRICE_SOURCE_INVALID");
  const expiration = new Date(estimate.expiresAt);
  if (Number.isNaN(expiration.getTime())) throw new Error("COST_ESTIMATE_EXPIRATION_INVALID");
  const stale = expiration.getTime() <= now.getTime();
  if (stale) return { canStart: false, reason: "Estimate expired—refresh pricing before admission.", stale: true };
  if (estimate.state !== "active") return { canStart: false, reason: `Estimate is ${estimate.state}.`, stale: false };
  return { canStart: true, reason: "Current governed estimate is eligible for server-side budget admission.", stale: false };
}

export function formatCost(amount: number, currency: string): string {
  if (!Number.isFinite(amount) || amount < 0 || !CURRENCY.test(currency)) throw new Error("COST_DISPLAY_INVALID");
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 2 }).format(amount);
}

export function orderedCostStages(stages: readonly CostStageEstimate[]): readonly CostStageEstimate[] {
  return [...stages].map((stage) => {
    if (!stage.stage || !Number.isFinite(stage.amount) || stage.amount < 0 || !Number.isFinite(stage.weight) || stage.weight < 0) throw new Error("COST_STAGE_INVALID");
    return { ...stage };
  }).sort((left, right) => left.stage.localeCompare(right.stage));
}
