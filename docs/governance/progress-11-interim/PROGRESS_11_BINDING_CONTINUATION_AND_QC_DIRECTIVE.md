# SIP v1.1.0 Progress 11 — Binding Continuation and True North QC Directive

**Decision date:** 2026-08-01  
**Authority:** True North milestone governance  
**Latest accepted checkpoint:** Progress 10  
**Accepted Progress 10 commit:** `ab409f6ac7ca583535f69e5806b7a3bdbfe08214`  
**Authorized Progress 11 epic:** `QA-002 — Dual vertical acceptance and release gates`

## 1. Decision

- **Progress 11 source implementation:** recognized as substantially implemented and committed
- **Progress 11 checkpoint:** not delivered and not accepted
- **Progress 11 milestone:** remains open
- **Progress 12:** unauthorized
- **Production promotion:** NO-GO
- **Production authorized:** false

The submitted ZIP is not a Progress 11 artifact. Its independently reproduced SHA-256 is:

```text
1e0c962a59a55a2a6395179c98467778ff56e2e394319b0ca46367551b5027dc
```

That is the exact accepted Progress 10 consolidated-delivery identity. It proves predecessor availability only. It does not contain or prove the Progress 11 commit, exact-commit acceptance, inner checkpoint, outer envelope, verifier results, delivery record, or handoff record.

No Progress 12 work is authorized by this directive.

## 2. Independently confirmed Progress 11 source identity

A surviving clean-source attestation records:

```text
Branch:
progress-11-release-gates

Final source commit:
65ce122c7ab05782f253ef1ed00b0e694b0557f6

Parent:
ef92605cb0e8b9bef1751ac1e8fd03ca46e0c9e9

Git tree:
b94be550599af50fe99e34e98173f22b30005bbd

Canonical source root:
0d9dab4f0540f1169da2f8e87b13d1f434639a071a746153dd867f0204b3c1f0

Source-root files:
1,245

Detached:
true

Clean before tests:
true
```

The milestone artifacts also retain the correct bounded posture:

```text
Authorized epic:
QA-002

Included requirements:
96

Deferred requirements:
0

Progress 12 authorized:
false

Production authorized:
false
```

These records are useful source and governance evidence. They are not substitutes for a complete exact-commit acceptance run or a verified project checkpoint.

## 3. Critical evidence distinction

The surviving 489-test matrix is valid pre-commit implementation evidence, but it is not the authoritative Progress 11 checkpoint matrix.

Its own metadata records:

```text
Tests:
489 passed
0 failed
0 errors
0 skipped

Recorded Git commit:
ef92605cb0e8b9bef1751ac1e8fd03ca46e0c9e9

Recorded Git dirty state:
true

Source root:
0d9dab4f0540f1169da2f8e87b13d1f434639a071a746153dd867f0204b3c1f0
```

The intended final Progress 11 commit is `65ce122c...`, not `ef92605c...`. The matrix therefore demonstrates that the final source bytes were exercised while present as uncommitted changes over the parent, but it does not prove clean-detached execution at the final commit.

The Progress 11 builder and verifier correctly require the acceptance report and matrix to identify the exact checkpoint commit, exact source root, and clean worktree. The surviving pre-commit matrix cannot satisfy those controls.

## 4. Current runtime condition

The following original paths are no longer present in the active runtime:

```text
/mnt/data/sip-progress-11-authoritative
/mnt/data/sip-progress-11-acceptance-final
/mnt/data/sip-progress-zips
/tmp/sip11-acceptance-final2.exit
/tmp/sip11-acceptance-final2.log
```

No complete Progress 11 Git bundle, exact source archive, inner checkpoint ZIP, or outer delivery envelope was available in the active runtime or located among the surviving Progress 11 artifacts.

The original acceptance process therefore cannot simply be polled or resumed in this environment.

## 5. Recovery strategy

The next implementation worker shall follow **Track A** when the exact Progress 11 Git object can be recovered. It shall use **Track B** only when exact recovery is impossible.

The tracks must not be mixed in a way that creates false identity continuity.

---

# Track A — Recover and finish the exact committed source

## 6. Locate the exact commit

Search every available source of Git objects before rebuilding:

