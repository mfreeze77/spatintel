# Local-First Desktop Review Development

`apps/desktop-review` is a dependency-free local reference application backed by `sip.desktop_review.ReviewProject`.

The project bundle stores immutable content-addressed inputs, an append-only hash-chained action log, an atomic snapshot, author identity, base scene commit, branch heads, correspondences, residuals, loop constraints, source weights, uncertainty, and unresolved merge conflicts. Undo and redo append compensating actions. Export produces a policy- and license-gated proposal that still requires server review; direct authoritative publication is rejected.

The local server must bind only to loopback and enforce Host, Origin, JSON content type, same-site request behavior, CSRF equality, a restrictive CSP, and no-store responses. No cloud login is required to open or edit a local bundle.

Run the reference profile:

```bash
make desktop-test
python apps/desktop-review/server.py --help
```

Native packaging, notarization, GPU visualization, operating-system keychain integration, and operator usability evaluation are external validation items.
