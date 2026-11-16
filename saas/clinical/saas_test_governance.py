"""Instrument catalog governance: administrative review, never patient records."""
from saas.core import saas_store as store


def list_catalog_for_review(*,page=1,search="",status=""):
    if type(page) is not int or not 1 <= page <= 100000:
        raise ValueError("Página inválida")
    search=(search or "").strip()[:100]
    if status not in ("","draft","pending","approved","archived"):
        raise ValueError("Situação inválida")
    conditions=[]
    args=[]
    if search:
        conditions.append("(t.title LIKE %s OR t.description LIKE %s)")
        args.extend(["%"+search+"%","%"+search+"%"])
    if status:
        conditions.append("t.status=%s")
        args.append(status)
    where=" WHERE "+" AND ".join(conditions) if conditions else ""
    sql="""SELECT t.id,t.title,t.description,t.status,t.visibility,t.active,
                  t.created_at,t.tenant_id,u.nome AS author_name,
                  v.id AS version_id,v.version_number,v.status AS version_status
           FROM tests t
           JOIN users u ON u.id=t.created_by
           LEFT JOIN test_versions v ON v.id=(
               SELECT v2.id FROM test_versions v2 WHERE v2.test_id=t.id
               ORDER BY v2.version_number DESC,v2.id DESC LIMIT 1)""" + where + """
           ORDER BY CASE WHEN t.status='pending' THEN 0 ELSE 1 END,
                    t.updated_at DESC,t.id DESC LIMIT %s OFFSET %s"""
    args.extend([26,(page-1)*25])
    return store.all_rows(sql,tuple(args))



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
        if not actor or not actor["active"] or actor["global_role"] not in ("admin","superadmin"):
            raise PermissionError("Somente administradores podem revisar instrumentos")
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


# Professional authoring stays inside its tenant. Publication creates a separate
# global candidate, leaving the locally approved/pinned version untouched.
def _active_author(cur, user_id, tenant_id):
    if (type(user_id) is not int or type(tenant_id) is not int
            or user_id <= 0 or tenant_id <= 0):
        raise PermissionError("Espaço profissional inválido")
    cur.execute(
        """SELECT u.id FROM users u
           JOIN tenant_members m ON m.user_id=u.id
           JOIN tenants t ON t.id=m.tenant_id
           WHERE u.id=%s AND m.tenant_id=%s AND u.active=1
             AND u.global_role IN ('professional','admin','superadmin')
             AND m.status='active' AND t.status='active' LIMIT 1""",
        (user_id, tenant_id))
    if not cur.fetchone():
        raise PermissionError("Profissional sem vínculo ativo com este espaço")


def _clean_definition(title, description, raw):
    import json
    from saas.clinical.saas_assessment_flow import parse_definition
    if not isinstance(title, str) or not 3 <= len(title.strip()) <= 240:
        raise ValueError("Informe um título entre 3 e 240 caracteres")
    if not isinstance(description, str) or len(description.strip()) > 1500:
        raise ValueError("Descrição limitada a 1500 caracteres")
    validated = parse_definition(raw)
    payload = json.dumps(validated, ensure_ascii=False, separators=(",", ":"))
    if len(payload.encode("utf-8")) > 120000:
        raise ValueError("Instrumento excede o tamanho permitido")
    return title.strip(), description.strip(), payload


def list_private_instruments(user_id, tenant_id):
    return store.all_rows(
        """SELECT t.id,t.title,t.description,t.status,t.created_at,
                  v.version_number,v.id AS version_id
           FROM tests t
           LEFT JOIN test_versions v ON v.id=(
              SELECT id FROM test_versions WHERE test_id=t.id
              ORDER BY version_number DESC,id DESC LIMIT 1)
           WHERE t.tenant_id=%s AND t.created_by=%s
             AND t.visibility='private' AND t.active=1
           ORDER BY t.updated_at DESC,t.id DESC LIMIT 100""",
        (tenant_id, user_id))


def private_instrument(user_id, tenant_id, test_id):
    if type(test_id) is not int or test_id <= 0:
        return None
    return store.one(
        """SELECT t.id,t.title,t.description,t.status,
                  v.version_number,v.definition_json
           FROM tests t JOIN test_versions v ON v.id=(
              SELECT id FROM test_versions WHERE test_id=t.id
              ORDER BY version_number DESC,id DESC LIMIT 1)
           WHERE t.id=%s AND t.tenant_id=%s AND t.created_by=%s
             AND t.visibility='private' AND t.active=1 LIMIT 1""",
        (test_id, tenant_id, user_id))