- the original coding session or resume token;
- any prior worker filesystem;
- a GitHub or other remote;
- local bare repositories;
- Git alternates and object caches;
- Git bundles;
- source archives;
- temporary worktrees;
- retained release artifacts;
- uploaded or File Library artifacts;
- operator backups.

Search targets include:

```text
65ce122c7ab05782f253ef1ed00b0e694b0557f6
b94be550599af50fe99e34e98173f22b30005bbd
0d9dab4f0540f1169da2f8e87b13d1f434639a071a746153dd867f0204b3c1f0
progress-11-release-gates
```

Example filesystem search:

```bash
find /mnt/data /tmp /root \
  \( -name '*progress-11*.bundle' \
  -o -name '*progress-11*.tar.gz' \
  -o -name '*progress-11*.zip' \
  -o -name '*65ce122c*' \) \
  -print 2>/dev/null
```

For every surviving repository:

```bash
git cat-file -e 65ce122c7ab05782f253ef1ed00b0e694b0557f6^{commit}
git show -s --format='%H%n%P%n%T%n%cI' \
  65ce122c7ab05782f253ef1ed00b0e694b0557f6
git merge-base --is-ancestor \
  ab409f6ac7ca583535f69e5806b7a3bdbfe08214 \
  65ce122c7ab05782f253ef1ed00b0e694b0557f6
```

Required exact values:

```text
Commit:
65ce122c7ab05782f253ef1ed00b0e694b0557f6

Parent:
ef92605cb0e8b9bef1751ac1e8fd03ca46e0c9e9

Tree:
b94be550599af50fe99e34e98173f22b30005bbd

Accepted Progress 10 ancestor:
true
```

If any value differs, the recovered object is not the attested Progress 11 source.

## 7. Recreate the branch and clean acceptance worktree

From the recovered repository:

```bash
git branch -f progress-11-release-gates \
  65ce122c7ab05782f253ef1ed00b0e694b0557f6

rm -rf /mnt/data/sip-progress-11-acceptance-final

git worktree add \
  --detach \
  /mnt/data/sip-progress-11-acceptance-final \
  65ce122c7ab05782f253ef1ed00b0e694b0557f6
```

Then prove:

```bash
cd /mnt/data/sip-progress-11-acceptance-final

test -z "$(git status --porcelain=v1 --untracked-files=all)"
test "$(git rev-parse HEAD)" = \
  "65ce122c7ab05782f253ef1ed00b0e694b0557f6"
test "$(git rev-parse HEAD^{tree})" = \
  "b94be550599af50fe99e34e98173f22b30005bbd"
```

Generate a fresh source attestation. Do not merely copy the surviving attestation into a reconstructed worktree:

```bash
PYTHONPATH=src:. python tools/create_source_attestation.py \
  --branch progress-11-release-gates \
  --output build/evidence/source-attestation.json
```

The new attestation must reproduce:

```text
Commit:
65ce122c7ab05782f253ef1ed00b0e694b0557f6

Tree:
b94be550599af50fe99e34e98173f22b30005bbd

Source root:
0d9dab4f0540f1169da2f8e87b13d1f434639a071a746153dd867f0204b3c1f0

Detached:
true

Clean before tests:
true
```

If the source root differs, stop. Do not package the source under the old identity.

## 8. Run complete exact-commit acceptance

From the clean detached worktree:

```bash
PYTHONPATH=src:. python tools/run_progress11_checkpoint_acceptance.py \
  --attestation build/evidence/source-attestation.json \
  --output build/reports/checkpoint-acceptance-gates.json
```

The acceptance controller must finish completely. A still-running process, missing exit record, partial matrix, truncated log, or absent gate report is not acceptance.

The authoritative Python matrix must record:

```text
git_commit:
65ce122c7ab05782f253ef1ed00b0e694b0557f6

git_dirty:
false

source_tree_root_sha256:
0d9dab4f0540f1169da2f8e87b13d1f434639a071a746153dd867f0204b3c1f0

failures:
0

errors:
0

skipped:
0
```

The final test count may be 489 or higher. The count alone is not decisive; exact source binding, clean execution, all required suites, and evidence completeness are decisive.

## 9. Required exact-commit gates

