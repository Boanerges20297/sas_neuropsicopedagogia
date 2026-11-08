#!/usr/bin/env bash
# Canonical SaaS deployment via the restricted host gateway.
set -Eeuo pipefail
umask 077
SHA="${1:-}"
ROOT=/opt/neuro-diagnosis
ENV=/etc/neuro-diagnosis/flask.env
APPROVAL=/etc/neuro-diagnosis/host-approved
COMPOSE=docker-compose.saas.yml
STAGE_COMPOSE=docker-compose.saas.stage.yml
ROUTER_SCRIPT=/usr/local/sbin/neuro-router-bluegreen
TRAEFIK_ROUTER=/etc/somos-enigma/traefik/dynamic/neuro-diagnosis-bluegreen.yml
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
# Fail closed until a separately authorized bootstrap points the file router
# at the existing healthy primary. The Docker provider alone is not blue/green.
[[ -f "$TRAEFIK_ROUTER" && -f "$ROUTER_SCRIPT" ]] ||
  { echo NEURO_BLUEGREEN_BOOTSTRAP_REQUIRED >&2; exit 73; }
grep -q 'url: "http://127.0.0.1:8781"' "$TRAEFIK_ROUTER" ||
  { echo NEURO_BLUEGREEN_NOT_PRIMARY >&2; exit 73; }
[[ "$(stat -c %u "$TRAEFIK_ROUTER")" == 0 ]] ||
  { echo NEURO_ROUTER_OWNER_INVALID >&2; exit 73; }

# Both currently live and candidate containers must stay independent.
if ! git show "$SHA:infra/host/neuro-router-bluegreen.sh" |
    cmp -s - "$ROUTER_SCRIPT"; then
  echo NEURO_ROUTER_SCRIPT_STALE >&2
  exit 73
fi
if docker container inspect neuro-diagnosis-flask-stage >/dev/null 2>&1; then
  echo NEURO_STALE_STAGE_REQUIRES_REVIEW >&2
  exit 73
fi
PREVIOUS="$(git rev-parse HEAD)"
ROLLBACK=0
TRAFFIC_ON_STAGE=0

smoke_local() {
  local port="$1"
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$port/health/ready" >/dev/null &&
       curl -fsS --max-time 3 "http://127.0.0.1:$port/saas/saude" >/dev/null &&
       curl -fsS --max-time 3 "http://127.0.0.1:$port/saas/entrar" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

smoke_public() {
  local slot="$1" headers
  for _ in $(seq 1 30); do
    headers="$(curl -fsS --max-time 5 -D - -o /dev/null https://neuro-diagnosis.tech/saas/entrar 2>/dev/null || true)"
    if printf '%s' "$headers" | tr -d '\r' |
       grep -qi "^x-neuro-deploy-slot: $slot$" &&
       curl -fsS --max-time 5 https://neuro-diagnosis.tech/saas/saude >/dev/null; then
       return 0
    fi
    sleep 1
  done
  return 1
}

cleanup_stage() {
  # Clean only our isolated canary, even if git rollback removed its compose file.
  if docker container inspect neuro-diagnosis-flask-stage >/dev/null 2>&1; then
    docker stop -t 10 neuro-diagnosis-flask-stage >/dev/null 2>&1 || true
    docker rm -f neuro-diagnosis-flask-stage >/dev/null 2>&1 || true
  fi
}

restore() {
  local result=$?
  trap - EXIT
  if [[ "$ROLLBACK" == 1 ]]; then
    echo "NEURO_ROLLBACK_CODE $PREVIOUS" >&2
    if [[ "$TRAFFIC_ON_STAGE" == 1 ]]; then
      # Keep the already healthy candidate serving while restoring primary.
      bash "$ROUTER_SCRIPT" 8782 || true
      smoke_public stage || echo NEURO_STAGE_RECOVERY_NOT_CONFIRMED >&2
    fi
    git reset --hard "$PREVIOUS" || true
    if [[ "$TRAFFIC_ON_STAGE" == 1 ]]; then
      if docker compose -f "$COMPOSE" build web &&
         docker compose -f "$COMPOSE" up -d --no-deps --force-recreate --no-build web &&
         smoke_local 8781; then
        bash "$ROUTER_SCRIPT" 8781 || true
        if smoke_public primary; then
          cleanup_stage
          echo NEURO_ROLLBACK_PRIMARY_RESTORED >&2
        else
          # The canary is still available for an immediate route correction.
          bash "$ROUTER_SCRIPT" 8782 || true
          echo NEURO_ROLLBACK_ROUTE_NEEDS_OPERATOR >&2
        fi
      else
        echo NEURO_ROLLBACK_PRIMARY_NOT_READY_STAGE_RETAINED >&2
      fi
    else
      # Primary was never interrupted; do not recreate it on a failed canary.
      cleanup_stage
      docker compose -f "$COMPOSE" build web || true
      echo NEURO_ROLLBACK_OLD_PRIMARY_NEVER_STOPPED >&2
    fi
  fi
  exit "$result"
}
trap restore EXIT

git merge --ff-only "$SHA"
ROLLBACK=1
docker compose -f "$COMPOSE" -f "$STAGE_COMPOSE" config --quiet
bash -n "$ROUTER_SCRIPT"
smoke_local 8781 || { echo NEURO_EXISTING_PRIMARY_UNHEALTHY >&2; exit 1; }
smoke_public primary || { echo NEURO_EXISTING_ROUTER_UNHEALTHY >&2; exit 1; }
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
# Candidate uses a separate container on loopback :8782 with identical
# auth, database, volume and BTA constraints, but no Traefik Docker labels.
# The current :8781 primary continues serving while the candidate starts.
docker compose -f "$COMPOSE" -f "$STAGE_COMPOSE" --profile stage \
  up -d --no-deps --force-recreate --no-build web_stage
smoke_local 8782 || { echo NEURO_STAGE_NOT_READY >&2; exit 1; }
echo NEURO_STAGE_READY

# Atomic reload of a dedicated Traefik file: both app instances stay live.
TRAFFIC_ON_STAGE=1
bash "$ROUTER_SCRIPT" 8782
smoke_public stage || { echo NEURO_STAGE_PUBLIC_ROUTE_FAILED >&2; exit 1; }
echo NEURO_TRAFFIC_ON_STAGE

# Recreate only primary while all new public requests reach healthy stage.
docker compose -f "$COMPOSE" up -d --no-deps --force-recreate --no-build web
smoke_local 8781 || { echo NEURO_PRIMARY_NOT_READY >&2; exit 1; }

bash "$ROUTER_SCRIPT" 8781
smoke_public primary || { echo NEURO_PRIMARY_PUBLIC_ROUTE_FAILED >&2; exit 1; }
echo NEURO_TRAFFIC_ON_PRIMARY
mkdir -p "$(dirname "$STATE")"
printf '%s\n' "$SHA" > "$STATE.tmp"
mv -f "$STATE.tmp" "$STATE"
chmod 0644 "$STATE"
ROLLBACK=0
TRAFFIC_ON_STAGE=0
cleanup_stage
printf 'NEURO_DEPLOY_OK sha=%s backup=%s\n' "$SHA" "$BACKUP"