def create_private_instrument(user_id, tenant_id, title, description, raw):
    title, description, payload = _clean_definition(title, description, raw)
    with store.transaction() as cur:
        _active_author(cur, user_id, tenant_id)
        cur.execute(
            """INSERT INTO tests
               (tenant_id,title,description,created_by,visibility,status,active)
               VALUES (%s,%s,%s,%s,'private','approved',1)""",
            (tenant_id, title, description, user_id))
        test_id = cur.lastrowid
        cur.execute(
            """INSERT INTO test_versions
               (test_id,version_number,definition_json,status,created_by)
               VALUES (%s,1,%s,'approved',%s)""",
            (test_id, payload, user_id))
        store.audit(cur, user_id, tenant_id, "private_instrument_created",
                    "test", test_id, reason="original_professional_instrument")
        return test_id


def revise_private_instrument(user_id, tenant_id, test_id,
                              title, description, raw):
    title, description, payload = _clean_definition(title, description, raw)
    with store.transaction() as cur:
        _active_author(cur, user_id, tenant_id)
        cur.execute(
            """SELECT id FROM tests WHERE id=%s AND tenant_id=%s
                 AND created_by=%s AND visibility='private' AND active=1
               FOR UPDATE""", (test_id, tenant_id, user_id))
        if not cur.fetchone():
            raise PermissionError("Instrumento privado não pertence ao profissional")
        cur.execute(
            "SELECT COALESCE(MAX(version_number),0) AS latest "
            "FROM test_versions WHERE test_id=%s", (test_id,))
        next_version = int(cur.fetchone()["latest"]) + 1
        cur.execute(
            """INSERT INTO test_versions
               (test_id,version_number,definition_json,status,created_by)
               VALUES (%s,%s,%s,'approved',%s)""",
            (test_id, next_version, payload, user_id))
        cur.execute(
            """UPDATE tests SET title=%s,description=%s,status='approved'
               WHERE id=%s AND tenant_id=%s""",
            (title, description, test_id, tenant_id))
        store.audit(cur, user_id, tenant_id, "private_instrument_revised",
                    "test", test_id, reason="version=" + str(next_version))
        return next_version


def submit_private_for_review(user_id, tenant_id, test_id):
    """Request public sharing without exposing the private copy or any patient data."""
    from saas.clinical.saas_assessment_flow import parse_definition
    import json
    with store.transaction() as cur:
        _active_author(cur, user_id, tenant_id)
        cur.execute(
            """SELECT id,title,description FROM tests
               WHERE id=%s AND tenant_id=%s AND created_by=%s
                 AND visibility='private' AND status='approved' AND active=1
               FOR UPDATE""", (test_id, tenant_id, user_id))
        original = cur.fetchone()
        if not original:
            raise PermissionError("Somente o autor pode solicitar compartilhamento")
        cur.execute(
            """SELECT id,version_number,definition_json FROM test_versions
               WHERE test_id=%s AND status='approved'
               ORDER BY version_number DESC,id DESC LIMIT 1""", (test_id,))
        version = cur.fetchone()
        if not version:
            raise ValueError("Instrumento sem versão disponível")
        cur.execute(
            """SELECT id FROM tests
               WHERE tenant_id IS NULL AND created_by=%s
                 AND visibility='global' AND title=%s
                 AND status IN ('pending','approved') AND active=1
               LIMIT 1 FOR UPDATE""", (user_id, original["title"]))
        if cur.fetchone():
            raise ValueError("Já existe solicitação pendente ou publicação aprovada deste instrumento")
        cur.execute(
            """INSERT INTO tests
               (tenant_id,title,description,created_by,visibility,status,active)
               VALUES (NULL,%s,%s,%s,'global','pending',1)""",
            (original["title"], original["description"], user_id))
        public_id = cur.lastrowid
        payload = json.dumps(parse_definition(version["definition_json"]),
                             ensure_ascii=False, separators=(",", ":"))
        cur.execute(
            """INSERT INTO test_versions
               (test_id,version_number,definition_json,status,created_by)
               VALUES (%s,1,%s,'draft',%s)""",
            (public_id, payload, user_id))
        store.audit(cur, user_id, tenant_id, "instrument_publication_requested",
                    "test", public_id,
                    reason=("origin=" + str(test_id) +
                            ";source_version=" + str(version["version_number"])))
        return public_id
