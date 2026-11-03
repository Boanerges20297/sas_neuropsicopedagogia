"""NeuroCore structured evidence checklist persistence; MySQL tenant boundary.

Never accepts arbitrary tenant scope from requests. Data is clinical-sensitive:
do not log evidence content. Does not persist diagnosis, symptoms or free text.
"""
import json
import saas_store as store

TOPICS = ("tea", "tdah")


def scoped_client(user_id, tenant_id, client_id):
    return store.one(
        """SELECT c.id,c.nome,c.status,c.created_at
           FROM clients c JOIN tenant_members m ON m.tenant_id=c.tenant_id
           WHERE c.id=%s AND c.tenant_id=%s AND c.professional_user_id=%s
             AND m.user_id=%s AND m.status='active' AND c.status<>'archived'
           LIMIT 1""",
        (client_id, tenant_id, user_id, user_id),
    )


def list_reviews(user_id, tenant_id, client_id):
    if not scoped_client(user_id, tenant_id, client_id):
        return []
    return store.all_rows(
        """SELECT r.topic,r.knowledge_version,r.updated_at
           FROM neurocore_evidence_reviews r
           WHERE r.tenant_id=%s AND r.client_id=%s AND r.professional_user_id=%s
           ORDER BY r.updated_at DESC""",
        (tenant_id, client_id, user_id),
    )


def get_review(user_id, tenant_id, client_id, topic):
    if topic not in TOPICS:
        raise ValueError("Tema inválido")
    if not scoped_client(user_id, tenant_id, client_id):
        return None
    row = store.one(
        """SELECT r.topic,r.knowledge_version,r.evidence_json,r.updated_at
           FROM neurocore_evidence_reviews r
           WHERE r.tenant_id=%s AND r.client_id=%s
             AND r.professional_user_id=%s AND r.topic=%s""",
        (tenant_id, client_id, user_id, topic),
    )
    if row:
        row["evidence_json"] = json.loads(row["evidence_json"]) if isinstance(
            row["evidence_json"], str) else row["evidence_json"]
    return row


def save_review(user_id, tenant_id, client_id, topic, evidence, version):
    from neurocore import evaluate_evidence
    if topic not in TOPICS or len(version) > 30:
        raise ValueError("Tema ou versão inválida")
    checked = evaluate_evidence(topic, evidence)  # validates each state
    if version != checked["version"]:
        raise ValueError("Versão de referência incompatível")
    payload = json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
    if len(payload.encode("utf-8")) > 12000:
        raise ValueError("Registro excedeu o limite permitido")
    with store.transaction() as cur:
        cur.execute(
            """SELECT c.id FROM clients c
               JOIN tenant_members m ON m.tenant_id=c.tenant_id
               WHERE c.id=%s AND c.tenant_id=%s
                 AND c.professional_user_id=%s AND c.status<>'archived'
                 AND m.user_id=%s AND m.status='active'
               FOR UPDATE""",
            (client_id, tenant_id, user_id, user_id),
        )
        if not cur.fetchone():
            raise PermissionError("Paciente não pertence ao espaço profissional")
        cur.execute(
            """INSERT INTO neurocore_evidence_reviews
                (tenant_id,client_id,professional_user_id,topic,knowledge_version,evidence_json)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 knowledge_version=VALUES(knowledge_version),
                 evidence_json=VALUES(evidence_json)""",
            (tenant_id, client_id, user_id, topic, version, payload),
        )
        store.audit(cur, user_id, tenant_id, "neurocore_checklist_save",
                    "client", client_id, reason="topic:" + topic)
