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
    password = env["PASSWORD_VPS"]

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, username=user, password=password, timeout=20)
    try:
        sftp = ssh.open_sftp()
        try:
            sftp.put("docker-compose.yml", "/home/neuro-diagnosis/docker-compose.yml")
        finally:
            sftp.close()

        cmd = (
            "cd /home/neuro-diagnosis && "
            "docker compose up -d app && "
            "docker compose ps && "
            "echo ---LABELS--- && "
            "docker inspect neuro-diagnosis-app --format '{{json .Config.Labels}}'"
        )
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=240)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out:
            print(out, end="")
        if err:
            print(err, end="")
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
