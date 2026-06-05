"""
Deploy helper for the Hostinger VPS.

Expected .env keys:
    HOST_VPS=root@your.server.ip
    PASSWORD_VPS=your-password

Common usage:
    python scripts/deploy_vps.py
    python scripts/deploy_vps.py --migrate-only
    python scripts/deploy_vps.py --no-build
"""

from __future__ import annotations

import argparse
import pathlib
import posixpath
import shlex
import sys
from dataclasses import dataclass

import paramiko


REMOTE_ROOT = "/home/neuro-diagnosis"

ROOT_FILES = [
    "manage.py",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "entrypoint.sh",
    "create_admin.py",
    "run_prod.py",
    ".gitignore",
    ".env.example",
    ".env.production.example",
]

CODE_DIRS = [
    "avaliacao",
    "neuro_diagnosis",
    "templates",
    "static",
    "ai_service",
]

EXCLUDED_DIRS = {
    ".git",
    ".planning",
    ".venv",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    "staticfiles",
}

EXCLUDED_FILES = {
    ".env",
    ".env.bak",
    "db.sqlite3",
    "pip_install.log",
    "django-runserver.out.log",
    "django-runserver.err.log",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
    ".log",
}


@dataclass(frozen=True)
class VpsConfig:
    username: str
    hostname: str
    password: str
    remote_root: str


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def load_env(path: pathlib.Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def load_config(env_path: pathlib.Path, remote_root: str) -> VpsConfig:
    env = load_env(env_path)
    missing = [key for key in ("HOST_VPS", "PASSWORD_VPS") if not env.get(key)]
    if missing:
        raise RuntimeError(f"Chaves ausentes no .env: {', '.join(missing)}")

    username, hostname = env["HOST_VPS"].split("@", 1)
    return VpsConfig(
        username=username,
        hostname=hostname,
        password=env["PASSWORD_VPS"],
        remote_root=remote_root,
    )


def connect(config: VpsConfig) -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=config.hostname,
        username=config.username,
        password=config.password,
        timeout=20,
    )
    return ssh


def ensure_remote_dir(sftp: paramiko.SFTPClient, path: str) -> None:
    current = ""
    for part in [item for item in path.strip("/").split("/") if item]:
        current += "/" + part
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def should_upload(path: pathlib.Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return False
    if path.name in EXCLUDED_FILES:
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return True


def iter_upload_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for file_name in ROOT_FILES:
        path = pathlib.Path(file_name)
        if path.exists() and should_upload(path):
            files.append(path)

    for dir_name in CODE_DIRS:
        root = pathlib.Path(dir_name)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and should_upload(path):
                files.append(path)

    return sorted(files, key=lambda item: item.as_posix())


def upload_project(ssh: paramiko.SSHClient, config: VpsConfig) -> None:
    files = iter_upload_files()
    print(f"Enviando {len(files)} arquivos para {config.remote_root}...")
    sftp = ssh.open_sftp()
    try:
        for local in files:
            remote = posixpath.join(config.remote_root, local.as_posix())
            ensure_remote_dir(sftp, posixpath.dirname(remote))
            sftp.put(str(local), remote)
            print(f"  upload {local.as_posix()}")
    finally:
        sftp.close()


def run_remote(ssh: paramiko.SSHClient, command: str, timeout: int) -> tuple[int, str, str]:
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, out, err


def checked_remote(ssh: paramiko.SSHClient, command: str, timeout: int) -> None:
    print(f"\n$ {command}")
    exit_code, out, err = run_remote(ssh, command, timeout)
    if out:
        print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    if exit_code != 0:
        raise RuntimeError(f"Comando remoto falhou com código {exit_code}")


def docker_exec(command: str) -> str:
    return f"docker compose exec -T app {command}"


def deploy(args: argparse.Namespace) -> None:
    config = load_config(pathlib.Path(args.env_file), args.remote_root)
    ssh = connect(config)
    try:
        checked_remote(ssh, f"mkdir -p {shlex.quote(config.remote_root)}", args.timeout)

        if not args.skip_upload:
            upload_project(ssh, config)
            checked_remote(ssh, f"cd {shlex.quote(config.remote_root)} && chmod +x entrypoint.sh", args.timeout)

        if args.migrate_only:
            checked_remote(
                ssh,
                f"cd {shlex.quote(config.remote_root)} && {docker_exec('python manage.py migrate')}",
                args.timeout,
            )
            checked_remote(
                ssh,
                f"cd {shlex.quote(config.remote_root)} && {docker_exec('python manage.py check')}",
                args.timeout,
            )
            return

        services = " ".join(shlex.quote(service) for service in args.services)
        up_flag = "--build " if not args.no_build else ""
        checked_remote(
            ssh,
            f"cd {shlex.quote(config.remote_root)} && docker compose up {up_flag}-d {services}",
            args.timeout,
        )

        checked_remote(
            ssh,
            f"cd {shlex.quote(config.remote_root)} && {docker_exec('python manage.py check')}",
            args.timeout,
        )

        if not args.skip_migrate:
            checked_remote(
                ssh,
                f"cd {shlex.quote(config.remote_root)} && {docker_exec('python manage.py migrate')}",
                args.timeout,
            )

        if not args.skip_collectstatic:
            checked_remote(
                ssh,
                f"cd {shlex.quote(config.remote_root)} && {docker_exec('python manage.py collectstatic --noinput')}",
                args.timeout,
            )

        if not args.skip_smoke:
            checked_remote(
                ssh,
                "curl -I -s http://127.0.0.1:8000/login/ | head -n 5",
                args.timeout,
            )

        checked_remote(
            ssh,
            f"cd {shlex.quote(config.remote_root)} && docker compose ps",
            args.timeout,
        )
    finally:
        ssh.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publica o projeto na VPS e aplica migrations.")
    parser.add_argument("--env-file", default=".env", help="Arquivo local com HOST_VPS e PASSWORD_VPS.")
    parser.add_argument("--remote-root", default=REMOTE_ROOT, help="Diretório do projeto na VPS.")
    parser.add_argument("--services", nargs="+", default=["app", "db", "ai"], help="Serviços do docker compose.")
    parser.add_argument("--timeout", type=int, default=420, help="Timeout de comandos remotos em segundos.")
    parser.add_argument("--skip-upload", action="store_true", help="Não envia arquivos; apenas executa Docker/migrations.")
    parser.add_argument("--no-build", action="store_true", help="Sobe containers sem rebuild.")
    parser.add_argument("--skip-migrate", action="store_true", help="Não executa manage.py migrate.")
    parser.add_argument("--skip-collectstatic", action="store_true", help="Não executa collectstatic.")
    parser.add_argument("--skip-smoke", action="store_true", help="Não testa /login/ por curl.")
    parser.add_argument("--migrate-only", action="store_true", help="Executa somente migrate e check no app já ativo.")
    return parser


def main() -> int:
    configure_stdout()
    parser = build_parser()
    args = parser.parse_args()
    try:
        deploy(args)
    except Exception as exc:
        print(f"\nERRO: {exc}", file=sys.stderr)
        return 1
    print("\nDeploy concluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
