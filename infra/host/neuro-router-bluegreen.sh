#!/usr/bin/env bash
# Atomic, project-scoped Traefik file-provider routing for Neuro-Diagnosis.
# The global Traefik process, other dynamic files and Docker routing are untouched.
set -Eeuo pipefail
umask 022

PORT="${1:-}"
[[ "$PORT" == "8781" || "$PORT" == "8782" ]] || { echo NEURO_ROUTER_INVALID_PORT >&2; exit 64; }
[[ "$EUID" == 0 ]] || { echo NEURO_ROUTER_REQUIRES_ROOT >&2; exit 77; }

DYNAMIC_DIR=/etc/somos-enigma/traefik/dynamic
ROUTE="$DYNAMIC_DIR/neuro-diagnosis-bluegreen.yml"
[[ -d "$DYNAMIC_DIR" ]] || { echo NEURO_TRAEFIK_FILE_PROVIDER_MISSING >&2; exit 73; }
if [[ -e "$ROUTE" ]]; then
  [[ -f "$ROUTE" && ! -L "$ROUTE" && "$(stat -c %u "$ROUTE")" == 0 ]] ||
    { echo NEURO_ROUTER_UNTRUSTED_FILE >&2; exit 73; }
fi
SLOT=primary
[[ "$PORT" == "8782" ]] && SLOT=stage
TMP="$(mktemp "$DYNAMIC_DIR/.neuro-bluegreen.XXXXXXXX")"
trap 'rm -f "$TMP"' EXIT
cat > "$TMP" <<YAML
# Managed exclusively by Neuro-Diagnosis deployment; no other service affected.
http:
  routers:
    neuro-bluegreen-auth:
      rule: "(Host(\`neuro-diagnosis.tech\`) || Host(\`www.neuro-diagnosis.tech\`)) && (PathPrefix(\`/saas/entrar\`) || Path(\`/saas/cadastro\`) || PathPrefix(\`/saas/recuperar-senha\`))"
      entryPoints: [websecure]
      priority: 2100
      tls:
        certResolver: letsencrypt
      service: neuro-bluegreen
      middlewares: [neuro-auth-limit, neuro-deploy-marker]
    neuro-bluegreen:
      rule: "Host(\`neuro-diagnosis.tech\`) || Host(\`www.neuro-diagnosis.tech\`)"
      entryPoints: [websecure]
      priority: 2000
      tls:
        certResolver: letsencrypt
      service: neuro-bluegreen
      middlewares: [neuro-general-limit, neuro-deploy-marker]
  middlewares:
    neuro-general-limit:
      rateLimit:
        average: 120
        period: 1m
        burst: 60
        sourceCriterion:
          ipStrategy:
            ipv6Subnet: 64
    neuro-auth-limit:
      rateLimit:
        average: 30
        period: 1m
        burst: 15
        sourceCriterion:
          ipStrategy:
            ipv6Subnet: 64
    neuro-deploy-marker:
      headers:
        customResponseHeaders:
          X-Neuro-Deploy-Slot: "$SLOT"
  services:
    neuro-bluegreen:
      loadBalancer:
        passHostHeader: true
        servers:
          - url: "http://127.0.0.1:$PORT"
YAML
chown root:root "$TMP"
chmod 0644 "$TMP"
mv -f "$TMP" "$ROUTE"
trap - EXIT
printf 'NEURO_ROUTER_SET slot=%s port=%s\n' "$SLOT" "$PORT"
