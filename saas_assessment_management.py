"""Scoped test-application operations. Never deletes the approved test catalog."""
import saas_store as store
import saas_care_store as care


def manage_application(uid, tenant_id, client_id, assessment_id, operation):
    if operation not in ("cancel", "reset"):
        raise ValueError("Ação de teste desconhecida")
    with store.transaction() as cur:
        care._lock_owned_client(cur, uid, tenant_id, client_id)
        cur.execute(
            """SELECT a.id,a.status,w.mode FROM assessments a
               JOIN care_assessment_workflows w ON w.assessment_id=a.id
                 AND w.tenant_id=a.tenant_id AND w.client_id=a.client_id
                 AND w.professional_user_id=a.responsible_user_id
               WHERE a.id=%s AND a.tenant_id=%s AND a.client_id=%s
                 AND a.responsible_user_id=%s FOR UPDATE""",
            (assessment_id, tenant_id, client_id, uid),
        )
        record = cur.fetchone()
        if not record:
            raise PermissionError("Aplicação de teste não encontrada para este paciente")
        if operation == "cancel":
            if record["status"] == "cancelled":
                raise ValueError("A aplicação já está cancelada")
            cur.execute(
                """UPDATE assessments SET status='cancelled'
                   WHERE id=%s AND tenant_id=%s AND client_id=%s
                     AND responsible_user_id=%s""",
                (assessment_id, tenant_id, client_id, uid),
            )
        else:
            if record["mode"] != "professional":
                raise ValueError("A aplicação destinada ao portal não pode ser reiniciada aqui")
            # Only answers for this exact application are deleted, never
            # test_versions, care_encounters, notes or diagnosis records.
            cur.execute(
                """DELETE FROM care_assessment_private_answers
                   WHERE assessment_id=%s AND tenant_id=%s""",
                (assessment_id, tenant_id),
            )
            cur.execute(
                """DELETE FROM assessment_responses
                   WHERE assessment_id=%s AND tenant_id=%s""",
                (assessment_id, tenant_id),
            )
            cur.execute(
                """UPDATE care_assessment_workflows SET revision=revision+1
                   WHERE assessment_id=%s AND tenant_id=%s AND client_id=%s
                     AND professional_user_id=%s""",
                (assessment_id, tenant_id, client_id, uid),
            )
            cur.execute(
                """UPDATE assessments SET status='pending',started_at=NULL,
                   submitted_at=NULL WHERE id=%s AND tenant_id=%s
                     AND client_id=%s AND responsible_user_id=%s""",
                (assessment_id, tenant_id, client_id, uid),
            )
        store.audit(cur, uid, tenant_id,
                    "care_assessment_cancelled" if operation == "cancel"
                    else "care_assessment_answers_reset",
                    "assessment", assessment_id,
                    reason="practitioner-requested-validation")
    return operation
