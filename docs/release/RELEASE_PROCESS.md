# Release Process

## Candidate creation

A candidate can be created while blockers remain:

```bash
PYTHONPATH=src:. python tools/release.py --mode candidate
```

It produces:

- deterministic source archive;
- evidence archive;
- source file manifest with bytes, mode, and SHA-256;
- CycloneDX SBOM;
- shared release record;
- release-readiness blockers;
- checksums;
- optional Ed25519 signature and public key.

Candidate success means the package was created, not that it is promotable.

## Promotion gate

```bash
SIP_RELEASE_SIGNING_KEY_B64='<base64-raw-32-byte-ed25519-key>' \
  PYTHONPATH=src:. python tools/release.py --mode release
```

Promotion fails when any blocker remains, including:

- dirty tree or missing exact version tag;
- specification hash mismatch;
- incomplete P0/P1 requirements;
- missing/failing reports or demonstrations;
- unresolved external validation;
- missing frozen web dependency graph;
- denied production image;
- missing/invalid release signing key.

## CI release workflow

`.github/workflows/release.yml` pins GitHub actions to immutable commit SHAs, installs frozen dependencies, runs the full local gates, and creates a signed bundle. It has no permission to publish a GitHub release; promotion/publishing should be a separately protected environment action after review.

## Verification

```bash
sha256sum -c SHA256SUMS
```

Verify `release-record.sig` against `release-public-key.txt` and the canonical bytes of `release-record.json`. Retain the public-key approval record separately from the artifact.
