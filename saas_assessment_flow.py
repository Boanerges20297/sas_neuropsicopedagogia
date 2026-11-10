"""Version-pinned, private questionnaire application for licensed clinicians.

Portal delivery can be queued but NOT opened until identity verification,
purpose-limited grant, consent and patient-account UI are implemented.
"""
import json
import re

import saas_store as store
import saas_care_store as care
from saas_clinical_flow import encrypt_text, decrypt_text

QUESTION_TYPES = frozenset(("single", "multiple", "text", "number", "yes_no"))
MODES = frozenset(("professional", "portal"))
KEY_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,99}$")


def parse_definition(raw):
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError as exc:
            raise ValueError("Definição do instrumento inválida") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("questions"), list):
        raise ValueError("Instrumento sem questionário configurado")
    questions = raw["questions"]
    if not 1 <= len(questions) <= 100:
        raise ValueError("Instrumento deve possuir entre 1 e 100 perguntas")
    normalized = []
    seen = set()
    for q in questions:
        if not isinstance(q, dict):
            raise ValueError("Pergunta inválida")
        key, kind, label = q.get("key"), q.get("type"), q.get("label")
        if not isinstance(key, str) or not KEY_RE.fullmatch(key) or key in seen:
            raise ValueError("Identificador de pergunta repetido ou inválido")
        seen.add(key)
        if kind not in QUESTION_TYPES or not isinstance(label, str) or not 1 <= len(label.strip()) <= 500:
            raise ValueError("Tipo ou enunciado de pergunta inválido")
        options = q.get("options", [])
        if kind == "yes_no":
            options = [{"value": "yes", "label": "Sim"},
                       {"value": "no", "label": "Não"}]
        if kind in ("single", "multiple", "yes_no"):
            if not isinstance(options, list) or not 2 <= len(options) <= 12:
                raise ValueError("Pergunta deve apresentar de 2 a 12 opções")
            vals = set()
            cleaned = []
            for option in options:
                if not isinstance(option, dict):
                    raise ValueError("Opção inválida")
                val, title = option.get("value"), option.get("label")
                if (not isinstance(val, str) or not KEY_RE.fullmatch(val)
                        or val in vals or not isinstance(title, str)
                        or not 1 <= len(title.strip()) <= 200):
                    raise ValueError("Opção repetida ou inválida")
                vals.add(val)
                cleaned.append({"value": val, "label": title.strip()})
            options = cleaned
        else:
            options = []
        normalized.append({"key": key, "type": kind, "label": label.strip(),
                           "required": q.get("required", False) is True,
                           "options": options,
                           "help": str(q.get("help") or "")[:400]})
    kind = raw.get("kind", "assessment")
    if kind not in ("assessment", "anamnesis"):
        raise ValueError("Categoria de instrumento desconhecida")
    return {"kind": kind, "questions": normalized}


def list_available(user_id, tenant_id):
    return store.all_rows(
        """SELECT v.id AS version_id,v.version_number,t.id AS test_id,
                  t.title,t.description,t.visibility
           FROM test_versions v
           JOIN tests t ON t.id=v.test_id AND t.status='approved'
              AND t.active=1
           WHERE v.status='approved'
             AND ((t.visibility='global' AND t.tenant_id IS NULL)
                OR (t.visibility='private' AND t.tenant_id=%s))
             AND EXISTS (
                SELECT 1 FROM tenant_members m
                JOIN tenants x ON x.id=m.tenant_id
                WHERE m.tenant_id=%s AND m.user_id=%s
                  AND m.status='active' AND x.status='active')
           ORDER BY t.title,v.version_number DESC""",
        (tenant_id, tenant_id, user_id))


def _version(cur, user_id, tenant_id, version_id):
    cur.execute(
        """SELECT v.id,v.version_number,v.definition_json,t.title
           FROM test_versions v JOIN tests t ON t.id=v.test_id
           WHERE v.id=%s AND v.status='approved' AND t.status='approved'
             AND t.active=1
             AND ((t.visibility='global' AND t.tenant_id IS NULL)
                  OR (t.visibility='private' AND t.tenant_id=%s))
             AND EXISTS(SELECT 1 FROM tenant_members m
               WHERE m.user_id=%s AND m.tenant_id=%s AND m.status='active')
           LIMIT 1""", (version_id, tenant_id, user_id, tenant_id))
    result = cur.fetchone()
    if not result:
        raise ValueError("Versão aprovada e acessível não encontrada")
    result["definition"] = parse_definition(result["definition_json"])
    return result


