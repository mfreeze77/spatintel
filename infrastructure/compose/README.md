# Docker Compose local environment

The default local profile runs PostgreSQL/PostGIS, Valkey, all 13 logical API boundaries, 15 deterministic capability-scoped workers, the governed LingBot adapter only when explicitly enabled, and the web application. Every worker has a separate process, immutable manifest, workload name, and least-privilege deployment identity. Workers stage review candidates; they cannot approve or publish representations.

## Bootstrap and start

```bash
python tools/bootstrap_secrets.py --output infrastructure/compose/secrets

docker compose \
  --env-file infrastructure/compose/.env.example \
  -f infrastructure/compose/docker-compose.yml \
  up --build
```

The generated development secrets are file-backed, mode `0600`, and ignored by Git. The bootstrap command is idempotent: it never replaces an existing secret. Only the control API and web UI bind host ports, and both bind to loopback by default. PostgreSQL and Valkey remain on an internal network. Development-header authentication is enabled only in this local Compose profile.

## Observability profile

Start the local-only OpenTelemetry Collector, Prometheus, and Grafana profile with telemetry export directed to the in-network collector:

```bash
SIP_OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318 \
  docker compose \
  --env-file infrastructure/compose/.env.example \
  -f infrastructure/compose/docker-compose.yml \
  --profile observability \
  up --build
```

Prometheus is available only at `127.0.0.1:${SIP_PROMETHEUS_PORT:-9090}` and Grafana only at `127.0.0.1:${SIP_GRAFANA_PORT:-3001}`. The Grafana user is `admin`; its password is read from `secrets/grafana_admin_password.txt`. The local collector exports traces only to its debug sink. It has no external exporter, and its privacy processor removes protected attributes before export.

Use the **SIP Overview** dashboard for API rate/error/latency, durable queue depth, worker outcomes and queue delay, reconstruction drift, coverage, residuals, confidence, failed regions, and prior-version quality changes. Alert procedures are in `docs/runbooks/OBSERVABILITY_INCIDENTS.md`.

## Optional object-store compatibility profile

MinIO is opt-in and allowed only for local S3-compatibility testing:

```bash
docker compose \
  --env-file infrastructure/compose/.env.example \
  -f infrastructure/compose/docker-compose.yml \
  --profile local-object-store \
  up --build
```

Production profiles must use an approved and supported S3-compatible service or cloud object store. MinIO administrator credentials are not mounted into application or worker services.

## Governed model profile

The LingBot adapter is excluded from the default profile. Enabling `--profile governed-models` only starts the adapter boundary; model execution still fails closed unless the exact source revision, checkpoint hash, license/right-to-use record, data classification, purpose, region, and retention controls are currently approved.

## Stop and remove local state

```bash
docker compose \
  --env-file infrastructure/compose/.env.example \
  -f infrastructure/compose/docker-compose.yml \
  down
```

Add `--volumes` only when destructive local reset is intended. Preservation export or a verified backup is required before deleting any non-disposable project state.
