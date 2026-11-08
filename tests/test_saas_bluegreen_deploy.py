"""Production blue/green deployment must never stop primary before canary is ready."""
import unittest
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]


class BlueGreenContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deploy=(BASE/"infra/host/deploy-neuro-diagnosis-saas.sh").read_text(encoding="utf-8")
        cls.router=(BASE/"infra/host/neuro-router-bluegreen.sh").read_text(encoding="utf-8")
        cls.stage=(BASE/"docker-compose.saas.stage.yml").read_text(encoding="utf-8")

    def test_stage_is_opt_in_and_isolated(self):
        stage=self.stage
        self.assertIn("profiles: [stage]",stage)
        self.assertIn("container_name: neuro-diagnosis-flask-stage",stage)
        self.assertIn('127.0.0.1:8782:8000',stage)
        self.assertIn("traefik.enable=false",stage)
        for required in ('read_only: true','cap_drop: [ALL]',
                         'no-new-privileges:true','user: "10001:10001"',
                         'MYSQL_HOST: neuro-diagnosis-db',
                         'bta_internal','neuro_existing',
                         'neuro_data:/var/lib/neuro-diagnosis'):
            self.assertIn(required,stage)

    def test_router_is_scoped_and_atomic(self):
        script=self.router
        self.assertIn("neuro-diagnosis-bluegreen.yml",script)
        self.assertIn('PORT="${1:-}"',script)
        self.assertIn('8781',script)
        self.assertIn('8782',script)
        self.assertIn('mktemp "$DYNAMIC_DIR/',script)
        self.assertIn('mv -f "$TMP" "$ROUTE"',script)
        self.assertIn('X-Neuro-Deploy-Slot:',script)
        self.assertIn('priority: 2100',script)
        self.assertIn('priority: 2000',script)
        self.assertIn('neuro-auth-limit',script)
        self.assertIn('neuro-general-limit',script)
        self.assertNotIn('docker restart',script)
        self.assertNotIn('docker compose down',script)

    def test_rollout_validates_stage_before_recreating_primary(self):
        script=self.deploy
        steps=[
            'docker compose -f "$COMPOSE" build web',
            'up -d --no-deps --force-recreate --no-build web_stage',
            'smoke_local 8782 ||',
            'bash "$ROUTER_SCRIPT" 8782',
            'smoke_public stage ||',
            'up -d --no-deps --force-recreate --no-build web',
            'smoke_local 8781 ||',
            'bash "$ROUTER_SCRIPT" 8781',
            'smoke_public primary ||',
            'ROLLBACK=0',
        ]
        pos=script.index('trap restore EXIT')
        for step in steps:
            found=script.find(step,pos)
            self.assertGreaterEqual(found,pos,step)
            pos=found+len(step)
        self.assertIn('NEURO_ROUTER_SCRIPT_STALE',script)
        self.assertIn('NEURO_BLUEGREEN_BOOTSTRAP_REQUIRED',script)
        self.assertIn('NEURO_STALE_STAGE_REQUIRES_REVIEW',script)
        self.assertIn('NEURO_HOST_SCRIPT_STALE',script)
        self.assertIn('NEURO_ROLLBACK_OLD_PRIMARY_NEVER_STOPPED',script)
        self.assertIn('NEURO_ROLLBACK_PRIMARY_NOT_READY_STAGE_RETAINED',script)
        self.assertNotIn('docker compose -f "$COMPOSE" up -d web\n',script)

    def test_rollback_does_not_tear_down_other_services(self):
        for body in (self.deploy,self.router):
            self.assertNotIn('docker compose down',body)
            self.assertNotIn('docker system prune',body)
            self.assertNotIn('docker network rm',body)
            self.assertNotIn('docker volume rm',body)
        self.assertIn('docker rm -f neuro-diagnosis-flask-stage',self.deploy)


if __name__=="__main__":
    unittest.main()
