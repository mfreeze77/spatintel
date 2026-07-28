#!/bin/sh
set -eu
read_secret() {
  variable="$1"
  path="$2"
  if [ -f "$path" ]; then
    value="$(cat "$path")"
    export "$variable=$value"
  fi
}
read_secret SIP_MASTER_KEY_B64 "${SIP_MASTER_KEY_FILE:-/run/secrets/sip_master_key_b64}"
read_secret SIP_SIGNING_KEY_B64 "${SIP_SIGNING_KEY_FILE:-/run/secrets/sip_signing_key_b64}"
read_secret SIP_POSTGRES_PASSWORD "${SIP_POSTGRES_PASSWORD_FILE:-/run/secrets/sip_postgres_password}"
read_secret SIP_VALKEY_PASSWORD "${SIP_VALKEY_PASSWORD_FILE:-/run/secrets/sip_valkey_password}"
read_secret AWS_ACCESS_KEY_ID "${SIP_S3_ACCESS_KEY_FILE:-/run/secrets/sip_minio_root_user}"
read_secret AWS_SECRET_ACCESS_KEY "${SIP_S3_SECRET_KEY_FILE:-/run/secrets/sip_minio_root_password}"
if [ -z "${SIP_DATABASE_URL:-}" ] && [ -n "${SIP_POSTGRES_PASSWORD:-}" ]; then
  encoded_password="$(python -c 'import os,urllib.parse; print(urllib.parse.quote(os.environ["SIP_POSTGRES_PASSWORD"], safe=""))')"
  export SIP_DATABASE_URL="postgresql+psycopg://${SIP_POSTGRES_USER:-sip}:${encoded_password}@${SIP_POSTGRES_HOST:-postgres}:${SIP_POSTGRES_PORT:-5432}/${SIP_POSTGRES_DB:-sip}"
fi
if [ -z "${SIP_VALKEY_URL:-}" ] && [ -n "${SIP_VALKEY_PASSWORD:-}" ]; then
  encoded_valkey_password="$(python -c 'import os,urllib.parse; print(urllib.parse.quote(os.environ["SIP_VALKEY_PASSWORD"], safe=""))')"
  export SIP_VALKEY_URL="redis://:${encoded_valkey_password}@${SIP_VALKEY_HOST:-valkey}:${SIP_VALKEY_PORT:-6379}/${SIP_VALKEY_DATABASE:-0}"
fi
umask 077
exec "$@"
