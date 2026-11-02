#!/usr/bin/env bash
set -Eeuo pipefail
STATUS="${1:-}"
REQUEST="${2:-}"
SHA="${3:-}"
MESSAGE="${4:-}"
ISSUE="${NEURO_STATUS_ISSUE:-}"
TOKEN_FILE=/home/runner/.config/neuro-diagnosis/issue-token
[[ "$STATUS" =~ ^(running|success|failed)$ ]] || exit 64
[[ "$REQUEST" =~ ^[A-Za-z0-9._-]{1,96}$ ]] || exit 64
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || exit 64
if [[ ! "$ISSUE" =~ ^[0-9]+$ ]] || [[ ! -r "$TOKEN_FILE" ]]; then
  printf 'NEURO_RUNNER_STATUS_LOCAL status=%s request=%s sha=%s\n' "$STATUS" "$REQUEST" "$SHA"
  exit 0
fi
BODY="$(python - "$STATUS" "$REQUEST" "$SHA" "$MESSAGE" <<'PY'
import json, sys
status, request, sha, message = sys.argv[1:]
payload = {"body": (
    "NEURO_RUNNER_" + status.upper() +
    "\nrequestId: `" + request + "`" +
    "\nsourceSha: `" + sha + "`" +
    "\n" + message[:240]
)}
print(json.dumps(payload, ensure_ascii=True))
PY
)"
TOKEN="$(cat "$TOKEN_FILE")"
curl --fail --silent --show-error --max-time 12 --retry 2 \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -H "Content-Type: application/json" \
  --data-binary "$BODY" \
  "https://api.github.com/repos/Boanerges20297/sas_neuropsicopedagogia/issues/$ISSUE/comments" >/dev/null
