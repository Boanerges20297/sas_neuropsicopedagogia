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
        sftp = ssh.open_sftp()
        try:
            sftp.put("sas_project/settings.py", "/home/neuro-diagnosis/sas_project/settings.py")
            sftp.put("docker-compose.yml", "/home/neuro-diagnosis/docker-compose.yml")
        finally:
            sftp.close()

        cmd = (
            "cd /home/neuro-diagnosis && "
            "grep -q '^SESSION_COOKIE_SECURE=' .env || echo 'SESSION_COOKIE_SECURE=False' >> .env; "
            "grep -q '^CSRF_COOKIE_SECURE=' .env || echo 'CSRF_COOKIE_SECURE=False' >> .env; "
            "grep -q '^CSRF_TRUSTED_ORIGINS=' .env || echo 'CSRF_TRUSTED_ORIGINS=https://neuro-diagnosis.tech,https://www.neuro-diagnosis.tech,http://76.13.121.172:8000' >> .env; "
            "docker compose up -d app && "
            "sleep 6 && "
            "docker compose logs --tail=20 app"
        )
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=240)
        print((stdout.read() + stderr.read()).decode("utf-8", errors="replace"), end="")
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
