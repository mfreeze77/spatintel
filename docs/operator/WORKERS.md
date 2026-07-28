# Worker Operations

## Admission

A worker must reject work unless all of these match:

- workload identity;
- worker manifest digest;
- capability and operation type;
- signed lease and expiration;
- tenant/project scope;
- source asset and input hash;
- classification, purpose, region, and provider approval;
- model/checkpoint hash where applicable;
- resource envelope and output staging scope;
- publication permission fixed to `false`.

## Runtime lifecycle

1. Acquire a lease.
2. Verify immutable inputs before reading decrypted bytes.
3. Restore only a compatible durable checkpoint.
4. Process inside the bounded sandbox.
5. Report objective stage/work units and the last durable checkpoint.
6. Honor cancellation at a safe boundary.
7. Stage full output in the private writable area.
8. Ingest the output as an encrypted content-addressed asset.
9. Create a quarantined candidate and receipt.
10. Release temporary resources according to retention policy.

## Failure handling

- **Expired or mismatched lease:** reject without source access.
- **Non-finite geometry or pose collapse:** quarantine with stable error code.
- **OOM/resource breach:** terminate, retain last safe checkpoint, and require new admission.
- **Provider/model revoked:** stop new work immediately; preserve prior reproducibility records.
- **Cancellation:** do not publish partial output; retain cleanup and checkpoint evidence.
- **Duplicate delivery:** return the deterministic existing candidate/receipt.

## Isolation verification

Compose assigns every worker a private named volume at `/var/lib/sip/runtime`. Kubernetes assigns a pod-private `emptyDir`. Source and manifests are read-only. Compute containers have no general network permission; telemetry egress is separated from compute permission.

Run:

```bash
make infrastructure
PYTHONPATH=src:. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/integration/test_worker_runtime.py \
  tests/contract/test_worker_manifests.py \
  tests/contract/test_worker_protocol.py \
  tests/security/test_worker_sandbox.py
```
