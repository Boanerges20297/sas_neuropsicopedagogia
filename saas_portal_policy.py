"""Future client/guardian portal authorization. Fail closed, no portal routes.

A contact record or an e-mail match grants NOTHING.
Only a verified identity link AND an active, unexpired, professional-authorized
scope can be admitted. This is a read gate for later portal endpoints.
"""
import saas_store as store

SCOPES = frozenset({"appointments", "released_documents"})

# A complete tenant/client/professional/linked-principal scope is required.
# Do not loosen joins or replace professional_user_id with admin privilege.
SELECT_ALLOWED = """
SELECT 1 AS allowed
FROM care_portal_grants g
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
 AND i.verified_by IS NOT NULL AND i.verified_at IS NOT NULL
 AND i.verification_evidence_ref IS NOT NULL
 AND c.verification_status='verified'
 AND c.contact_role='legal_guardian'
 AND p.status='active' AND t.status='active'
 AND u.active=1 AND u.global_role='patient'
LIMIT 1
"""


def can_access(principal_user_id, tenant_id, client_id, scope):
    """Verify only explicit, time-bounded guardian grants; never auto-share."""
    if scope not in SCOPES:
        return False
    ids = (principal_user_id, tenant_id, client_id)
    if any(type(v) is not int or v <= 0 for v in ids):
        return False
    return bool(store.one(SELECT_ALLOWED, ids + (scope,)))
