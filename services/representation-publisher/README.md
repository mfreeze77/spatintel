# representation-publisher

This directory is the independently deployable entry point for the `representation-publisher` logical boundary. The shared implementation remains in `src/sip`; `service.json` is generated from the actual OpenAPI surface and is checked for drift.

```bash
PYTHONPATH=src SIP_SERVICE_NAME=representation-publisher python services/representation-publisher/main.py
```

The service exposes only its owned routes plus liveness, readiness, and bounded-cardinality Prometheus metrics. Authentication and object authorization are enforced server-side.
