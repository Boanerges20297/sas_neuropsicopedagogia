"""Private per-indicator clinician feedback. No excerpt or response is stored."""
from saas.core import saas_store as store
from neurocore.feedback_learning import VERDICTS, candidate_policy


def save_feedback(user_id, tenant_id, client_id, topic, signal, verdict,
                  engine_version, assessment_id=None):
    if verdict not in VERDICTS:
        raise ValueError("Avaliação do indicador inválida")
    if topic not in ("tea", "tdah") or len(engine_version) > 50:
        raise ValueError("Tema ou versão inválida")
    if (not signal.get("feedback_key") or not signal.get("feature_key")
            or signal.get("source_type") not in ("teste", "prontuario")):
        raise ValueError("Indicador não verificável")
    if assessment_id is not None and (not isinstance(assessment_id, int)
                                      or assessment_id < 1):
        raise ValueError("Instrumento inválido")
    with store.transaction() as cur:
        cur.execute(
            """SELECT c.id FROM clients c
               JOIN tenant_members m ON m.tenant_id=c.tenant_id
               WHERE c.id=%s AND c.tenant_id=%s AND c.professional_user_id=%s
                 AND c.status<>'archived' AND m.user_id=%s AND m.status='active'
               FOR UPDATE""",
            (client_id, tenant_id, user_id, user_id))
        if not cur.fetchone():
            raise PermissionError("Paciente fora do espaço profissional")
        cur.execute(
            """INSERT INTO neurocore_indicator_feedback
                (tenant_id,client_id,professional_user_id,assessment_id,
                 topic,feature_key,signal_key,source_type,verdict,engine_version)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 verdict=VALUES(verdict),
                 engine_version=VALUES(engine_version),
                 updated_at=CURRENT_TIMESTAMP""",
            (tenant_id, client_id, user_id, assessment_id, topic,
             signal["feature_key"], signal["feedback_key"],
             signal["source_type"], verdict, engine_version))
        store.audit(cur, user_id, tenant_id, "neurocore_indicator_feedback",
                    "client", client_id, reason="topic:" + topic +
                    ";verdict:" + verdict)


def list_feedback(user_id, tenant_id, client_id, topic):
    rows = store.all_rows(
        """SELECT f.signal_key,f.verdict FROM neurocore_indicator_feedback f
           JOIN clients c ON c.id=f.client_id AND c.tenant_id=f.tenant_id
           JOIN tenant_members m ON m.tenant_id=f.tenant_id
            AND m.user_id=f.professional_user_id AND m.status='active'
           WHERE f.tenant_id=%s AND f.client_id=%s
             AND f.professional_user_id=%s AND f.topic=%s
             AND c.professional_user_id=%s AND c.status<>'archived'""",
        (tenant_id, client_id, user_id, topic, user_id))
    return {row["signal_key"]: row["verdict"] for row in rows}


def preview_candidate_policy(user_id, tenant_id, topic):
    """Offline model candidates only: never imported into active inference."""
    if topic not in ("tea", "tdah"):
        raise ValueError("Tema inválido")
    rows = store.all_rows(
        """SELECT f.feature_key,f.client_id,f.verdict FROM neurocore_indicator_feedback f
           JOIN clients c ON c.id=f.client_id AND c.tenant_id=f.tenant_id
           JOIN tenant_members m ON m.tenant_id=f.tenant_id
             AND m.user_id=f.professional_user_id AND m.status='active'
           WHERE f.tenant_id=%s AND f.professional_user_id=%s AND f.topic=%s
             AND c.professional_user_id=%s AND c.status<>'archived'
           ORDER BY f.updated_at DESC LIMIT 2500""",
        (tenant_id, user_id, topic, user_id))
    return candidate_policy(rows)
