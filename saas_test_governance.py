"""Instrument catalog governance: superadmin only; NEVER queries patient records."""
import saas_store as store


def list_catalog_for_review():
    return store.all_rows(
        """SELECT t.id,t.title,t.description,t.status,t.visibility,t.active,
                  t.created_at,t.tenant_id,u.nome AS author_name,
                  v.id AS version_id,v.version_number,v.status AS version_status
           FROM tests t
           JOIN users u ON u.id=t.created_by
           LEFT JOIN test_versions v ON v.id=(
               SELECT v2.id FROM test_versions v2 WHERE v2.test_id=t.id
               ORDER BY v2.version_number DESC,v2.id DESC LIMIT 1)
           ORDER BY CASE WHEN t.status='pending' THEN 0 ELSE 1 END,
                    t.updated_at DESC,t.id DESC LIMIT 100""")


def catalog_item(test_id):
    return store.one(
        """SELECT t.id,t.title,t.description,t.status,t.visibility,t.active,
                  t.created_at,t.tenant_id,u.nome AS author_name,
                  v.id AS version_id,v.version_number,v.status AS version_status,
                  v.definition_json
           FROM tests t JOIN users u ON u.id=t.created_by
           LEFT JOIN test_versions v ON v.id=(
               SELECT v2.id FROM test_versions v2 WHERE v2.test_id=t.id
               ORDER BY v2.version_number DESC,v2.id DESC LIMIT 1)
           WHERE t.id=%s""",(test_id,))


def decide_catalog_item(actor_id,test_id,decision,reason):
    if type(actor_id) is not int or type(test_id) is not int or min(actor_id,test_id)<=0:
        raise PermissionError("Identificador invalido")
    if decision not in ("approve","request_changes"):
        raise ValueError("Decisao invalida")
    reason=(reason or "").strip()
    if len(reason)<10 or len(reason)>500:
        raise ValueError("Descreva a revisao tecnica em 10 a 500 caracteres")
    with store.transaction() as cur:
        cur.execute("SELECT global_role,active FROM users WHERE id=%s FOR UPDATE",(actor_id,))
        actor=cur.fetchone()
        if not actor or not actor["active"] or actor["global_role"]!="superadmin":
            raise PermissionError("Somente superadmin pode revisar instrumentos")
        cur.execute("SELECT id,status,active,tenant_id FROM tests WHERE id=%s FOR UPDATE",(test_id,))
        item=cur.fetchone()
        if not item or not item["active"]:
            raise ValueError("Instrumento nao encontrado")
        if item["status"]!="pending":
            raise ValueError("Somente instrumentos pendentes podem ser decididos")
        cur.execute(
            """SELECT id,version_number,status FROM test_versions WHERE test_id=%s
               ORDER BY version_number DESC,id DESC LIMIT 1 FOR UPDATE""",(test_id,))
        version=cur.fetchone()
        if not version or version["status"]!="draft":
            raise ValueError("Versao de teste pendente em rascunho obrigatoria")
        if decision=="approve":
            cur.execute("UPDATE test_versions SET status='approved',approved_by=%s,approved_at=UTC_TIMESTAMP() WHERE id=%s",
                        (actor_id,version["id"]))
            cur.execute("UPDATE tests SET status='approved' WHERE id=%s",(test_id,))
        else:
            cur.execute("UPDATE tests SET status='draft' WHERE id=%s",(test_id,))
        store.audit(cur,actor_id,None,
                    "test_catalog_approved" if decision=="approve" else "test_catalog_changes_requested",
                    "test",test_id,reason=("version="+str(version["version_number"])+";"+reason)[:500])
    return True
