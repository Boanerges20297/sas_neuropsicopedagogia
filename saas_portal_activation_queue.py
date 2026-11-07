"""Minimum-data queue for verified client-account activation requests.

This is *not* a clinical records listing. Only a professional's own patients
or global admins may view eligible account links.
"""
import saas_store as store

CUTOFF = "DATE_SUB(DATE(CONVERT_TZ(UTC_TIMESTAMP(),'+00:00','-03:00')), INTERVAL 18 YEAR)"

QUEUE_SQL = f"""
SELECT
 p.id AS client_id, p.nome AS patient_name,
 p.tenant_id, t.nome AS tenant_name,
 p.professional_user_id, clinician.nome AS clinician_name,
 u.id AS principal_id, u.nome AS account_name,
 intake.representation_mode, req.status AS login_status
FROM care_patient_intakes intake
JOIN clients p ON p.id=intake.client_id AND p.tenant_id=intake.tenant_id
 AND p.professional_user_id=intake.professional_user_id
JOIN tenants t ON t.id=p.tenant_id AND t.status='active'
JOIN tenant_members m ON m.tenant_id=p.tenant_id
 AND m.user_id=p.professional_user_id
 AND m.status='active' AND m.membership_role IN ('owner','professional')
JOIN users clinician ON clinician.id=p.professional_user_id
 AND clinician.active=1
LEFT JOIN care_portal_self_links self_link
 ON self_link.tenant_id=p.tenant_id AND self_link.client_id=p.id
 AND self_link.professional_user_id=p.professional_user_id
 AND intake.representation_mode='self'
LEFT JOIN care_portal_identity_links guardian_link
 ON guardian_link.tenant_id=p.tenant_id AND guardian_link.client_id=p.id
 AND guardian_link.professional_user_id=p.professional_user_id
 AND guardian_link.contact_id=intake.guardian_contact_id
 AND intake.representation_mode='guardian'
LEFT JOIN care_client_contacts contact
 ON contact.id=guardian_link.contact_id
 AND contact.tenant_id=p.tenant_id AND contact.client_id=p.id
 AND contact.professional_user_id=p.professional_user_id
JOIN users u ON u.id=CASE
 WHEN intake.representation_mode='self' THEN self_link.user_id
 ELSE guardian_link.user_id END
 AND u.global_role='patient'
JOIN care_portal_login_requests req ON req.user_id=u.id
 AND req.status IN ('pending','active')
LEFT JOIN care_portal_client_activations activation
 ON activation.tenant_id=p.tenant_id AND activation.client_id=p.id
 AND activation.professional_user_id=p.professional_user_id
 AND activation.user_id=u.id
WHERE p.status='active' AND p.birth_date IS NOT NULL
 AND (activation.id IS NULL OR activation.status='pending')
 AND ((req.status='pending' AND u.active=0)
      OR (req.status='active' AND u.active=1))
 AND (
  (intake.representation_mode='self'
   AND intake.guardian_contact_id IS NULL
   AND p.birth_date <= {CUTOFF}
   AND self_link.verification_status='verified'
   AND self_link.verified_by=p.professional_user_id
   AND self_link.verified_at IS NOT NULL
   AND self_link.verification_evidence_ref IS NOT NULL
   AND self_link.verification_evidence_ref<>''
   AND self_link.consent_at IS NOT NULL
   AND self_link.consent_evidence_ref IS NOT NULL
   AND self_link.consent_evidence_ref<>'')
  OR
  (intake.representation_mode='guardian'
   AND p.birth_date > {CUTOFF}
   AND p.birth_date <= DATE(CONVERT_TZ(UTC_TIMESTAMP(),'+00:00','-03:00'))
   AND contact.verification_status='verified'
   AND contact.contact_role='legal_guardian'
   AND guardian_link.verification_status='verified'
   AND guardian_link.verified_by=p.professional_user_id
   AND guardian_link.verified_at IS NOT NULL
   AND guardian_link.verification_evidence_ref IS NOT NULL
   AND guardian_link.verification_evidence_ref<>'')
 )
 AND (%s=1 OR p.professional_user_id=%s)
ORDER BY p.created_at DESC,p.id DESC
LIMIT 100
"""


def pending_activation_queue(actor_id):
    """Return minimum identity fields for eligible requests, no clinical data."""
    if type(actor_id) is not int or actor_id <= 0:
        raise PermissionError("Identidade de operador invalida")
    operator = store.one(
        "SELECT id,global_role,active FROM users WHERE id=%s", (actor_id,))
    if not operator or not operator["active"]:
        raise PermissionError("Conta nao autorizada")
    role = operator["global_role"]
    if role not in ("professional", "admin", "superadmin"):
        raise PermissionError("Apenas profissionais e administradores")
    admin = int(role in ("admin", "superadmin"))
    return store.all_rows(QUEUE_SQL, (admin, actor_id))
