#!/usr/bin/env bash
# One-time, audited bootstrap for the isolated Neuro-Diagnosis release runner.
# Does not touch MySQL, patient data, Traefik, or the running Flask container.
set -Eeuo pipefail
umask 077
[[ "$(id -u)" == 0 ]] || { echo NEURO_ROOT_REQUIRED >&2; exit 77; }
ROOT=/opt/neuro-diagnosis
cd "$ROOT"
[[ "$(git branch --show-current)" == main ]] || exit 70
[[ -z "$(git status --porcelain)" ]] || exit 70
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] || exit 70
[[ "$(git remote get-url origin)" == https://github.com/Boanerges20297/sas_neuropsicopedagogia.git ]] || exit 70
[[ -r /etc/neuro-diagnosis/flask.env ]] || exit 73
find /var/lib/neuro-diagnosis/backups -maxdepth 1 -type f -name 'pre-neuro-*.sql' -size +0c | grep -q . || exit 73

RUNNER_DIR=/var/lib/neuro-pipeline
RUNNER_HOME="$RUNNER_DIR/home"
SSH_DIR="$RUNNER_HOME/.ssh"
HOST_USER=neuro-runner-host
HOST_HOME=/home/neuro-runner-host
GATEWAY=/usr/local/sbin/neuro-host-gateway
DEPLOY=/usr/local/sbin/deploy-neuro-diagnosis

for pair in "$ROOT/infra/host/neuro-host-gateway:$GATEWAY" "$ROOT/infra/host/deploy-neuro-diagnosis-saas.sh:$DEPLOY"; do
  src="${pair%%:*}"
  dst="${pair#*:}"
  if [[ -e "$dst" ]] && ! cmp -s "$src" "$dst"; then
    echo "NEURO_HOST_COMMAND_CONFLICT: $dst" >&2
    exit 73
  fi
done
if getent passwd "$HOST_USER" >/dev/null; then
  [[ "$(getent passwd "$HOST_USER" | cut -d: -f6)" == "$HOST_HOME" ]] || exit 73
else
  useradd --system --create-home --home-dir "$HOST_HOME" --shell /bin/bash "$HOST_USER"
fi
passwd -l "$HOST_USER" >/dev/null || true
install -d -o root -g root -m 0755 "$RUNNER_DIR"
install -d -o 10001 -g 10001 -m 0700 "$RUNNER_DIR/work" "$RUNNER_HOME" "$SSH_DIR"
install -d -o "$HOST_USER" -g "$HOST_USER" -m 0700 "$HOST_HOME/.ssh"
if [[ ! -f "$SSH_DIR/vps_deploy_ed25519" ]]; then
  ssh-keygen -q -t ed25519 -N '' -f "$SSH_DIR/vps_deploy_ed25519" -C neuro-runner-forced-command
fi
chmod 0600 "$SSH_DIR/vps_deploy_ed25519"
chmod 0644 "$SSH_DIR/vps_deploy_ed25519.pub"
chown 10001:10001 "$SSH_DIR/vps_deploy_ed25519" "$SSH_DIR/vps_deploy_ed25519.pub"
[[ -r /etc/ssh/ssh_host_ed25519_key.pub ]] || exit 73
printf 'host.docker.internal %s\n' "$(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)" > "$SSH_DIR/known_hosts_vps"
chmod 0600 "$SSH_DIR/known_hosts_vps"
chown 10001:10001 "$SSH_DIR/known_hosts_vps"
printf 'restrict,command="%s" %s\n' "$GATEWAY" "$(cat "$SSH_DIR/vps_deploy_ed25519.pub")" > "$HOST_HOME/.ssh/authorized_keys"
chmod 0600 "$HOST_HOME/.ssh/authorized_keys"
chown "$HOST_USER:$HOST_USER" "$HOST_HOME/.ssh/authorized_keys"
install -m 0755 "$ROOT/infra/host/neuro-host-gateway" "$GATEWAY"
install -m 0755 "$ROOT/infra/host/deploy-neuro-diagnosis-saas.sh" "$DEPLOY"
printf '%s\n' "$HOST_USER ALL=(root) NOPASSWD: $DEPLOY *" > "/etc/sudoers.d/neuro-runner-host"
chmod 0440 "/etc/sudoers.d/neuro-runner-host"
visudo -cf "/etc/sudoers.d/neuro-runner-host" >/dev/null
sshd -t
install -d -o root -g root -m 0700 /var/lib/neuro-diagnosis/backups
touch /etc/neuro-diagnosis/host-approved
chmod 0600 /etc/neuro-diagnosis/host-approved
echo NEURO_HOST_GATEWAY_BOOTSTRAPPED
echo "NEURO_SOURCE_SHA=$(git rev-parse HEAD)"
