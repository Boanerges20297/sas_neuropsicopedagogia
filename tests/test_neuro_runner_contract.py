"""Static safety checks for the isolated Neuro-Diagnosis SaaS release runner."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RunnerSecurityContractTests(unittest.TestCase):
    def test_runner_compose_isolated_from_mysql_and_docker_socket(self):
        config = (ROOT / "docker-compose.runner.yml").read_text(encoding="utf-8")
        for expected in ("neuro-diagnosis-runner", "user: \"10001:10001\"",
                         "read_only: true", "no-new-privileges:true",
                         "/var/lib/neuro-pipeline/work:/work",
                         "/var/lib/neuro-pipeline/home:/home/runner"):
            self.assertIn(expected, config)
        for forbidden in ("/var/run/docker.sock", "privileged: true",
                          "/etc/neuro-diagnosis/flask.env",
                          "MYSQL_PASSWORD", "neuro-diagnosis-db"):
            self.assertNotIn(forbidden, config)

    def test_unrequested_commits_never_trigger_deploy(self):
        watcher = (ROOT / "scripts/runner-watch.sh").read_text(encoding="utf-8")
        self.assertIn(".release/request.json", watcher)
        self.assertIn('git diff --quiet "$parent" "$sha" -- .release/request.json', watcher)
        self.assertIn("scripts/runner-release.sh", watcher)

    def test_gateway_requires_exact_sha_and_explicit_host_approval(self):
        gateway = (ROOT / "infra/host/neuro-host-gateway").read_text(encoding="utf-8")
        deploy = (ROOT / "infra/host/deploy-neuro-diagnosis-saas.sh").read_text(encoding="utf-8")
        self.assertIn("SSH_ORIGINAL_COMMAND", gateway)
        self.assertIn("NEURO_GATEWAY_DENIED", gateway)
        self.assertIn("^[0-9a-f]{40}$", deploy)
        self.assertIn("/etc/neuro-diagnosis/host-approved", deploy)
        self.assertIn("mysql_saas_profile_migration.sql", deploy)
        self.assertIn("mysqldump", deploy)

    def test_release_rejects_stale_privileged_host_script_before_checkout(self):
        deploy = (ROOT / "infra/host/deploy-neuro-diagnosis-saas.sh").read_text(encoding="utf-8")
        self.assertIn("NEURO_HOST_SCRIPT_STALE", deploy)
        self.assertIn('git show "$SHA:infra/host/deploy-neuro-diagnosis-saas.sh"', deploy)
        self.assertIn("cmp -s - /usr/local/sbin/deploy-neuro-diagnosis", deploy)
        self.assertLess(deploy.index("NEURO_HOST_SCRIPT_STALE"),
                        deploy.index('git merge --ff-only "$SHA"'))
        self.assertIn("mysql_saas_email_verification_migration.sql", deploy)

    def test_health_gate_checks_new_email_schema(self):
        source = (ROOT / "saas_routes.py").read_text(encoding="utf-8")
        self.assertIn("'SELECT 1 FROM saas_email_verifications LIMIT 1'", source)
        self.assertIn("'SELECT 1 FROM saas_email_challenges LIMIT 1'", source)
        self.assertIn("for query in _HEALTH_READINESS_QUERIES:", source)
        self.assertIn("store.one(query)", source)

    def test_public_route_has_bounded_retries_before_rollback(self):
        deploy = (ROOT / "infra/host/deploy-neuro-diagnosis-saas.sh").read_text(encoding="utf-8")
        self.assertIn('for _ in $(seq 1 30); do', deploy)
        self.assertIn('https://neuro-diagnosis.tech/saas/entrar', deploy)
        self.assertIn('smoke_public stage || { echo NEURO_STAGE_PUBLIC_ROUTE_FAILED', deploy)
        self.assertIn('smoke_public primary || { echo NEURO_PRIMARY_PUBLIC_ROUTE_FAILED', deploy)
        self.assertIn('trap restore EXIT', deploy)
        self.assertIn('^x-neuro-deploy-slot: $slot$', deploy)
        self.assertLess(deploy.index('smoke_local 8782 ||'),
                        deploy.index('bash "$ROUTER_SCRIPT" 8782',deploy.index('# Candidate uses')))
        self.assertLess(deploy.index('smoke_public primary ||'),
                        deploy.index('ROLLBACK=0',deploy.index('# Candidate uses')))

    def test_issue_observability_reserves_one_issue_without_leaking_token(self):
        compose = (ROOT / "docker-compose.runner.yml").read_text(encoding="utf-8")
        observer = (ROOT / "scripts/runner-observe.sh").read_text(encoding="utf-8")
        self.assertIn('NEURO_STATUS_ISSUE: "${NEURO_STATUS_ISSUE:-2}"', compose)
        self.assertIn('TOKEN_FILE=/home/runner/.config/neuro-diagnosis/issue-token', observer)
        self.assertIn("curl --config -", observer)
        self.assertIn("Authorization: Bearer %s", observer)
        self.assertNotIn('-H "Authorization: Bearer $TOKEN"', observer)

    def test_repository_is_public_read_only_for_runner(self):
        entry = (ROOT / "infra/runner/runner-entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("https://github.com/Boanerges20297/sas_neuropsicopedagogia.git", entry)
        self.assertNotIn("gh auth", entry)


if __name__ == "__main__":
    unittest.main()
