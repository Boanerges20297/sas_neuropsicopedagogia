"""Explicit provision of a PRIVATE clinical workspace for a SaaS administrator.

Administrative BTA exemption does not imply clinical authority over other tenants.
Workspace is created only by authenticated POST + CSRF in saas_routes.
"""
import saas_store as store


def own_admin_workspace(user_id):
    # Membership alone does NOT confer clinical tenancy to platform administrators.
    return store.one(
        """SELECT t.id,t.nome,t.slug,t.status FROM tenants t
           JOIN tenant_members m ON m.tenant_id=t.id
           WHERE t.owner_user_id=%s AND m.user_id=%s
             AND m.membership_role='owner' AND m.status='active'
             AND t.status='active' LIMIT 1""",
        (user_id, user_id),
    )


def activate_personal_admin_workspace(user_id):
    with store.transaction() as cur:
        cur.execute(
            """SELECT id,nome,global_role,active FROM users
               WHERE id=%s FOR UPDATE""",
            (user_id,),
        )
        admin = cur.fetchone()
        if not admin or not admin["active"] or admin["global_role"] not in (
                "admin", "superadmin"):
            raise PermissionError("Somente contas administrativas ativas")
        cur.execute(
            """SELECT id,status FROM tenants WHERE owner_user_id=%s
               ORDER BY id FOR UPDATE""",
            (user_id,),
        )
        rows = cur.fetchall()
        if rows:
            if len(rows) != 1 or rows[0]["status"] != "active":
                raise ValueError("Há um espaço existente que requer revisão administrativa")
            cur.execute(
                """SELECT status,membership_role FROM tenant_members
                   WHERE tenant_id=%s AND user_id=%s""",
                (rows[0]["id"], user_id),
            )
            member = cur.fetchone()
            if not member or member["status"] != "active" or member["membership_role"] != "owner":
                raise PermissionError("O vínculo do espaço existente exige revisão")
            return rows[0]["id"]
        slug = "admin-clinic-" + str(user_id)
        name = ("Espaço clínico de " + admin["nome"])[:180]
        cur.execute(
            """INSERT INTO tenants(nome,slug,owner_user_id,status)
               VALUES(%s,%s,%s,'active')""",
            (name, slug, user_id),
        )
        tenant_id = cur.lastrowid
        cur.execute(
            """INSERT INTO tenant_members(tenant_id,user_id,membership_role,status)
               VALUES(%s,%s,'owner','active')""",
            (tenant_id, user_id),
        )
        store.audit(cur,user_id,tenant_id,"admin_workspace_created","tenant",tenant_id)
        return tenant_id
