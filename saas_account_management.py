"""Account administration. Metadata only: never query clinical records."""
import saas_store as store
from saas_account_access import can_admin, actor_can_grant
from saas_account_provision import ACCOUNT_ROLES, _identity

FLAGS=("accounts","professionals","activations","clinic")

def account_detail(actor_id,target_id):
    if not can_admin(actor_id,"accounts"): raise PermissionError("Acesso negado")
    return store.one("""SELECT u.id,u.nome,u.email,u.global_role,u.active,
           u.must_change_password,r.user_id AS rights_id,
           r.allow_accounts,r.allow_professionals,r.allow_activations,r.allow_clinic,
           EXISTS(SELECT 1 FROM tenants t WHERE t.owner_user_id=u.id) AS has_tenant
           FROM users u LEFT JOIN saas_account_rights r ON r.user_id=u.id
           WHERE u.id=%s""",(target_id,))

def update_managed_account(actor_id,target_id,*,nome,email,role,active,rights):
    if type(actor_id) is not int or type(target_id) is not int or min(actor_id,target_id)<=0:
        raise PermissionError("Identificador invalido")
    if role not in ACCOUNT_ROLES: raise ValueError("Perfil invalido")
    name,mail=_identity(nome,email)
    flags={k:bool(rights.get(k,False)) for k in FLAGS}
    active=bool(active)
    with store.transaction() as cur:
        cur.execute("SELECT id,global_role,active FROM users WHERE id=%s FOR UPDATE",(actor_id,))
        actor=cur.fetchone()
        if not actor or not actor["active"] or actor["global_role"] not in ("admin","superadmin"):
            raise PermissionError("Operador inativo ou sem perfil administrativo")
        if not actor_can_grant(cur,actor,{"accounts":True}):
            raise PermissionError("Gestao de contas nao permitida")
        cur.execute("SELECT id,nome,email,global_role,active FROM users WHERE id=%s FOR UPDATE",(target_id,))
        old=cur.fetchone()
        if not old: raise ValueError("Conta nao encontrada")
        old_role=old["global_role"]
        if (role=="superadmin" or old_role=="superadmin") and actor["global_role"]!="superadmin":
            raise PermissionError("Somente superadmin gerencia superadmins")
        if actor_id==target_id and (role!=old_role or not active):
            raise PermissionError("Nao altere seu proprio perfil ou suspensao")
        if old_role=="superadmin" and (role!="superadmin" or not active):
            cur.execute("SELECT id FROM users WHERE global_role='superadmin' AND active=1 FOR UPDATE")
            if len(cur.fetchall())<2: raise PermissionError("Ultimo superadmin nao pode ser removido")
        if role!=old_role:
            if role=="patient":
                cur.execute("SELECT id FROM tenants WHERE owner_user_id=%s LIMIT 1 FOR UPDATE",(target_id,))
                if cur.fetchone(): raise ValueError("Conta com espaco clinico nao pode virar paciente")
            if role=="professional":
                cur.execute("""SELECT 1 FROM professional_profiles p
                   JOIN professional_details d ON d.user_id=p.user_id
                   JOIN tenants t ON t.owner_user_id=p.user_id
                   WHERE p.user_id=%s LIMIT 1 FOR UPDATE""",(target_id,))
                if not cur.fetchone():
                    raise ValueError("Perfil Profissional requer dados e espaco clinico previamente cadastrados")
            if old_role=="patient":
                for table in ("care_portal_identity_links","care_portal_self_links"):
                    cur.execute("SELECT 1 FROM "+table+" WHERE user_id=%s LIMIT 1 FOR UPDATE",(target_id,))
                    if cur.fetchone(): raise ValueError("Vinculo de paciente/responsavel exige desligamento formal")
        if role=="admin":
            if not actor_can_grant(cur,actor,flags):
                raise PermissionError("Direitos acima dos permitidos ao operador")
        elif role=="superadmin":
            flags={k:False for k in FLAGS}
        elif any(flags.values()):
            raise ValueError("Permissoes administrativas somente para Administrador")
        if active and not old["active"]:
            if role=="professional":
                raise ValueError("Aprove profissionais pelo fluxo de homologacao/BTA")
            if role=="patient":
                cur.execute("SELECT status FROM care_portal_login_requests WHERE user_id=%s FOR UPDATE",(target_id,))
                row=cur.fetchone()
                if not row or row["status"]!="active":
                    raise ValueError("Ative paciente/responsavel pelo fluxo clinico de identidade")
        cur.execute("UPDATE users SET nome=%s,email=%s,global_role=%s,active=%s WHERE id=%s",
                    (name,mail,role,int(active),target_id))
        if role=="admin":
            cur.execute("""INSERT INTO saas_account_rights
                (user_id,allow_accounts,allow_professionals,allow_activations,allow_clinic,created_by)
                VALUES(%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                allow_accounts=VALUES(allow_accounts),
                allow_professionals=VALUES(allow_professionals),
                allow_activations=VALUES(allow_activations),
                allow_clinic=VALUES(allow_clinic)""",
                (target_id,*(int(flags[k]) for k in FLAGS),actor_id))
        else:
            cur.execute("DELETE FROM saas_account_rights WHERE user_id=%s",(target_id,))
        reason="role="+old_role+"->"+role+";active="+str(bool(old["active"]))+"->"+str(active)+";rights="+",".join(k for k in FLAGS if flags[k])
        store.audit(cur,actor_id,None,"admin_account_updated","user",target_id,reason=reason[:500])
    return target_id
