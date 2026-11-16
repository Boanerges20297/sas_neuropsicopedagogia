"""Tenant isolation helpers for professional workspaces.

Owner checks are enforced server-side. A shared assessment may be answered
by other tenants but may never be edited by them.
"""
import sqlite3
from flask import abort, request, redirect, url_for
from flask_login import current_user


def professional_id_for_patient(conn, user_id):
    row = conn.execute(
        "SELECT professional_id FROM users WHERE id=? AND role IN ('patient','user') AND active=1",
        (user_id,)).fetchone()
    return row["professional_id"] if row else None


def can_read_test(conn, test_id):
    row = conn.execute(
        "SELECT id, owner_id, shared, ativo FROM tests WHERE id=?",
        (test_id,)).fetchone()
    if row is None or not row["ativo"]:
        return False
    if current_user.is_authenticated:
        if current_user.is_admin() or row["shared"] or row["owner_id"] == current_user.id:
            return True
        if current_user.role in ("patient", "user"):
            owner = professional_id_for_patient(conn, current_user.id)
            return owner is not None and row["owner_id"] == owner
        return False
    return bool(row["shared"])


def can_edit_test(conn, test_id):
    row = conn.execute("SELECT owner_id FROM tests WHERE id=?", (test_id,)).fetchone()
    if not row or not current_user.is_authenticated:
        return False
    return current_user.is_admin() or (
        current_user.role == "professional" and row["owner_id"] == current_user.id)


def can_access_response(conn, response_id):
    row = conn.execute(
        "SELECT professional_id,patient_id FROM responses WHERE id=?",
        (response_id,)).fetchone()
    if not row or not current_user.is_authenticated:
        return False
    if current_user.is_admin():
        return True
    return current_user.role == "professional" and row["professional_id"] == current_user.id


def scoped_stats(conn, professional_id):
    conn.row_factory = sqlite3.Row
    totals = conn.execute(
        "SELECT COUNT(*) AS n FROM responses WHERE professional_id=?", (professional_id,)
    ).fetchone()["n"]
    new_today = conn.execute(
        "SELECT COUNT(*) AS n FROM responses WHERE professional_id=? AND DATE(timestamp)=DATE('now')",
        (professional_id,)).fetchone()["n"]
    total_patients = conn.execute(
        "SELECT COUNT(*) AS n FROM users WHERE professional_id=? AND role IN ('patient','user') AND active=1",
        (professional_id,)).fetchone()["n"]
    types = [dict(row) for row in conn.execute(
        "SELECT id,nome,descricao FROM test_types ORDER BY id")]
    by_type = list(conn.execute(
        """SELECT tt.nome,COUNT(r.id) AS count FROM test_types tt
           LEFT JOIN responses r ON r.test_type_id=tt.id AND r.professional_id=?
           GROUP BY tt.id,tt.nome ORDER BY count DESC""", (professional_id,)))
    from datetime import datetime, timedelta
    daily = []
    for offset in range(6,-1,-1):
        day = (datetime.now() - timedelta(days=offset)).date().isoformat()
        count = conn.execute(
            "SELECT COUNT(*) FROM responses WHERE professional_id=? AND DATE(timestamp)=?",
            (professional_id,day)).fetchone()[0]
        daily.append((day,count))
    latest = conn.execute(
        "SELECT timestamp FROM responses WHERE professional_id=? ORDER BY timestamp DESC LIMIT 1",
        (professional_id,)).fetchone()
    from datetime import datetime as dt
    try:
        stamp = dt.fromisoformat(latest["timestamp"]) if latest and latest["timestamp"] else None
    except (ValueError, TypeError):
        stamp = None
    recent = []
    for row in conn.execute(
        """SELECT r.id,r.timestamp,tt.nome AS test_type FROM responses r
           LEFT JOIN test_types tt ON r.test_type_id=tt.id
           WHERE r.professional_id=? ORDER BY r.timestamp DESC LIMIT 5""",
        (professional_id,)):
        try:
            date = dt.fromisoformat(row["timestamp"]) if row["timestamp"] else None
        except (ValueError, TypeError):
            date = None
        recent.append({"id":row["id"],"timestamp":date,"test_type":row["test_type"] or "Avaliação"})
    return {
        "total_responses": totals,
        "new_today": new_today,
        "total_users": total_patients,
        "admin_count": 0,
        "test_types": types,
        "responses_by_type": by_type,
        "daily_responses": daily,
        "recent_responses": recent,
        "last_response_date": stamp.strftime("%d/%m/%Y") if stamp else "Sem registros",
        "last_response_time": stamp.strftime("%H:%M") if stamp else "",
    }
