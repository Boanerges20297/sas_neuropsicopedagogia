#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/work/sas_neuropsicopedagogia
ORIGIN=git@github.com:Boanerges20297/sas_neuropsicopedagogia.git
[[ "${NEURO_PIPELINE_EXECUTOR:-}" == neuro-diagnosis-runner ]] || exit 70
[[ "$(id -u)" == 10001 ]] || exit 70
[[ ! -S /var/run/docker.sock ]] || exit 70
if [[ ! -d "$ROOT/.git" ]]; then
    [[ ! -e "$ROOT" ]] || [[ -z "$(find "$ROOT" -mindepth 1 -print -quit)" ]] || exit 70
    git clone "$ORIGIN" "$ROOT"
fi
cd "$ROOT"
[[ "$(git remote get-url origin)" == "$ORIGIN" ]] || exit 70
[[ -z "$(git status --porcelain)" ]] || exit 70
git fetch --quiet origin main
git checkout -q main
git reset --hard origin/main >/dev/null
exec bash "$ROOT/scripts/runner-watch.sh"