The final acceptance must retain direct, source-bound evidence for:

- environment doctor;
- static source and policy checks;
- specification controls;
- generated-schema and contract fixed point;
- service catalog and event catalog;
- worker manifests and fixtures;
- all migrations through `0021_progress11_release_assurance`;
- complete hermetic Python matrix;
- Swift Linux fixtures, without claiming physical iOS acceptance;
- browser-independent runtime and source checks, without claiming the frozen Next.js build;
- desktop local-first checks;
- infrastructure structural checks;
- security controls;
- privacy controls;
- license, provider, model, and checkpoint governance;
- benchmark and operating-envelope evidence;
- Construction dual-vertical acceptance;
- LiveForever dual-vertical acceptance;
- hybrid authority and measurement controls;
- rollback;
- backup and restore;
- migration and recovery;
- open export;
- independent restore;
- load/reference performance;
- support and escalation;
- known limitations;
- signed release manifest;
- release-readiness denial;
- evidence-bound traceability after all release artifacts exist.

The final acceptance report must keep execution status separate from control completeness. A successful command cannot transform an unavailable external control into `passed_complete`.

## 10. Mandatory adversarial stop-lines

The exact-commit matrix shall directly prove at least the following.

### Construction and hybrid authority

- proxy, visual, design, generated, and provider-self-validated geometry cannot satisfy authoritative measurement;
- authoritative measurements re-resolve against eligible metric evidence;
- hidden or unauthorized layers cannot be selected, picked, measured, searched, counted, faceted, or exported;
- restricted records do not leak through result shells, identifiers, URLs, hashes, support bundles, counts, or timing-dependent alternate paths;
- replacement of proxy geometry preserves history and provenance;
- rollback restores the previous release and semantic state without losing accepted evidence;
- independent measurement ground truth is explicitly distinguished from synthetic geometry.

### LiveForever truth, consent, and safety

- consent revocation propagates to narratives, derivatives, generated assets, indexes, caches, exports, and publications;
- generated, restored, reconstructed, inferred, artistic, disputed, and unknown material remains visibly and machine-readably labeled;
- conflicting recollections remain preserved rather than silently merged;
- family corrections create attributed revisions and preserve original testimony;
- quiet mode, evidence mode, pause, reset, captions, reduced motion, and safe exit remain available;
- private transcript marks and restricted witnesses do not leak into family or public exports;
- voice, likeness, first-person simulation, dialogue, and autonomous persona remain disabled unless separately and explicitly governed.

### Release control and package integrity

- stale, partial, mismatched, unsafe, unsigned, or source-unbound release manifests are rejected;
- a release candidate cannot authorize production;
- P0, truth, consent, authority, tenant-isolation, evidence-integrity, rollback, migration, backup/restore, and security failures are nonwaivable;
- permitted waivers require independent approval, compensating control, rationale, owner, scope, and expiration;
- corrupted export or restore packages are rejected;
- duplicate members, traversal, symlinks, unchecked files, missing files, zip bombs, and content-root mismatches are rejected;
- failed gate operations retain denial and audit evidence;
- concurrent acceptance cannot overwrite immutable evidence;
- production promotion fails closed while any required external evidence is absent.

## 11. Evidence fixed point

After exact-commit acceptance:

```bash
PYTHONPATH=src:. python tools/schema_codegen/generate.py \
  --root . --check

PYTHONPATH=src:. python tools/build_traceability_map.py \
  --check-evidence

PYTHONPATH=src:. python tools/audit_progress11_traceability.py \
  --check
```

All generated and controlled artifacts must be stable.

If any source or generated controlled byte changes:

1. stop packaging;
2. commit the change on the Progress 11 branch;
3. create a new clean detached worktree at the new commit;
4. regenerate source attestation;
5. rerun the complete acceptance sequence;
6. use the new commit, tree, and source root everywhere.

Do not patch the detached worktree and package it without committing.

## 12. Build the inner Progress 11 checkpoint

Only after exact-commit acceptance succeeds:

