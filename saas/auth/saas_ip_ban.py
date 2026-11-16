"""Neuro-Diagnosis project-scoped temporary origin bans.

A bounded, persistent SQLite store on the existing Neuro data volume records
only HMAC pseudonyms, timestamps, strike counts and offense types. No raw IP,
request URL, cookie, username or clinical information is stored.

This is a second line of defense behind Traefik. Traefik's rejected requests
never reach Flask, so 429s generated *at the edge* are not scored here.
"""
from __future__ import annotations

from contextlib import closing
from collections import OrderedDict
import hashlib
import hmac
import ipaddress
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

from flask import current_app, g, jsonify, request

_LOG = logging.getLogger(__name__)
_SETUP_LOCK = threading.Lock()
_INITIALIZED = set()
_WARNING_AT = 0.0
# One-second bounded cache avoids a SQLite read for every dashboard asset
# request. Other Gunicorn workers see fresh bans within at most one second.
_BAN_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 2048
_CACHE_TTL = 1.0
_CLEANUP_AT = 0.0

WINDOW_SECONDS = 60
STRIKE_FORGET_SECONDS = 24 * 3600
BAN_SCHEDULE_SECONDS = (5 * 60, 15 * 60, 45 * 60)
BAN_THRESHOLD = 20
BANNABLE = {400: 2, 403: 1, 404: 1, 429: 5}
SKIP_PATHS = frozenset({"/saas/saude"})
SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS neuro_ip_ban (
    identity TEXT PRIMARY KEY,
    window_start REAL NOT NULL,
    score INTEGER NOT NULL,
    ban_until REAL NOT NULL DEFAULT 0,
    strikes INTEGER NOT NULL DEFAULT 0,
    last_event REAL NOT NULL,
    reason TEXT NOT NULL
)
"""

def _enabled():
    # Do not mutate persistent state from the ordinary Flask test client.
    if current_app.config.get("TESTING") and os.getenv("NEURO_IP_BAN_TESTING") != "1":
        return False
    return (os.getenv("SAAS_PRIMARY", "false").lower() == "true"
            and os.getenv("NEURO_IP_BAN_ENABLED", "true").lower() == "true")

def _in_scope():
    return request.path.startswith("/saas/") and request.path not in SKIP_PATHS

def _trusted_proxies():
    networks = []
    for candidate in os.getenv("NEURO_IP_BAN_TRUSTED_PROXIES", "").split(","):
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            network = ipaddress.ip_network(candidate, strict=True)
        except ValueError:
            raise ValueError("Invalid NEURO_IP_BAN_TRUSTED_PROXIES configuration")
        # No broad private subnets: only the explicitly pinned proxy host.
        if network.num_addresses != 1:
            raise ValueError("Trusted proxies must be individual host addresses")
        networks.append(network)
    return networks

def client_address():
    """Normalize the source IP; never honor client-controlled XFF directly."""
    try:
        peer = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return None
    if any(peer in network for network in _trusted_proxies()):
        chain = request.headers.get("X-Forwarded-For", "")
        # When peer is the gateway, a missing/invalid chain is NOT the gateway.
        if not chain or len(chain) > 512 or chain.count(",") > 5:
            return None
        try:
            # Traefik sanitizes untrusted client forwarding headers at its edge;
            # the final hop represents the client immediately before Traefik.
            peer = ipaddress.ip_address(chain.split(",")[-1].strip())
        except ValueError:
            return None
    # Do not automatically ban proxy, loopback, shared internal or link-local IPs.
    if not peer.is_global:
        return None
    if peer.version == 6:
        peer = ipaddress.ip_network(f"{peer}/64", strict=False).network_address
    return str(peer)

def _identifier(address):
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY must be configured for IP bans")
    return hmac.new(secret.encode("utf-8"),
                    b"neuro-ip-ban-v1:" + address.encode("ascii"),
                    hashlib.sha256).hexdigest()

def _db_path():
    path = Path(os.getenv(
        "NEURO_IP_BAN_DB", "/var/lib/neuro-diagnosis/neuro-ip-bans.sqlite3"))
    if not path.is_absolute():
        raise ValueError("IP ban storage path must be absolute")
    return path

def _connect():
    path = _db_path()
    if str(path) not in _INITIALIZED:
        with _SETUP_LOCK:
            if str(path) not in _INITIALIZED:
                # Existing mounted volume only. Never create a directory outside
                # the application installation.
                with closing(sqlite3.connect(str(path), timeout=0.2)) as con:
                    con.execute("PRAGMA journal_mode=WAL")
                    con.execute("PRAGMA busy_timeout=200")
                    con.execute(SQL_SCHEMA)
                    con.execute("CREATE INDEX IF NOT EXISTS neuro_ip_ban_expiry "
                                "ON neuro_ip_ban(last_event)")
                    con.commit()
                _INITIALIZED.add(str(path))
    con = sqlite3.connect(str(path), timeout=0.2)
    con.execute("PRAGMA busy_timeout=200")
    return con

def _warn_sparingly(exc):
    global _WARNING_AT
    now = time.monotonic()
    if now - _WARNING_AT > 60:
        _WARNING_AT = now
        _LOG.warning("Neuro IP ban store unavailable (%s); Traefik limits remain active.",
                     type(exc).__name__)

def _active_ban(identity, now):
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT ban_until FROM neuro_ip_ban WHERE identity=?",
            (identity,)).fetchone()
    return max(0, int(row[0] - now + 0.999)) if row and row[0] > now else 0

def _cached_ban(identity, now):
    key = (str(_db_path()), identity)
    with _CACHE_LOCK:
        cached = _BAN_CACHE.get(key)
        if cached and cached[0] > now:
            _BAN_CACHE.move_to_end(key)
            return max(0, int(cached[1] - now + 0.999))
    seconds = _active_ban(identity, now)
    with _CACHE_LOCK:
        _BAN_CACHE[key] = (now + _CACHE_TTL, now + seconds)
        _BAN_CACHE.move_to_end(key)
        while len(_BAN_CACHE) > _CACHE_MAX:
            _BAN_CACHE.popitem(last=False)
    return seconds


def enforce():
    """Flask before_request: deny an active ban before DB-backed clinical guards."""
    if not _enabled() or not _in_scope():
        return None
    addr = client_address()
    if addr is None:
        return None
    try:
        seconds = _cached_ban(_identifier(addr), time.time())
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        _warn_sparingly(exc)
        return None  # Availability: Traefik still protects the app.
    if not seconds:
        return None
    g.neuro_ip_ban_blocked = True
    response = jsonify({"erro": "Limite temporário desta conexão. Tente novamente.",
                        "codigo": 429})
    response.status_code = 429
    response.headers["Retry-After"] = str(seconds)
    response.headers["Cache-Control"] = "no-store"
    return response

def _score(identity, weight, reason, now):
    global _CLEANUP_AT
    with closing(_connect()) as con, con:
        con.execute("BEGIN IMMEDIATE")
        # Bounded, opportunistic cleanup prevents unbounded disk growth.
        if now - _CLEANUP_AT > 600:
            con.execute(
                "DELETE FROM neuro_ip_ban WHERE identity IN "
                "(SELECT identity FROM neuro_ip_ban "
                "WHERE last_event < ? ORDER BY last_event LIMIT 1000)",
                (now - STRIKE_FORGET_SECONDS,))
            _CLEANUP_AT = now
        row = con.execute(
            """SELECT window_start,score,ban_until,strikes,last_event
               FROM neuro_ip_ban WHERE identity=?""", (identity,)).fetchone()
        if row:
            window_start, score, ban_until, strikes, last_event = row
            if now - last_event > STRIKE_FORGET_SECONDS:
                strikes = 0
            if ban_until > now:
                return False  # Never extend an existing ban by retries.
            if now - window_start >= WINDOW_SECONDS:
                window_start, score = now, 0
        else:
            window_start, score, ban_until, strikes = now, 0, 0.0, 0
        score = min(BAN_THRESHOLD, score + weight)
        banned = score >= BAN_THRESHOLD
        if banned:
            duration = BAN_SCHEDULE_SECONDS[min(int(strikes),
                                               len(BAN_SCHEDULE_SECONDS) - 1)]
            ban_until = now + duration
            strikes = min(int(strikes) + 1, len(BAN_SCHEDULE_SECONDS))
            score, window_start = 0, now
        con.execute(
            """INSERT INTO neuro_ip_ban
               (identity,window_start,score,ban_until,strikes,last_event,reason)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(identity) DO UPDATE SET
                 window_start=excluded.window_start,score=excluded.score,
                 ban_until=excluded.ban_until,strikes=excluded.strikes,
                 last_event=excluded.last_event,reason=excluded.reason""",
            (identity, window_start, score, ban_until, strikes, now, reason))
        return banned

def record(reason, weight):
    """Only failed/suspicious requests write. Ordinary traffic is read-only."""
    if not _enabled() or not _in_scope():
        return False
    addr = client_address()
    if addr is None:
        return False
    try:
        identity = _identifier(addr)
        result = _score(identity, int(weight), reason, time.time())
        with _CACHE_LOCK:
            _BAN_CACHE.pop((str(_db_path()), identity), None)
        return result
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        _warn_sparingly(exc)
        return False

def login_failure():
    """Explicitly count failed password attempts, which return 302 or 200."""
    record("invalid_credentials", 3)

def track_response(response):
    if not _enabled() or not _in_scope() or getattr(
            g, "neuro_ip_ban_blocked", False):
        return response
    status = response.status_code
    if status in BANNABLE:
        record("http_" + str(status), BANNABLE[status])
    return response
