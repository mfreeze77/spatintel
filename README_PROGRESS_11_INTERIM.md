# SIP v1.1.0 — Most Complete Progress 11 Working Snapshot

This repository snapshot is a **best-effort interim reconstruction**, not an accepted
Progress 11 checkpoint. It starts from the independently accepted Progress 10 commit
`ab409f6ac7ca583535f69e5806b7a3bdbfe08214` and overlays every surviving Progress 11
source, contract, migration, test, requirements, documentation, and checkpoint-tool file.

The outer working bundle retains every conflicting Progress 11 file variant separately,
so no surviving work is discarded. `PROGRESS_11_INTERIM_FILE_SELECTION.json` records
which variant was selected for the runnable reconstructed tree.

## Governing posture

- Authorized Progress 11 scope: `QA-002 — Dual vertical acceptance and release gates`
- Progress 11 milestone: open
- Progress 12: unauthorized
- Production: NO-GO
- Production authorized: false

## Important evidence distinction

The bundle contains retained pre-commit matrices and clean-source attestations from
several Progress 11 reconstruction attempts. They are historical implementation evidence.
They are not a substitute for a complete clean-detached acceptance run against this new
interim reconstruction commit.

## Recovery

Use the Git bundle included in the outer working package to clone this exact interim
snapshot. The accepted Progress 10 consolidated package is also included unchanged as the
last independently accepted full checkpoint.
