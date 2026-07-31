# Progress 08 SLO and Performance-Budget Runbook

SLOs and budgets are versioned records. They state endpoint or workflow class, viewer/device tier, capture and processing profile, execution profile, model/checkpoint, queue class, objective, window, thresholds, evidence class, and source manifest hash. Synthetic/local evidence is never presented as deployed, physical-device, browser, or GPU evidence.

## SLO lifecycle

1. Register a versioned definition before collecting compliance evidence.
2. Record measurements with exact window, sample count, value, evidence class, and source hash.
3. Compare against the objective and retain error-budget state.
4. Alert on fast and slow burn without exposing tenant identifiers or restricted values.
5. Supersede by a new version; never rewrite historical measurements.

## Required classes

- API availability and latency by route template and result-size class.
- Search latency and freshness by query/result-size class.
- Queue wait, execution duration, retry, and failure by low-cardinality worker capability.
- Viewer first-meaningful-scene, frame time, memory, network, and scene-size tier.
- iOS responsiveness, bounded frame drops, thermal profile, and upload responsiveness (external physical-device evidence).
- Reconstruction runtime, peak RAM/VRAM, drift, coverage, residual, confidence, and failed regions by pinned compute/model profile.

## Performance-budget evaluation

A budget defines thresholds, degradation behavior, and evidence class. Failure must activate an explicit fallback or block; it may not silently lower reconstruction quality or authority. Viewer budgets preserve metric/evidence layers before optional visual detail. API and search budgets cap result size and reject high-cardinality labels. Load tests include noisy-neighbor and tenant-quota behavior.

## External evidence

Physical iOS thermal/upload validation, mounted-browser performance, real CUDA profiles, deployed SLOs, and customer load remain external. Their records must identify hardware, OS/runtime, network, model/checkpoint, container digest, and evidence owner before status promotion.
