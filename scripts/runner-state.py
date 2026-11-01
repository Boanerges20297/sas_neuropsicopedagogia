"""Persist a runner outcome atomically outside the source checkout."""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
if len(sys.argv) != 6:
    raise SystemExit("usage: runner-state.py state.json requestId sourceSha status message")
path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "requestId": sys.argv[2],
    "sourceSha": sys.argv[3],
    "status": sys.argv[4],
    "message": sys.argv[5][:500],
    "updatedAt": datetime.now(timezone.utc).isoformat(),
}
fd, tmp = tempfile.mkstemp(prefix=".runner-state-", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
    os.replace(tmp, path)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
