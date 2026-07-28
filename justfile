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

release:
    make release
