#!/usr/bin/env bash
# Canonical SaaS deployment via the restricted host gateway.
set -Eeuo pipefail
umask 077
SHA="${1:-}"
ROOT=/opt/neuro-diagnosis
ENV=/etc/neuro-diagnosis/flask.env
APPROVAL=/etc/neuro-diagnosis/host-approved
COMPOSE=docker-compose.saas.yml
STATE=/var/lib/neuro-pipeline/deployed-sha
BACKUPS=/var/lib/neuro-diagnosis/backups
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || exit 64
[[ -f "$APPROVAL" && -r "$ENV" && -d "$ROOT/.git" ]] || { echo NEURO_HOST_NOT_BOOTSTRAPPED >&2; exit 73; }
cd "$ROOT"
[[ "$(git branch --show-current)" == main ]] || exit 70
[[ -z "$(git status --porcelain)" ]] || exit 70
REMOTE="$(git remote get-url origin)"
[[ "$REMOTE" == "https://github.com/Boanerges20297/sas_neuropsicopedagogia.git" ||
   "$REMOTE" == "git@github.com:Boanerges20297/sas_neuropsicopedagogia.git" ]] || exit 70
git fetch --quiet origin main
[[ "$(git rev-parse origin/main)" == "$SHA" ]] || { echo NEURO_SHA_NOT_MAIN >&2; exit 70; }
# The root-owned executable is installed independently of Git. Refuse the
# release BEFORE changing code when the installed deployment logic is stale.
# Compare with the requested Git commit, not the previous checkout.
if ! git show "$SHA:infra/host/deploy-neuro-diagnosis-saas.sh" |
    cmp -s - /usr/local/sbin/deploy-neuro-diagnosis; then
  echo NEURO_HOST_SCRIPT_STALE >&2
  exit 73
fi
PREVIOUS="$(git rev-parse HEAD)"
ROLLBACK=0
restore() {
    if [[ "$ROLLBACK" == 1 ]]; then
        echo "NEURO_ROLLBACK_CODE $PREVIOUS" >&2
        git checkout -q main || true
        git reset --hard "$PREVIOUS" || true
        docker compose -f "$COMPOSE" build web || true
        docker compose -f "$COMPOSE" up -d web || true
    fi
}
trap restore EXIT
git merge --ff-only "$SHA"
ROLLBACK=1
docker compose -f "$COMPOSE" config --quiet
docker compose -f "$COMPOSE" build web
mkdir -p "$BACKUPS"
BACKUP="$BACKUPS/pre-release-${SHA:0:12}-$(date -u +%Y%m%dT%H%M%S).sql"
docker exec neuro-diagnosis-db sh -c 'exec mysqldump --single-transaction --no-tablespaces -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' > "$BACKUP"
[[ -s "$BACKUP" ]] && grep -q 'CREATE TABLE' "$BACKUP" || { echo NEURO_BACKUP_INVALID >&2; exit 1; }
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_saas_profile_migration.sql"
# Additive, idempotent NeuroCore documentation table after the verified database backup.
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_neurocore_review_migration.sql"
# Additive care workflow tables: appointments, encounter metadata and contacts.
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_care_workflow_migration.sql"
# Future guardian portal metadata and time-bounded grants; portal routes remain disabled.
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_care_portal_access_migration.sql"
# Adult-self vs minor/guardian intake, additive after patient and contact tables.
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_care_patient_intake_migration.sql"
# Adult identity proof and explicit purpose-specific consent, no portal routes.
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_care_portal_self_access_migration.sql"
# Scoped client/account release per professional; admin/superadmin may review all.
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_care_client_activation_migration.sql"
# Account permissions and MFA schema are installed before the new application starts.
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_saas_account_rights_migration.sql"
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_saas_mfa_migration.sql"
# Shared login throttling and disposable email OTP reset records.
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_saas_login_recovery_migration.sql"
# Encrypted SMTP credential storage; never write secrets into deploy logs.
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_saas_smtp_settings_migration.sql"
# Email ownership verification (new accounts only), additive and idempotent.
# Required before the new application starts referencing these tables.
docker exec -i neuro-diagnosis-db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neuro_diagnosis' < "$ROOT/scripts/mysql_saas_email_verification_migration.sql"
docker compose -f "$COMPOSE" up -d web
ok=0
for _ in $(seq 1 24); do
  if curl -fsS --max-time 3 http://127.0.0.1:8781/health/ready >/dev/null &&
     curl -fsS --max-time 3 http://127.0.0.1:8781/saas/saude >/dev/null &&
     curl -fsS --max-time 3 http://127.0.0.1:8781/saas/entrar >/dev/null; then
    ok=1
    break
  fi
  sleep 5
done
[[ "$ok" == 1 ]] || exit 1
public_ok=0
# Traefik briefly withdraws the router while Docker recreates the web container.
# A transient HTTPS 404 is not a failed deployment; retry within a fixed window.
for _ in $(seq 1 12); do
  if curl -fsS --max-time 5 https://neuro-diagnosis.tech/saas/entrar >/dev/null; then
    public_ok=1
    break
  fi
  sleep 5
done
[[ "$public_ok" == 1 ]] || { echo NEURO_PUBLIC_ROUTE_NOT_READY >&2; exit 1; }
mkdir -p "$(dirname "$STATE")"
printf '%s\n' "$SHA" > "$STATE.tmp"
mv -f "$STATE.tmp" "$STATE"
chmod 0644 "$STATE"
ROLLBACK=0
printf 'NEURO_DEPLOY_OK sha=%s backup=%s\n' "$SHA" "$BACKUP"
