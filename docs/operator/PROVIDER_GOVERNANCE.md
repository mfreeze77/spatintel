# Provider and Model Governance

## Default state

Every unregistered, unsigned, expired, revoked, research-only, or rights-unclear provider/model is denied before decrypted source access. Source-code licensing does not establish checkpoint, training-data, dataset, output-commercialization, privacy, or export-control permission.

## Approval dossier

An approval record must bind:

- provider and capability version;
- source revision and build/container digest;
- model/checkpoint SHA-256;
- license and attribution obligations;
- data and training provenance statements;
- allowed classifications, purposes, regions, scene classes, and output roles;
- retention and deletion behavior;
- external transfer and subprocessors;
- security review and vulnerability evidence;
- benchmark corpus and thresholds;
- cancellation, checkpoint, cleanup, and recovery behavior;
- expiration, owner, and revocation procedure.

## LingBot-Map posture

The adapter source is pinned to commit `1f480aeb8a47a24656090d46d053115b7fe60435`. No weights are bundled. The fixture backend tests contract and operating behavior without asserting learned-model quality. Production execution remains denied until exact checkpoint bytes, rights dossier, scan-clean CUDA/PyTorch image, GPU benchmark, and real-scene validation are approved.

## Manual and hosted tools

Manual or hosted conversion tools use the same policy envelope. Confidential construction, critical-infrastructure, biometric, or private-family data cannot be exported to an unapproved service. Return artifacts require hash verification, independent validation, receipt, and policy review.

## Commands

```bash
make license-check
PYTHONPATH=src:. python tools/check_governance.py
```

Release mode additionally requires current vulnerability, signature, and rights evidence.
