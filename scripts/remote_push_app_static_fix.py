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
            sftp.put("requirements.txt", "/home/neuro-diagnosis/requirements.txt")
            sftp.put("sas_project/settings.py", "/home/neuro-diagnosis/sas_project/settings.py")
        finally:
            sftp.close()

        cmd = (
            "cd /home/neuro-diagnosis && "
            "docker compose up -d --build app && "
            "sleep 8 && "
            "curl -I -s http://127.0.0.1:8000/static/style.css | head -10 && "
            "echo ---LOGIN--- && "
            "curl -s http://127.0.0.1:8000/login/ | grep -o '/static/style.css' | head -1 && "
            "echo ---PS--- && docker compose ps app"
        )
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=600)
        print((stdout.read() + stderr.read()).decode("utf-8", errors="replace"), end="")
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
