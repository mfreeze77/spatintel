# Progress 09 Deployment Profiles

Progress 09 defines four explicitly non-production reference profiles: `local-only`, `edge`, `hybrid`, and `aws-reference`. Each profile declares feature availability, cloud dependence, degraded behavior, pinned service-image identities, infrastructure versions, external secret references, resource limits, residency admission, and provider-replacement paths.

Generate and verify profiles with:

```bash
make deployment-profiles
make infrastructure
```

Zero image digests are development sentinels. They block production promotion until replaced by built, scanned, signed, approved image digests. Structural profile validation is not executed deployment evidence.

Project binding requires tenant/project scope, a residency policy, optional transfer policy, revision, and explicit acknowledgement of enabled cloud-dependent features. Upload and worker scheduling admission occur before persistence or scheduling.
