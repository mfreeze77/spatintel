set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    make help

bootstrap:
    make bootstrap

doctor:
    make doctor

dev:
    make dev

test:
    make test

test-all:
    make test-all

lint:
    make lint

typecheck:
    make typecheck

security:
    make security

license-check:
    make license-check

spec-check:
    make spec-check

benchmark:
    make benchmark

fixtures:
    make fixtures

demo-foundation:
    make demo-foundation

demo-hybrid:
    make demo-hybrid

demo-construction:
    make demo-construction

demo-liveforever:
    make demo-liveforever

export-demo:
    make export-demo

restore-demo:
    make restore-demo

web-acceptance:
    make web-acceptance

checkpoint-verify checkpoint_zip:
    CHECKPOINT_ZIP={{checkpoint_zip}} make checkpoint-verify

release:
    make release

traceability-evidence:
    make traceability-evidence

release-mode:
    make release-mode
