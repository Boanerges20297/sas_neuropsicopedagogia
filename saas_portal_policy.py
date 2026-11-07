"""Closed-by-default authorization contracts for a future patient/guardian portal.

Login is an existing SaaS patient user, never the minor's medical record.
An e-mail match, contact row, identity link or consent alone grants NOTHING.
No portal endpoint is registered by this module.
"""
import saas_store as store

SCOPES = frozenset({"appointments", "released_documents"})

# Both adults and minors are evaluated using the Fortaleza civil date, not
# a stale 'age' property or the MySQL server's configured local timezone.
_ADULT_CUTOFF = "DATE_SUB(DATE(CONVERT_TZ(UTC_TIMESTAMP(),'+00:00','-03:00')), INTERVAL 18 YEAR)"

# A verified responsible adult can represent a child only until age 18.
# Each child's linkage, grant and consent must match the tenant + clinician.
SELECT_ALLOWED = f"""
SELECT 1 AS allowed
FROM care_portal_grants g
JOIN care_portal_login_requests login_request
  ON login_request.user_id=g.user_id AND login_request.status='active'
JOIN care_portal_identity_links i
  ON i.id=g.identity_link_id
 AND i.tenant_id=g.tenant_id
 AND i.client_id=g.client_id
 AND i.professional_user_id=g.professional_user_id
 AND i.user_id=g.user_id
JOIN care_client_contacts c
  ON c.id=i.contact_id
 AND c.tenant_id=i.tenant_id
 AND c.client_id=i.client_id
 AND c.professional_user_id=i.professional_user_id
JOIN care_patient_intakes intake
  ON intake.tenant_id=g.tenant_id AND intake.client_id=g.client_id
 AND intake.professional_user_id=g.professional_user_id
 AND intake.guardian_contact_id=c.id
JOIN care_portal_client_activations a
  ON a.tenant_id=g.tenant_id AND a.client_id=g.client_id
 AND a.professional_user_id=g.professional_user_id AND a.user_id=g.user_id
JOIN care_portal_consents v
  ON v.tenant_id=g.tenant_id AND v.client_id=g.client_id
 AND v.professional_user_id=g.professional_user_id
 AND v.user_id=g.user_id AND v.permission_scope=g.permission_scope
JOIN clients p
  ON p.id=g.client_id AND p.tenant_id=g.tenant_id
 AND p.professional_user_id=g.professional_user_id
JOIN tenants t ON t.id=g.tenant_id
JOIN tenant_members m ON m.tenant_id=g.tenant_id
 AND m.user_id=g.professional_user_id
 AND m.status='active' AND m.membership_role IN ('owner','professional')
JOIN users u ON u.id=g.user_id
WHERE g.user_id=%s AND g.tenant_id=%s AND g.client_id=%s
 AND g.permission_scope=%s
 AND g.status='active' AND g.expires_at > UTC_TIMESTAMP()
 AND g.authorized_by=g.professional_user_id AND g.authorized_at IS NOT NULL
 AND i.verification_status='verified'
 AND i.verified_by=i.professional_user_id
 AND i.verified_at IS NOT NULL AND i.verification_evidence_ref IS NOT NULL
 AND i.verification_evidence_ref<>''
 AND c.verification_status='verified'
 AND c.contact_role='legal_guardian'
 AND intake.representation_mode='guardian'
 AND a.status='active' AND a.activated_at IS NOT NULL
 AND p.birth_date IS NOT NULL
 AND p.birth_date > {_ADULT_CUTOFF}
 AND p.birth_date <= DATE(CONVERT_TZ(UTC_TIMESTAMP(),'+00:00','-03:00'))
 AND v.status='accepted' AND v.expires_at > UTC_TIMESTAMP()
 AND v.consent_at IS NOT NULL AND v.consent_evidence_ref IS NOT NULL
 AND v.consent_evidence_ref<>'' AND v.confirmed_by_user_id=g.user_id
 AND p.status='active' AND t.status='active'
 AND u.active=1 AND u.global_role='patient'
LIMIT 1
"""

# An adult accesses THEIR OWN clinical record only with independent verified
# identity + consent + clinician-authorized, expiring permission.
SELECT_SELF_ALLOWED = f"""
SELECT 1 AS allowed
FROM care_portal_self_grants g
JOIN care_portal_login_requests login_request
  ON login_request.user_id=g.user_id AND login_request.status='active'
JOIN care_portal_self_links i
  ON i.id=g.self_link_id AND i.tenant_id=g.tenant_id
 AND i.client_id=g.client_id
 AND i.professional_user_id=g.professional_user_id AND i.user_id=g.user_id
JOIN care_patient_intakes intake
  ON intake.tenant_id=g.tenant_id AND intake.client_id=g.client_id
 AND intake.professional_user_id=g.professional_user_id
JOIN care_portal_client_activations a
  ON a.tenant_id=g.tenant_id AND a.client_id=g.client_id
 AND a.professional_user_id=g.professional_user_id AND a.user_id=g.user_id
JOIN care_portal_consents v
  ON v.tenant_id=g.tenant_id AND v.client_id=g.client_id
 AND v.professional_user_id=g.professional_user_id
 AND v.user_id=g.user_id AND v.permission_scope=g.permission_scope
JOIN clients p
  ON p.id=g.client_id AND p.tenant_id=g.tenant_id
 AND p.professional_user_id=g.professional_user_id
JOIN tenants t ON t.id=g.tenant_id
JOIN tenant_members m ON m.tenant_id=g.tenant_id
 AND m.user_id=g.professional_user_id
 AND m.status='active' AND m.membership_role IN ('owner','professional')
JOIN users u ON u.id=g.user_id
WHERE g.user_id=%s AND g.tenant_id=%s AND g.client_id=%s
 AND g.permission_scope=%s
 AND g.status='active' AND g.expires_at > UTC_TIMESTAMP()
 AND g.authorized_by=g.professional_user_id AND g.authorized_at IS NOT NULL
 AND i.verification_status='verified'
 AND i.verified_by=i.professional_user_id
 AND i.verified_at IS NOT NULL AND i.verification_evidence_ref IS NOT NULL
 AND i.verification_evidence_ref<>'' AND i.consent_evidence_ref IS NOT NULL
 AND i.consent_evidence_ref<>'' AND i.consent_at IS NOT NULL
 AND intake.representation_mode='self'
 AND intake.guardian_contact_id IS NULL
 AND p.birth_date IS NOT NULL AND p.birth_date <= {_ADULT_CUTOFF}
 AND a.status='active' AND a.activated_at IS NOT NULL
 AND v.status='accepted' AND v.expires_at > UTC_TIMESTAMP()
 AND v.consent_at IS NOT NULL AND v.consent_evidence_ref IS NOT NULL
 AND v.consent_evidence_ref<>'' AND v.confirmed_by_user_id=g.user_id
 AND p.status='active' AND t.status='active'
 AND u.active=1 AND u.global_role='patient'
LIMIT 1
"""


def can_access(principal_user_id, tenant_id, client_id, scope):
    """Server-side decision only. No implicit email/account-derived access."""
    if scope not in SCOPES:
        return False
    ids = (principal_user_id, tenant_id, client_id)
    if any(type(v) is not int or v <= 0 for v in ids):
        return False
    args = ids + (scope,)
    return bool(store.one(SELECT_ALLOWED, args) or
                store.one(SELECT_SELF_ALLOWED, args))
