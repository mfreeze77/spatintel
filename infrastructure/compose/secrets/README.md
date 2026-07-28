# Local Compose secrets

Generate local-only secrets before `docker compose up`:

```bash
python tools/bootstrap_secrets.py --output infrastructure/compose/secrets
```

The command creates the following files with mode `0600` and never overwrites an existing file:

- `postgres_password.txt`
- `valkey_password.txt`
- `master_key_b64.txt`
- `signing_key_b64.txt`
- `grafana_admin_password.txt`
- `minio_root_user.txt` and `minio_root_password.txt` for the optional local-object-store profile only

The directory is ignored by Git. These values are development credentials, not production secret material. Production deployments must use the configured external secrets/KMS path, workload identity, rotation policy, and audited break-glass procedure. Never copy these files into an image, commit them, paste them into logs, or reuse them across environments.

To rotate a disposable local secret, stop Compose, remove only the intended secret file, rerun the bootstrap command, and recreate the affected services. Rotating the master key for retained data must use the platform key-rotation workflow; deleting `master_key_b64.txt` is not a data-migration procedure.
