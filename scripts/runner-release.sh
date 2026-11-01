#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/work/sas_neuropsicopedagogia
SHA="${NEURO_RELEASE_REQUEST_SHA:-}"
ID="${NEURO_RELEASE_REQUEST_ID:-}"
[[ "${NEURO_PIPELINE_EXECUTOR:-}" == neuro-diagnosis-runner ]] || exit 70
[[ "${NEURO_PIPELINE_TRIGGER:-}" == watcher-v1 ]] || exit 70
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || exit 70
[[ "$ID" =~ ^[A-Za-z0-9._-]{1,96}$ ]] || exit 70
[[ "$(id -u)" == 10001 && ! -S /var/run/docker.sock ]] || exit 70
cd "$ROOT"
[[ "$(git branch --show-current)" == main ]] || exit 70
[[ "$(git rev-parse HEAD)" == "$SHA" ]] || exit 70
[[ -z "$(git status --porcelain)" ]] || exit 70
git fetch --quiet origin main
git merge-base --is-ancestor "$SHA" origin/main
request="$(python scripts/release_request.py --request .release/request.json)"
IFS=$'\t' read -r rid ver build <<< "$request"
[[ "$rid" == "$ID" && "$ver" == "${NEURO_RELEASE_REQUEST_VERSION:-}" && "$build" == "${NEURO_RELEASE_REQUEST_BUILD:-}" ]] || exit 70
bash scripts/runner-gates.sh
KEY=/home/runner/.ssh/vps_deploy_ed25519
HOST_KEYS=/home/runner/.ssh/known_hosts_vps
[[ -r "$KEY" && -r "$HOST_KEYS" ]] || exit 70
SSH=(ssh -i "$KEY" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$HOST_KEYS" neuro-runner-host@host.docker.internal)
"${SSH[@]}" "deploy $SHA"
"${SSH[@]}" "smoke $SHA"
printf 'NEURO_PIPELINE_OK request=%s sha=%s\n' "$ID" "$SHA"
