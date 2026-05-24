import pathlib
import shlex
import sys

sys.path.insert(0, r"C:\tmp\codex_py312_ssh")

import paramiko


def load_env(path: pathlib.Path) -> dict:
    env = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def main() -> int:
    code = r"""
from django.test import Client
from avaliacao.models import PerfilUsuario

admin = PerfilUsuario.objects.filter(role='admin').first() or PerfilUsuario.objects.filter(is_superuser=True).first()
assert admin, 'Nenhuma administradora encontrada para smoke test.'

client = Client(HTTP_HOST='neuro-diagnosis.tech')
client.force_login(admin)

paths = [
    '/dashboard/',
    '/admin/pacientes/',
    '/admin/pacientes/novo/',
    '/admin/ia/',
    '/admin/respostas/',
    '/admin/usuarios/',
]
for path in paths:
    resp = client.get(path)
    print(path, resp.status_code)
    assert resp.status_code == 200, resp.content[:500]

for path in ['/select-test/', '/admin/testes/', '/admin/categorias/']:
    resp = client.get(path)
    print(path, resp.status_code, resp.get('Location'))
    assert resp.status_code in (301, 302)

resp = client.post('/admin/ia/', {
    'pergunta': 'avaliar sinais de altas habilidades',
    'contexto': 'aprendizagem rapida, criatividade e interesse intenso por leitura',
})
print('/admin/ia/ POST', resp.status_code)
assert resp.status_code == 200, resp.content[:500]
"""
    env = load_env(pathlib.Path(".env"))
    user, host = env["HOST_VPS"].split("@", 1)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, username=user, password=env["PASSWORD_VPS"], timeout=20)
    try:
        cmd = (
            "cd /home/neuro-diagnosis && "
            "docker compose exec -T app python manage.py shell -c "
            + shlex.quote(code)
        )
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=180)
        output = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace")
        if output:
            print(output, end="")
        if error:
            print(error, end="")
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
