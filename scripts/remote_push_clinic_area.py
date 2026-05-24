import pathlib
import sys

sys.path.insert(0, r"C:\tmp\codex_py312_ssh")

import paramiko


REMOTE_ROOT = "/home/neuro-diagnosis"

FILES = [
    "avaliacao/models.py",
    "avaliacao/views.py",
    "avaliacao/urls.py",
    "avaliacao/migrations/0002_paciente_anotacaoatendimento.py",
    "avaliacao/static/style.css",
    "templates/dashboard.html",
    "templates/admin_responses.html",
    "templates/admin_users.html",
    "templates/view_response.html",
    "templates/user_area.html",
    "templates/login.html",
    "templates/register.html",
    "templates/includes/admin_navbar.html",
    "templates/pacientes_list.html",
    "templates/paciente_form.html",
    "templates/paciente_detail.html",
    "templates/ia_consulta.html",
    "neuro_diagnosis/settings.py",
    "neuro_diagnosis/urls.py",
    "neuro_diagnosis/wsgi.py",
    "neuro_diagnosis/asgi.py",
    "entrypoint.sh",
    "Dockerfile",
    "docker-compose.yml",
    "create_admin.py",
    "run_prod.py",
    ".gitignore",
]


def load_env(path: pathlib.Path) -> dict:
    env = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def ensure_remote_dir(sftp, path: str) -> None:
    parts = path.strip("/").split("/")
    current = ""
    for part in parts:
        current += "/" + part
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def main() -> int:
    env = load_env(pathlib.Path(".env"))
    user, host = env["HOST_VPS"].split("@", 1)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, username=user, password=env["PASSWORD_VPS"], timeout=20)

    try:
        sftp = ssh.open_sftp()
        try:
            for file_name in FILES:
                local = pathlib.Path(file_name)
                remote = f"{REMOTE_ROOT}/{file_name.replace(chr(92), '/')}"
                ensure_remote_dir(sftp, str(pathlib.PurePosixPath(remote).parent))
                sftp.put(str(local), remote)
                print(f"uploaded {file_name}")
        finally:
            sftp.close()

        cmd = (
            f"cd {REMOTE_ROOT} && "
            "rm -rf sas_project && "
            "docker compose down && "
            "docker compose up --build -d app db && "
            "sleep 8 && "
            "docker compose exec -T app python manage.py check && "
            "docker compose exec -T app python manage.py migrate && "
            "docker compose ps"
        )
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
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
