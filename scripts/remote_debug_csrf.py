import pathlib

import paramiko


def load_env() -> dict:
    env = {}
    for line in pathlib.Path(".env").read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def main() -> int:
    env = load_env()
    user, host = env["HOST_VPS"].split("@", 1)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, username=user, password=env["PASSWORD_VPS"], timeout=20)
    try:
        command = r"""
cd /home/neuro-diagnosis &&
echo ---ENV--- &&
docker compose exec -T app sh -lc 'printenv | grep -E "CSRF|SESSION_COOKIE|DEBUG_MODE"' &&
echo ---HEADERS--- &&
curl -I -s http://127.0.0.1:8000/login/ | sed -n '1,30p' &&
echo ---HTML-CSRF--- &&
curl -s http://127.0.0.1:8000/login/ | grep -n csrf | head
"""
        stdin, stdout, stderr = ssh.exec_command(command, timeout=120)
        print((stdout.read() + stderr.read()).decode("utf-8", errors="replace"), end="")
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
