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
for i in $(seq 1 30); do curl -s http://127.0.0.1:8000/login/ -o /tmp/nd_login_probe.html && break || sleep 2; done &&
curl -s -c /tmp/nd_cookies.txt http://127.0.0.1:8000/login/ -o /tmp/nd_login.html &&
TOKEN=$(grep -o 'name="csrfmiddlewaretoken" value="[^"]*"' /tmp/nd_login.html | sed 's/.*value="//; s/"//') &&
echo "token_len=${#TOKEN}" &&
curl -s -b /tmp/nd_cookies.txt -c /tmp/nd_cookies.txt \
  -X POST http://127.0.0.1:8000/login/ \
  -H 'Referer: http://76.13.121.172:8000/login/' \
  -d "csrfmiddlewaretoken=$TOKEN&email=admin@admin.com&senha=admin123" \
  -D /tmp/nd_headers.txt -o /tmp/nd_body.html &&
head -20 /tmp/nd_headers.txt &&
echo ---BODY-SNIP--- &&
head -5 /tmp/nd_body.html
"""
        stdin, stdout, stderr = ssh.exec_command(command, timeout=180)
        print((stdout.read() + stderr.read()).decode("utf-8", errors="replace"), end="")
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
