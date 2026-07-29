# SIP v1.1.0 Progress 06-R1 Candidate Implementation Report

Progress 06-R1 is a narrow remediation of the accepted Progress 06 development snapshot. It does not add Progress 07 scope.

The remediation makes consent revocation and deficiency retesting tenant/project scoped; derives independent issue-verifier identity from the authenticated principal; replaces caller-controlled restricted-annex booleans with exact immutable server approval and separation of duties; requires complete exact SHA-256 coverage for Construction owner-handoff and LiveForever preservation packages; rejects unexpected, unchecked, malformed, duplicate, unsafe, or altered package content; revalidates package bytes on idempotent replay; requires live immutable in-scope source assets for document and interchange provenance; and isolates every parallel test shard to its own runtime, database, object store, and multipart root.

Append-only migration `0015_progress06_r1_security_controls` stores restricted-export approvals. Migrations `0012`, `0013`, and `0014` remain unchanged.

Final commit, source identity, clean-detached test totals, package hashes, and independent verifier results are generated only after the source is committed and accepted from a clean detached worktree. Progress 07 remains unauthorized and production remains **NO-GO**.
