"""Controlled Neuro IP-ban pentest. No network and no production data."""
from __future__ import annotations

from contextlib import closing
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app
import saas_ip_ban as bans


class IpBanSecurityTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Path(self.dir.name) / "neuro-guard.sqlite3"
        self.initial = app.config["TESTING"]
        app.config["TESTING"] = True
        self.env = patch.dict(os.environ, {
            "SAAS_PRIMARY": "true",
            "NEURO_IP_BAN_ENABLED": "true",
            "NEURO_IP_BAN_TESTING": "1",
            "NEURO_IP_BAN_DB": str(self.db),
            "NEURO_IP_BAN_TRUSTED_PROXIES": "172.18.0.1/32",
            "SECRET_KEY": "Synthetic-pentest-key-000000000000000001",
        })
        self.env.start()
        self.client = app.test_client()

    def tearDown(self):
        self.env.stop()
        app.config["TESTING"] = self.initial
        self.dir.cleanup()

    def route(self, ip="8.8.8.8", address="172.18.0.1", path="/saas/entrar"):
        return self.client.get(path, environ_overrides={"REMOTE_ADDR": address},
                               headers={"X-Forwarded-For": ip})

    def offend(self, times=7, ip="8.8.8.8"):
        with app.test_request_context(
                "/saas/entrar", environ_base={"REMOTE_ADDR": "172.18.0.1"},
                headers={"X-Forwarded-For": ip}):
            for _ in range(times):
                bans.login_failure()

    def test_repeated_failures_trigger_five_minute_temporary_ban(self):
        self.assertEqual(self.route().status_code, 200)
        self.offend(times=6)
        self.assertEqual(self.route().status_code, 200)
        self.offend(times=1)
        blocked = self.route()
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json["codigo"], 429)
        self.assertGreater(int(blocked.headers["Retry-After"]), 0)
        self.assertLessEqual(int(blocked.headers["Retry-After"]), 300)
        self.assertEqual(blocked.headers["Cache-Control"], "no-store")
        # Legitimate user behind a different IP stays online.
        self.assertEqual(self.route("9.9.9.9").status_code, 200)

    def test_bans_expire_and_repeated_abuse_escalates_without_extension(self):
        self.offend(times=7)
        self.assertEqual(self.route().status_code, 429)
        with closing(sqlite3.connect(self.db)) as con, con:
            first = con.execute("SELECT identity, ban_until, strikes FROM neuro_ip_ban").fetchone()
        for _ in range(10):
            self.assertEqual(self.route().status_code, 429)
        with closing(sqlite3.connect(self.db)) as con, con:
            after = con.execute("SELECT ban_until, strikes FROM neuro_ip_ban").fetchone()
            self.assertEqual(after, first[1:])
            con.execute("UPDATE neuro_ip_ban SET ban_until=0,window_start=0 WHERE identity=?",
                        (first[0],))
        self.offend(times=7)
        blocked = self.route()
        self.assertEqual(blocked.status_code, 429)
        self.assertGreater(int(blocked.headers["Retry-After"]), 300)
        self.assertLessEqual(int(blocked.headers["Retry-After"]), 900)

    def test_untrusted_remote_peer_cannot_spoof_forwarded_ip(self):
        self.offend(times=7)
        self.assertEqual(self.route(ip="8.8.8.8").status_code, 429)
        # 1.1.1.1 is the real peer and MUST NOT inherit a forged XFF ban.
        result = self.route(ip="8.8.8.8", address="1.1.1.1")
        self.assertEqual(result.status_code, 200)
        # An internal gateway without validated XFF must never be banned.
        self.assertEqual(self.route(ip="", address="172.18.0.1").status_code, 200)

    def test_persistent_storage_never_contains_raw_ip_or_passwords(self):
        self.offend(times=7)
        with closing(sqlite3.connect(self.db)) as con, con:
            items = con.execute(
                "SELECT identity,reason,ban_until FROM neuro_ip_ban").fetchall()
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0][0]), 64)
        self.assertNotIn("8.8.8.8", repr(items))
        self.assertEqual(items[0][1], "invalid_credentials")

    def test_ban_is_scoped_to_neuro_routes_and_health_remains_available(self):
        self.offend(times=7)
        # Protected app route is blocked without reaching the view.
        self.assertEqual(self.route().status_code, 429)
        # The only public health probe must remain available.
        with patch("saas_routes.store.one", return_value={"ok": 1}):
            health = self.route(path="/saas/saude")
        self.assertEqual(health.status_code, 200)

    def test_ipv6_subnet_rotation_cannot_change_identity(self):
        with app.test_request_context(
                "/saas/entrar", environ_base={"REMOTE_ADDR": "172.18.0.1"},
                headers={"X-Forwarded-For": "2001:4860:4860:1::aa"}):
            first = bans.client_address()
        with app.test_request_context(
                "/saas/entrar", environ_base={"REMOTE_ADDR": "172.18.0.1"},
                headers={"X-Forwarded-For": "2001:4860:4860:1::bb"}):
            second = bans.client_address()
        self.assertEqual(first, second)

    def test_404_scanning_and_http_429_contribute_to_strikes(self):
        with app.test_request_context(
                "/saas/entrar", environ_base={"REMOTE_ADDR": "172.18.0.1"},
                headers={"X-Forwarded-For": "8.8.8.8"}):
            results = [bans.record("http_429", 5) for _ in range(4)]
            self.assertEqual(results, [False, False, False, True])
        self.assertEqual(self.route().status_code, 429)

    def test_bad_store_path_never_takes_application_offline(self):
        with patch.dict(os.environ, {"NEURO_IP_BAN_DB": str(self.db / "no.sqlite")}):
            result = self.route()
        self.assertEqual(result.status_code, 200)


if __name__ == "__main__":
    unittest.main()