def create_assessment(user_id, tenant_id, client_id, version_id,
                      mode, encounter_id=None):
    if mode not in MODES:
        raise ValueError("Selecione como o instrumento será respondido")
    with store.transaction() as cur:
        care._lock_owned_client(cur, user_id, tenant_id, client_id)
        _version(cur, user_id, tenant_id, version_id)
        if encounter_id:
            cur.execute(
                """SELECT id FROM care_encounters
                   WHERE id=%s AND tenant_id=%s AND client_id=%s
                     AND professional_user_id=%s AND status='draft'""",
                (encounter_id, tenant_id, client_id, user_id))
            if not cur.fetchone():
                raise PermissionError("Atendimento não pertence ao paciente")
        cur.execute(
            """INSERT INTO assessments
               (tenant_id,client_id,test_version_id,responsible_user_id,status)
               VALUES (%s,%s,%s,%s,'pending')""",
            (tenant_id, client_id, version_id, user_id))
        assessment_id = cur.lastrowid
        cur.execute(
            """INSERT INTO care_assessment_workflows
               (assessment_id,tenant_id,client_id,professional_user_id,
                encounter_id,mode,delivery_status)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (assessment_id, tenant_id, client_id, user_id, encounter_id, mode,
             "ready" if mode == "professional" else "awaiting_portal_access"))
        store.audit(cur, user_id, tenant_id, "care_assessment_assigned",
                    "assessment", assessment_id, reason="mode:" + mode)
        return assessment_id


def list_for_patient(user_id, tenant_id, client_id):
    from saas_neurocore_store import scoped_client
    if not scoped_client(user_id, tenant_id, client_id):
        raise PermissionError("Paciente indisponível")
    return store.all_rows(
        """SELECT a.id,a.status,a.created_at,t.title,v.version_number,
                  w.mode,w.delivery_status
           FROM assessments a
           JOIN care_assessment_workflows w ON w.assessment_id=a.id
             AND w.tenant_id=a.tenant_id AND w.client_id=a.client_id
             AND w.professional_user_id=a.responsible_user_id
           JOIN test_versions v ON v.id=a.test_version_id
           JOIN tests t ON t.id=v.test_id
           WHERE a.tenant_id=%s AND a.client_id=%s
             AND a.responsible_user_id=%s
           ORDER BY a.created_at DESC,a.id DESC LIMIT 100""",
        (tenant_id, client_id, user_id))


def scoped_assessment(user_id, tenant_id, client_id, assessment_id):
    record = store.one(
        """SELECT a.id,a.status,a.created_at,a.submitted_at,a.test_version_id,
                  v.definition_json,v.version_number,t.title,
                  w.mode,w.delivery_status,w.revision,w.encounter_id
           FROM assessments a
           JOIN care_assessment_workflows w ON w.assessment_id=a.id
             AND w.tenant_id=a.tenant_id AND w.client_id=a.client_id
             AND w.professional_user_id=a.responsible_user_id
           JOIN test_versions v ON v.id=a.test_version_id
           JOIN tests t ON t.id=v.test_id
           JOIN clients c ON c.id=a.client_id AND c.tenant_id=a.tenant_id
             AND c.professional_user_id=a.responsible_user_id
           JOIN tenant_members m ON m.tenant_id=a.tenant_id
             AND m.user_id=a.responsible_user_id AND m.status='active'
           WHERE a.id=%s AND a.tenant_id=%s AND a.client_id=%s
             AND a.responsible_user_id=%s AND m.user_id=%s
             AND c.status='active' LIMIT 1""",
        (assessment_id, tenant_id, client_id, user_id, user_id))
    if not record:
        return None
    record["definition"] = parse_definition(record.pop("definition_json"))
    return record


def read_answers(user_id, tenant_id, client_id, assessment_id):
    if not scoped_assessment(user_id, tenant_id, client_id, assessment_id):
        raise PermissionError("Questionário não localizado")
    rows = store.all_rows(
        """SELECT question_key,ciphertext FROM care_assessment_private_answers
           WHERE tenant_id=%s AND assessment_id=%s""",
        (tenant_id, assessment_id))
    return {r["question_key"]: json.loads(
        decrypt_text(r["ciphertext"], "assessment-answer")) for r in rows}


def _validate_answers(questions, answers, complete):
    if not isinstance(answers, dict) or len(answers) > 100:
        raise ValueError("Respostas inválidas")
    keys = {q["key"]: q for q in questions}
    if any(k not in keys for k in answers):
        raise ValueError("Pergunta não faz parte do instrumento")
    cleaned = {}
    for key, q in keys.items():
        value = answers.get(key)
        if value is None or value == "" or value == []:
            if complete and q["required"]:
                raise ValueError("Responda à pergunta obrigatória: " + q["label"][:90])
            continue
        kind = q["type"]
        if kind in ("single", "yes_no"):
            if not isinstance(value, str) or value not in {o["value"] for o in q["options"]}:
                raise ValueError("Opção inválida para: " + q["label"][:90])
        elif kind == "multiple":
            if (not isinstance(value, list) or not value or len(value) > len(q["options"])
                    or len(value) != len(set(map(str, value)))
                    or any(type(v) is not str or v not in {o["value"] for o in q["options"]}
                           for v in value)):
                raise ValueError("Seleção inválida para: " + q["label"][:90])
        elif kind == "text":
            if not isinstance(value, str) or len(value) > 5000:
                raise ValueError("Texto inválido ou muito extenso")
        elif kind == "number":
            if (type(value) not in (int, float) or not -100000 <= value <= 100000):
                raise ValueError("Valor numérico inválido")
        cleaned[key] = value
    return cleaned


def save_answers(user_id, tenant_id, client_id, assessment_id,
                 payload, expected_revision, submit=False):
    if not isinstance(payload, dict):
        raise ValueError("Formato de respostas inválido")
    try:
        revision = int(expected_revision)
    except (TypeError, ValueError) as exc:
        raise ValueError("Versão de formulário inválida") from exc
    if revision < 0:
        raise ValueError("Versão de formulário inválida")
    with store.transaction() as cur:
        care._lock_owned_client(cur, user_id, tenant_id, client_id)
        cur.execute(
            """SELECT a.status,a.test_version_id,w.mode,w.revision
               FROM assessments a JOIN care_assessment_workflows w
                 ON w.assessment_id=a.id
               WHERE a.id=%s AND a.tenant_id=%s AND a.client_id=%s
                 AND a.responsible_user_id=%s AND w.tenant_id=a.tenant_id
                 AND w.professional_user_id=a.responsible_user_id
               FOR UPDATE""",
            (assessment_id, tenant_id, client_id, user_id))
        row = cur.fetchone()
        if not row:
            raise PermissionError("Questionário não localizado")
        if row["mode"] != "professional":
            raise PermissionError("Somente a pessoa autorizada no portal poderá responder")
        if row["status"] not in ("pending", "in_progress"):
            raise ValueError("Questionário já finalizado")
        if row["revision"] != revision:
            raise ValueError("As respostas foram alteradas em outra aba. Atualize a página.")
        version = _version(cur, user_id, tenant_id, row["test_version_id"])
        cleaned = _validate_answers(version["definition"]["questions"], payload, submit)
        ciphertexts = {key: encrypt_text(
            json.dumps(val, ensure_ascii=False, separators=(",", ":")),
            "assessment-answer") for key, val in cleaned.items()}
        cur.execute("DELETE FROM care_assessment_private_answers WHERE assessment_id=%s AND tenant_id=%s",
                    (assessment_id, tenant_id))
        for key, ciphertext in ciphertexts.items():
            cur.execute(
                """INSERT INTO care_assessment_private_answers
                   (tenant_id,assessment_id,question_key,ciphertext,edited_by)
                   VALUES (%s,%s,%s,%s,%s)""",
                (tenant_id, assessment_id, key, ciphertext, user_id))
        cur.execute(
            """UPDATE care_assessment_workflows SET revision=revision+1
               WHERE assessment_id=%s AND tenant_id=%s""",
            (assessment_id, tenant_id))
        cur.execute(
            """UPDATE assessments SET status=%s,
                 started_at=COALESCE(started_at,UTC_TIMESTAMP()),
                 submitted_at=CASE WHEN %s THEN UTC_TIMESTAMP() ELSE submitted_at END
               WHERE id=%s AND tenant_id=%s""",
            ("submitted" if submit else "in_progress", 1 if submit else 0,
             assessment_id, tenant_id))
        store.audit(cur, user_id, tenant_id,
                    "care_assessment_submitted" if submit else "care_assessment_saved",
                    "assessment", assessment_id)
        return revision + 1
