# Container baseline — 2026-07-27

The release target uses Python 3.13.14 and Node.js 24.18.0 LTS base images, both pinned by OCI index digest. The executing workspace is older (Python 3.13.5 and Node.js 22.16.0), so current local tests are compatibility evidence, not proof that the release images built.

Node.js announced another security release for July 27, 2026. The current Node digest is therefore marked `production_allowed: false` until the fixed release is published, pinned, scanned, and the web build is rerun. No waiver converts that external dependency state into production approval.
