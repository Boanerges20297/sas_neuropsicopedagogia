import pathlib
import sys

import paramiko


def load_env(path: pathlib.Path) -> dict:
    env = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: remote_exec.py \"<command>\"")
        return 2

    env = load_env(pathlib.Path(".env"))
    user, host = env["HOST_VPS"].split("@", 1)
    password = env["PASSWORD_VPS"]
    command = sys.argv[1]

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, username=user, password=password, timeout=20)
    try:
        stdin, stdout, stderr = ssh.exec_command(command, timeout=180)
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
