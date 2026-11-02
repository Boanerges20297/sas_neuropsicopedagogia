"""Read-only structural release checks, also runnable on the STI."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
def check():
    required = [
        "release.json", "Dockerfile", ".dockerignore",
        "docker-compose.saas.yml", "docker-compose.runner.yml", "requirements.production.txt",
        "scripts/runner-watch.sh", "scripts/runner-release.sh",
        "scripts/runner-gates.sh", "scripts/release_request.py",
        "infra/runner/runner-entrypoint.sh", "infra/runner/Dockerfile",
        "infra/host/neuro-host-gateway",
        "infra/host/deploy-neuro-diagnosis-saas.sh",
    ]
    missing = [n for n in required if not (ROOT / n).is_file()]
    if missing:
        raise RuntimeError("Missing canonical files: " + ", ".join(missing))
    if (ROOT / ".github" / "workflows").exists():
        raise RuntimeError("GitHub Actions are forbidden for this pipeline")
    for name in ("Dockerfile", "docker-compose.saas.yml", "docker-compose.runner.yml"):
        body = (ROOT / name).read_text(encoding="utf-8-sig")
        if "/var/run/docker.sock" in body or "privileged: true" in body:
            raise RuntimeError("Unsafe runtime in " + name)
    print("NEURO_PIPELINE_STRUCTURE_OK")
if __name__ == "__main__":
    check()
