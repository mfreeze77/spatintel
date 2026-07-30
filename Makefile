SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

PYTHON ?= python
PYTHONPATH := $(CURDIR)/src:$(CURDIR)
REPORT_DIR := build/reports

.PHONY: help bootstrap doctor dev test test-all lint typecheck security license-check spec-check benchmark \
        demo-foundation demo-hybrid demo-scene-runtime demo-construction demo-liveforever demo-security export-demo restore-demo \
        contracts infrastructure migrations swift-test web-test desktop-test web-acceptance fixtures release release-mode traceability-evidence checkpoint-verify clean

help:
	@printf '%s\n' \
	  'SIP v1.1.0 developer commands' \
	  '  make bootstrap          Generate deterministic contracts/manifests and initialize local state' \
	  '  make doctor             Report supported local tool profiles' \
	  '  make dev                Run the local control API (development authentication only)' \
	  '  make test               Run Python test categories in isolated processes' \
	  '  make test-all           Run Python, Swift, web runtime, contracts, and infrastructure checks' \
	  '  make lint               Run source and artifact policy linting' \
	  '  make typecheck          Run available Python/TypeScript/Swift type/build checks' \
	  '  make security           Run static and executable security gates' \
	  '  make license-check      Run dependency/provider/model license governance' \
	  '  make spec-check         Validate complete specification and requirements control data' \
	  '  make benchmark          Run deterministic CPU reference benchmarks' \
	  '  make fixtures           Regenerate and verify the deterministic synthetic test corpus' \
	  '  make demo-scene-runtime Run retained synthetic scene-runtime review demonstration' \
	  '  make demo-construction  Run retained synthetic Construction demonstration' \
	  '  make demo-liveforever   Run retained synthetic LiveForever demonstration' \
	  '  make demo-security      Run retained synthetic Progress 07 security/privacy demonstration' \
	  '  make export-demo        Run preservation export demonstration' \
	  '  make restore-demo       Run clean preservation restore demonstration' \
	  '  make release            Build a hashed release candidate (release gates remain fail-closed)' \
	  '  make desktop-test      Run the dependency-free local-first desktop review profile' \
	  '  make web-acceptance     Run or explicitly block the Node 24.18.0/pnpm 10.28.2 frozen web profile' \
	  '  make traceability-evidence  Verify post-commit evidence against the committed traceability map' \
	  '  make release-mode       Execute fail-closed production release admission' \
	  '  make checkpoint-verify  Verify CHECKPOINT_ZIP with the independent checkpoint verifier'

bootstrap:
	@mkdir -p runtime build/evidence build/reports build/manifests build/release
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/generate_worker_manifests.py
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/generate_test_fixtures.py
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/schema_codegen/generate.py --root .
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/generate_kubernetes.py
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/generate_third_party_lock.py
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/build_traceability_map.py
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/update_requirements.py
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/bootstrap_secrets.py --output infrastructure/compose/secrets >/dev/null
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sip.cli spec-check
	@echo 'bootstrap complete; dependency installation is intentionally separate and governed by pinned manifests'

doctor:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sip.cli doctor

dev:
	SIP_ENV=development SIP_ALLOW_DEVELOPMENT_AUTH=true PYTHONPATH=$(PYTHONPATH) $(PYTHON) services/control-api/main.py

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/run_test_matrix.py --jobs 4 --shard-jobs 4 --timeout 300

web-test:
	@mkdir -p build/evidence build/reports
	npm --workspace apps/web run verify-runtime 2>&1 | tee build/evidence/web-runtime-test.log
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/record_test_evidence.py

desktop-test:
	@mkdir -p build/evidence build/reports/tests
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest -q tests/integration/test_desktop_review.py --junitxml=$(REPORT_DIR)/tests/desktop-review-direct.xml 2>&1 | tee build/evidence/desktop-review-test.log
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/record_test_evidence.py

web-acceptance:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/web_acceptance.py

swift-test:
	@mkdir -p build/evidence build/reports
	cd apps/ios-capture && swift test 2>&1 | tee ../../build/evidence/swift-test-linux.log
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/record_test_evidence.py

contracts:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/schema_codegen/generate.py --check --root .
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/generate_worker_manifests.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/generate_test_fixtures.py --check

fixtures:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/generate_test_fixtures.py
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/generate_test_fixtures.py --check

infrastructure:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/validate_infrastructure.py

migrations:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest -q tests/migration --junitxml=$(REPORT_DIR)/tests/migration-direct.xml

test-all: test web-test desktop-test swift-test contracts infrastructure

lint:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/static_checks.py

typecheck:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/typecheck.py

security:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/security_check.py
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/progress07_supply_chain_check.py
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/run_test_matrix.py --suite security --jobs 1 --shard-jobs 1 --timeout 300

license-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/generate_third_party_lock.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/check_governance.py
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/license_check.py

spec-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/build_traceability_map.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/update_requirements.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/audit_progress05_traceability.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/audit_progress06_traceability.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/audit_progress06_r1_traceability.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/audit_progress06_r2_traceability.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/audit_progress07_traceability.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sip.spec_lint

traceability-evidence:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/build_traceability_map.py --check-evidence
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/update_requirements.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/audit_progress05_traceability.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/audit_progress06_traceability.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/audit_progress06_r1_traceability.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/audit_progress06_r2_traceability.py --check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/audit_progress07_traceability.py --check

benchmark:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/run_benchmarks.py

demo-foundation:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/run_demo.py foundation

demo-hybrid:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/run_demo.py hybrid

demo-scene-runtime:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/run_demo.py scene-runtime

demo-construction:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/run_demo.py construction

demo-liveforever:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/run_demo.py liveforever

demo-security:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/demo_progress07_security.py

export-demo:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/run_demo.py export

restore-demo:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/run_demo.py restore

release:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/release.py

release-mode:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/release.py --mode release

checkpoint-verify:
	@test -n "$${CHECKPOINT_ZIP:-}" || { echo 'CHECKPOINT_ZIP is required'; exit 2; }
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/verify_checkpoint.py "$${CHECKPOINT_ZIP}"

clean:
	rm -rf build/generated build/reports/tests build/release runtime/demo
