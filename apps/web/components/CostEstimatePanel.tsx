import { formatCost, orderedCostStages, validateCostEstimate, type CostEstimateView } from "../lib/cost-planner";

const DEFAULT_ESTIMATE: CostEstimateView = {
  estimateId: "synthetic-progress08-estimate",
  processingTier: "CPU reference",
  totalAmount: 4.25,
  currency: "USD",
  stageEstimates: [
    { stage: "fusion", amount: 2.25, weight: 1 },
    { stage: "metric-validation", amount: 2, weight: 1 },
  ],
  priceSourceVersion: "synthetic-reference-v1",
  priceSourceHash: "1111111111111111111111111111111111111111111111111111111111111111",
  expiresAt: "2099-01-01T00:00:00Z",
  state: "active",
  expensiveFinalReconstruction: false,
  externalValidationRequired: true,
};

export function CostEstimatePanel({ estimate = DEFAULT_ESTIMATE, now = new Date() }: { estimate?: CostEstimateView; now?: Date } = {}): React.ReactNode {
  const decision = validateCostEstimate(estimate, now);
  const stages = orderedCostStages(estimate.stageEstimates);
  return (
    <section className="panel" aria-labelledby="cost-estimate-title" data-estimate-id={estimate.estimateId}>
      <p className="eyebrow">Estimate—not an invoice</p>
      <h2 id="cost-estimate-title">Estimated final reconstruction cost</h2>
      <p>Review cost before optional final reconstruction. Processing tier: <strong>{estimate.processingTier}</strong>. Estimated total: <strong>{formatCost(estimate.totalAmount, estimate.currency)}</strong>.</p>
      <dl>
        <dt>Price source</dt><dd>{estimate.priceSourceVersion}</dd>
        <dt>Price-source SHA-256</dt><dd><code>{estimate.priceSourceHash}</code></dd>
        <dt>Expires</dt><dd>{estimate.expiresAt}</dd>
        <dt>External validation</dt><dd>{estimate.externalValidationRequired ? "Required before production claims" : "Not required for this synthetic profile"}</dd>
      </dl>
      <table>
        <caption>Estimated cost by deterministic processing stage</caption>
        <thead><tr><th scope="col">Stage</th><th scope="col">Estimate</th></tr></thead>
        <tbody>{stages.map((stage) => <tr key={stage.stage}><th scope="row">{stage.stage}</th><td>{formatCost(stage.amount, estimate.currency)}</td></tr>)}</tbody>
      </table>
      <p role="status">{decision.reason}</p>
      <button type="button" disabled={!decision.canStart} aria-describedby="cost-admission-note">Request budget admission for final reconstruction</button>
      <p id="cost-admission-note">Server-side budget admission enforces tenant quotas, concurrency limits, and independent override approval.</p>
    </section>
  );
}
