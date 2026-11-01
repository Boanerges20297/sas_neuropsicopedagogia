"""Validate a canonical release request without touching deployment infrastructure."""
import argparse
import json
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ID_RE = re.compile(r"[A-Za-z0-9._-]{1,96}\Z")
VER_RE = re.compile(r"[A-Za-z0-9._-]{1,48}\Z")
def validate(request, release):
    if type(request) is not dict or type(release) is not dict:
        raise ValueError("JSON objects required")
    if request.get("schemaVersion") != 1 or request.get("action") != "release":
        raise ValueError("invalid release schema or action")
    request_id = request.get("requestId")
    version = request.get("versionName")
    build = request.get("versionCode")
    if not isinstance(request_id, str) or not ID_RE.fullmatch(request_id):
        raise ValueError("invalid requestId")
    if not isinstance(version, str) or not VER_RE.fullmatch(version):
        raise ValueError("invalid versionName")
    if type(build) is not int or build < 1:
        raise ValueError("invalid versionCode")
    if version != release.get("versionName") or build != release.get("versionCode"):
        raise ValueError("version mismatch against release.json")
    if set(request) != {"schemaVersion", "action", "requestId", "versionName", "versionCode"}:
        raise ValueError("unexpected request fields")
    return request_id, version, build
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdin", action="store_true", help="read request JSON from stdin")
    parser.add_argument("--request", type=Path, help="validate an explicit request file")
    args = parser.parse_args()
    if args.stdin == bool(args.request):
        parser.error("choose exactly one of --stdin or --request")
    try:
        request = json.load(sys.stdin) if args.stdin else json.loads(args.request.read_text())
        release = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
        fields = validate(request, release)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("NEURO_RELEASE_INVALID:", str(exc), file=sys.stderr)
        return 2
    print("\t".join(str(x) for x in fields))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
