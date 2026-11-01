#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/work/sas_neuropsicopedagogia
STATE=/home/runner/.local/state/neuro-diagnosis
INTERVAL="${NEURO_PIPELINE_POLL_SECONDS:-60}"
[[ "$INTERVAL" =~ ^[0-9]+$ ]] && (( INTERVAL >= 15 )) || exit 70
[[ "${NEURO_PIPELINE_EXECUTOR:-}" == neuro-diagnosis-runner ]] || exit 70
[[ -n "${NEURO_STATUS_ISSUE:-}" ]] || { echo NEURO_RUNNER_NOT_BOOTSTRAPPED; exit 70; }
[[ -r /home/runner/.config/neuro-diagnosis/issue-token ]] || exit 70
[[ -r /home/runner/.ssh/vps_deploy_ed25519 ]] || exit 70
mkdir -p "$STATE/processed" "$STATE/rejected" "$STATE/logs"
exec 9>"$STATE/watcher.lock"
flock -n 9 || exit 73
cd "$ROOT"
[[ "$(git remote get-url origin)" == git@github.com:Boanerges20297/sas_neuropsicopedagogia.git ]] || exit 70
while :; do
    if ! git fetch --quiet origin main; then
        echo NEURO_FETCH_FAILED >&2
        sleep "$INTERVAL"; continue
    fi
    sha="$(git rev-parse origin/main)"
    if ! git cat-file -e "$sha:.release/request.json" 2>/dev/null; then
        sleep "$INTERVAL"; continue
    fi
    parent="$(git rev-parse "${sha}^1" 2>/dev/null || true)"
    if [[ -z "$parent" ]] || git diff --quiet "$parent" "$sha" -- .release/request.json; then
        sleep "$INTERVAL"; continue
    fi
    [[ ! -e "$STATE/rejected/$sha" ]] || { sleep "$INTERVAL"; continue; }
    # Validate against metadata from the SAME immutable commit.
    req="$(git show "$sha:.release/request.json")"
    rel="$(git show "$sha:release.json")"
    fields="$(REQUEST_JSON="$req" RELEASE_JSON="$rel" python - <<'PY'
import json, os, re
a=json.loads(os.environ['REQUEST_JSON'])
b=json.loads(os.environ['RELEASE_JSON'])
assert type(a)==dict and type(b)==dict
assert set(a)=={'schemaVersion','requestId','action','versionName','versionCode'}
assert a['schemaVersion']==1 and a['action']=='release'
assert re.fullmatch(r'[A-Za-z0-9._-]{1,96}',a['requestId'])
assert re.fullmatch(r'[A-Za-z0-9._-]{1,48}',a['versionName'])
assert type(a['versionCode']) is int and a['versionCode']>0
assert a['versionName']==b.get('versionName') and a['versionCode']==b.get('versionCode')
print(a['requestId']+'\t'+a['versionName']+'\t'+str(a['versionCode']))
PY
)" || {
        echo invalid-release >"$STATE/rejected/$sha"
        sleep "$INTERVAL"; continue
    }
    IFS=$'\t' read -r request_id version build <<< "$fields"
    statefile="$STATE/processed/$request_id.json"
    [[ ! -e "$statefile" ]] || { sleep "$INTERVAL"; continue; }
    if [[ -n "$(git status --porcelain)" ]]; then
        python scripts/runner-state.py "$statefile" "$request_id" "$sha" failed "dirty tree"
        sleep "$INTERVAL"; continue
    fi
    git checkout -q main
    git reset --hard "$sha" >/dev/null
    python scripts/runner-state.py "$statefile" "$request_id" "$sha" running "started"
    bash scripts/runner-observe.sh running "$request_id" "$sha" started || true
    logfile="$STATE/logs/$request_id.$sha.log"
    set +e
    NEURO_RELEASE_REQUEST_ID="$request_id" NEURO_RELEASE_REQUEST_SHA="$sha" \
      NEURO_RELEASE_REQUEST_VERSION="$version" NEURO_RELEASE_REQUEST_BUILD="$build" \
      NEURO_PIPELINE_TRIGGER=watcher-v1 bash scripts/runner-release.sh >"$logfile" 2>&1
    result=$?
    set -e
    if [[ "$result" == 0 ]]; then
        python scripts/runner-state.py "$statefile" "$request_id" "$sha" success NEURO_PIPELINE_OK
        bash scripts/runner-observe.sh success "$request_id" "$sha" NEURO_PIPELINE_OK || true
    else
        python scripts/runner-state.py "$statefile" "$request_id" "$sha" failed "pipeline exit $result"
        bash scripts/runner-observe.sh failed "$request_id" "$sha" failed || true
    fi
    sleep "$INTERVAL"
done
