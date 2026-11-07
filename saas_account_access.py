"""Fine-grained SaaS admin rights, separated from clinical tenant ownership.

Existing admins without rights rows retain their legacy abilities.
New admins have explicit allow flags; superadmins remain unrestricted.
"""
import saas_store as store

FEATURES = ("accounts", "professionals", "activations", "clinic")
COLUMN = {
    "accounts": "allow_accounts",
    "professionals": "allow_professionals",
    "activations": "allow_activations",
    "clinic": "allow_clinic",
}


def _is_enabled(role, row, feature):
    if role == "superadmin":
        return True
    if role != "admin":
        return False
    if row is None:
        return True
    return bool(row[COLUMN[feature]])


def admin_permissions(user_id):
    if type(user_id) is not int or user_id <= 0:
        return {feature: False for feature in FEATURES}
    row = store.one(
        """SELECT u.global_role,u.active,r.user_id AS rights_id,
                  r.allow_accounts,r.allow_professionals,
                  r.allow_activations,r.allow_clinic
           FROM users u LEFT JOIN saas_account_rights r ON r.user_id=u.id
           WHERE u.id=%s""", (user_id,))
    if not row or not row["active"]:
        return {feature: False for feature in FEATURES}
    limits = row if row["rights_id"] is not None else None
    return {feature: _is_enabled(row["global_role"], limits, feature)
            for feature in FEATURES}


def can_admin(user_id, feature):
    return feature in FEATURES and admin_permissions(user_id)[feature]


def actor_can_grant(cur, actor, requested):
    if actor["global_role"] == "superadmin":
        return True
    if actor["global_role"] != "admin":
        return False
    cur.execute(
        """SELECT allow_accounts,allow_professionals,allow_activations,
                  allow_clinic
           FROM saas_account_rights WHERE user_id=%s""",
        (actor["id"],),
    )
    row = cur.fetchone()
    return all(not enabled or _is_enabled("admin", row, feature)
               for feature, enabled in requested.items())
