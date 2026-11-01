#!/usr/bin/env bash
set -Eeuo pipefail
cd /work/sas_neuropsicopedagogia
[[ "${NEURO_PIPELINE_EXECUTOR:-}" == "neuro-diagnosis-runner" ]] || exit 70
[[ "$(git branch --show-current)" == "main" ]] || exit 70
[[ -z "$(git status --porcelain)" ]] || exit 70
python -m py_compile app.py schema.py scripts/release_request.py
python scripts/pipeline_contract.py
python -m venv /home/runner/.venv
PYTHON=/home/runner/.venv/bin/python
"$PYTHON" -m pip install --quiet -r requirements.production.txt
"$PYTHON" -m pip check
"$PYTHON" - <<'PY'
import os
import secrets
import tempfile
import unittest
from pathlib import Path
with tempfile.TemporaryDirectory(prefix="neuro-ci-") as scratch:
    os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
    os.environ["DATABASE_NAME"] = str(Path(scratch) / "ci.sqlite3")
    for name in ("ADMIN_EMAIL", "ADMIN_PASSWORD", "SUPERADMIN_EMAIL", "SUPERADMIN_PASSWORD"):
        os.environ[name] = ""
    from app import init_db
    init_db()
    suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
PY
printf 'NEURO_PIPELINE_GATES_OK\n'
