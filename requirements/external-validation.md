# External validation

Requirements below need evidence unavailable in the current environment.

- **DATDB-004** — owner: `Database Reliability Engineering` — Rehearse forward migration and recovery against a sanitized production-sized PostgreSQL/PostGIS copy, measure duration/locks/storage, validate rollback or forward-fix behavior, and retain environment and database integrity evidence.
- **OPSSEC-005** — owner: `Security Engineering / Mobile Release Engineering` — Build signed production containers and Apple mobile artifacts, execute vulnerability and hardening scans against their final digests, verify patch-SLA tracking, and retain scanner databases, signatures, and review evidence.
- **OPSPERF-001** — owner: `Mobile Engineering / Performance QA` — Run the declared capture profile on every supported physical iPhone/iPad tier under controlled thermal and battery states; retain frame-drop, responsiveness, thermal, device, build, and profile evidence.
- **OPSPERF-002** — owner: `Mobile Engineering / Network Performance QA` — Run foreground-responsiveness and resumable-upload trials on supported physical devices across declared network profiles; retain throughput, responsiveness, interruption, resume, device, and build evidence.
- **DELDEV-005** — owner: `ML Platform / Release Engineering` — Run the documented GPU doctor on each supported NVIDIA driver/CUDA/container profile with an approved local checkpoint hash; retain driver, runtime, device, image, checkpoint, and pass/fail evidence.