```bash
mkdir -p /mnt/data/sip-progress-zips

PYTHONPATH=src:. python tools/build_progress11_checkpoint.py \
  --output \
  /mnt/data/sip-progress-zips/Spatial-Intelligence-Platform-v1.1.0-progress-11.zip \
  --attestation build/evidence/source-attestation.json \
  --branch progress-11-release-gates
```

The builder must reject:

- dirty source;
- wrong branch reference;
- wrong commit;
- wrong tree;
- wrong source root;
- non-detached or unclean attestation;
- matrix bound to another commit;
- matrix with `git_dirty: true`;
- missing acceptance report;
- missing traceability;
- scope other than 96 included and 0 deferred;
- promotion of `PLTVIEW-007`;
- production authorization;
- Progress 12 authorization.

## 13. Verify the inner checkpoint twice

Run from outside the source tree:

```bash
PYTHONPATH=src:. python tools/verify_progress11_checkpoint.py \
  /mnt/data/sip-progress-zips/Spatial-Intelligence-Platform-v1.1.0-progress-11.zip \
  --output \
  /mnt/data/sip-progress-zips/Spatial-Intelligence-Platform-v1.1.0-progress-11.verification.json

PYTHONPATH=src:. python tools/verify_progress11_checkpoint.py \
  /mnt/data/sip-progress-zips/Spatial-Intelligence-Platform-v1.1.0-progress-11.zip \
  --output \
  /mnt/data/sip-progress-zips/Spatial-Intelligence-Platform-v1.1.0-progress-11.verification.final-rerun.json
```

Both must return:

```text
status: passed_complete
findings: 0
```

A builder-produced “verification” file is not an independent run. The final ZIP bytes must be re-opened and rehashed by the verifier.

## 14. Source recovery artifacts

Generate and independently validate:

- branch-complete Git bundle;
- Git bundle SHA-256;
- exact committed-source archive;
- source archive SHA-256;
- `SOURCE_COMMIT.json`;
- complete source-file manifest;
- predecessor checkpoint record;
- Git/source equivalence report;
- bundle verification transcript.

The bundle must reproduce:

```text
Commit:
65ce122c7ab05782f253ef1ed00b0e694b0557f6

Tree:
b94be550599af50fe99e34e98173f22b30005bbd

Accepted Progress 10 ancestor:
true
```

The exact source archive and source manifest must reconcile every file byte and executable-mode semantic.

## 15. Build and verify the outer envelope

Build:

```text
Spatial-Intelligence-Platform-v1.1.0-progress-11-delivery-package.zip
```

The outer package shall directly include:

- the complete inner Progress 11 ZIP;
- inner checksum;
- inner manifest;
- inner build report;
- both inner-verifier reports;
- inner integrity transcript;
- Git bundle and checksum;
- exact source archive and checksum;
- source commit and complete source-file manifests;
- independent Git/source verification;
- predecessor continuity;
- authoritative specification ZIP and checksum;
- exact milestone scope;
- traceability audit;
- JSON, CSV, and SQLite requirements ledgers;
- implementation map and coverage report;
- complete exact-commit acceptance;
- final test matrix;
- authoritative evidence index;
- release-readiness record;
- Construction and LiveForever release demonstration;
- hybrid, security/privacy, operations, deployment, recovery, export, and restore demonstrations;
- release manifest and rollback/recovery instructions;
- known-limitations and operating-envelope documents;
- continuation and implementation reports;
- binding True North authorization records.

Run the dedicated outer verifier twice. The outer verifier must:

- validate every indexed outer payload;
- enforce explicit self-exclusion of the index;
- reject unsafe, duplicate, unexpected, or missing members;
- validate modes, sizes, hashes, and payload root;
- invoke a fresh nested verification of the actual inner ZIP bytes;
- validate the Git/source and predecessor identities;
- validate scope, traceability, requirement counts, and release posture;
- prove `progress_12_authorized: false`;
- prove `production_authorized: false`.

Required result:

```text
status: passed_complete
findings: 0
```

## 16. Final handoff records

After both ZIPs and both final verifier reruns are immutable, generate:

- final delivery record;
- final delivery-record checksum;
- final cross-artifact handoff check;
- final handoff-check checksum;
- delivery summary;
- completed automatic-resume record.

The final handoff check must compare actual bytes rather than trusting copied claims.

Required final posture:

