#!/usr/bin/env bash
set -euo pipefail
revision=1f480aeb8a47a24656090d46d053115b7fe60435
target="${1:-$(dirname "$0")/vendor/lingbot-map}"
[ "${SIP_ALLOW_NETWORK_SOURCE_FETCH:-false}" = true ] || { echo 'Denied: set SIP_ALLOW_NETWORK_SOURCE_FETCH=true after source review.' >&2; exit 78; }
command -v git >/dev/null
rm -rf "$target"
mkdir -p "$target"
git -C "$target" init -q
git -C "$target" remote add origin https://github.com/Robbyant/lingbot-map.git
git -C "$target" fetch --depth 1 origin "$revision"
git -C "$target" checkout --detach FETCH_HEAD
actual=$(git -C "$target" rev-parse HEAD)
[ "$actual" = "$revision" ] || { echo "revision mismatch: $actual" >&2; exit 65; }
printf '%s\n' "$revision" > "$target/.sip-source-revision"
find "$target" -type f -not -path '*/.git/*' -print0 | sort -z | xargs -0 sha256sum > "$target/.sip-source-files.sha256"