```text
Progress 11:
Delivered for independent True North milestone-closure review

Progress 12:
Unauthorized

Production promotion:
NO-GO

Production authorized:
false
```

Delivery does not itself close Progress 11 or authorize Progress 12.

---

# Track B — Rebuild Progress 11 with a new identity

## 17. When Track B is required

Use Track B only when the exact Git object `65ce122c...` cannot be recovered from any repository, remote, bundle, source archive, backup, prior session, or operator-controlled artifact.

The surviving source attestation, pre-commit matrix, milestone scope, traceability audit, migration, source files, tests, and documentation may guide reconstruction. They do not recreate the unavailable Git commit merely by matching file content.

## 18. Reconstruct from accepted Progress 10

Start from the accepted Progress 10 Git bundle contained in the uploaded consolidated package:

```text
Accepted base commit:
ab409f6ac7ca583535f69e5806b7a3bdbfe08214

Accepted outer ZIP SHA-256:
1e0c962a59a55a2a6395179c98467778ff56e2e394319b0ca46367551b5027dc
```

Clone the accepted Progress 10 bundle, create a new branch, and reapply the bounded QA-002 implementation using the surviving Progress 11 artifacts and the milestone report.

The reconstruction must include all Progress 11 source, schema, migration, contract, service, test, documentation, governance, and tooling changes—not merely the few individually retained files.

## 19. New identity is mandatory

A reconstructed source tree shall receive:

- a new commit SHA;
- a new tree SHA if any byte or mode differs;
- a freshly computed source root;
- a fresh source attestation;
- a fresh exact-commit matrix;
- fresh generated evidence;
- fresh manifests and packages.

It shall not claim:

```text
65ce122c7ab05782f253ef1ed00b0e694b0557f6
b94be550599af50fe99e34e98173f22b30005bbd
```

unless Git itself reproduces those exact objects.

The old attestation and pre-commit matrix shall be retained only as historical reconstruction inputs and marked non-authoritative.

## 20. Reconstructed checkpoint sequence

After reconstruction:

1. regenerate every controlled artifact;
2. run the complete pre-commit matrix;
3. repair all locally executable findings;
4. reach an evidence fixed point;
5. commit;
6. create a clean detached worktree at the new commit;
7. generate a new source attestation;
8. rerun complete exact-commit acceptance;
9. build the inner Progress 11 checkpoint;
10. verify it twice;
11. generate Git/source recovery artifacts;
12. build the outer delivery envelope;
13. verify it twice with fresh nested verification;
14. generate final delivery and handoff records;
15. deliver for True North review with Progress 12 and production still denied.

---

# 21. Stop-line prohibitions

The next worker shall not:

- describe the uploaded Progress 10 ZIP as a Progress 11 package;
- accept Progress 11 based on the source attestation alone;
- reuse the 489-test pre-commit matrix as exact-commit acceptance;
- hide the matrix’s `git_dirty: true` or parent-commit identity;
- claim that a process “probably finished” without its completed report and exit evidence;
- package a dirty or reconstructed tree under the old commit identity;
- copy stale evidence into a new source root and call it current;
- edit migration history before revision `0021`;
- promote externally validated requirements using synthetic tests;
- promote `PLTVIEW-007` without mounted viewer evidence;
- claim Linux Swift fixtures are physical iOS/LiDAR acceptance;
- claim browser-independent checks are the frozen production web build;
- claim structural cloud files are credentialed deployment;
- claim synthetic acceptance is a customer or human-subject pilot;
- authorize Progress 12;
- authorize production.

## 22. Current governing state

```text
Latest accepted checkpoint:
Progress 10

Accepted commit:
ab409f6ac7ca583535f69e5806b7a3bdbfe08214

Progress 11 source:
Attested committed implementation exists historically

Progress 11 exact commit:
65ce122c7ab05782f253ef1ed00b0e694b0557f6

Progress 11 exact source currently recoverable in active runtime:
false

Progress 11 authoritative clean-detached acceptance:
not completed or retained

Progress 11 inner checkpoint:
not created

Progress 11 outer envelope:
not created

Progress 11 milestone:
open

Progress 12:
unauthorized

Production:
NO-GO
```
