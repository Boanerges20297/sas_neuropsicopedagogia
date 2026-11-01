"""BTA License Platform S2S consumer for Neuro-Diagnosis.

The BTA controls license status, plans and limits. Product controls account
activation and tenant isolation. Browser never contacts BTA directly.
"""
import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import requests

RESOLVE_PATH = "/api/v1/licenses/resolve"
LICENSED_STATES = frozenset(("active","grace"))


@dataclass(frozen=True)
class LicenseDecision:
    status: str  # licensed | exempt (local admin) | unlicensed | unavailable | not_configured
    state: str = ""
    reason: str = ""
    limits: dict | None = None
    entitlements: dict | None = None

    @property
    def allowed(self):
        return self.status == "exempt" or (self.status == "licensed" and self.state in LICENSED_STATES)


class BTAClient:
    def __init__(self, base_url=None, client_id=None, key_id=None, key_file=None):
        self.base_url = (base_url if base_url is not None else os.getenv("BTA_BASE_URL","")).rstrip("/")
        self.client_id = client_id if client_id is not None else os.getenv("BTA_CLIENT_ID","")
        self.key_id = key_id if key_id is not None else os.getenv("BTA_KEY_ID","")
        self.key_file = key_file if key_file is not None else os.getenv("BTA_PRIVATE_KEY_PATH","")

    def configured(self):
        return bool(self.base_url and self.client_id and self.key_id and self.key_file
                    and os.path.isfile(self.key_file))

    def signed_headers(self, method, path, body):
        if not self.configured():
            raise RuntimeError("Cliente S2S não provisionado")
        timestamp=str(int(time.time()))
        nonce=secrets.token_urlsafe(24)
        digest=hashlib.sha256(body).hexdigest()
        message="\n".join((method.upper(),path,timestamp,nonce,digest)).encode("utf-8")
        with open(self.key_file,"rb") as f:
            key=serialization.load_pem_private_key(f.read(),password=None)
        if not isinstance(key,Ed25519PrivateKey):
            raise ValueError("BTA exige chave Ed25519")
        signature=base64.b64encode(key.sign(message)).decode("ascii")
        return {
            "X-BTA-Client-Id":self.client_id,
            "X-BTA-Key-Id":self.key_id,
            "X-BTA-Timestamp":timestamp,
            "X-BTA-Nonce":nonce,
            "X-BTA-Body-SHA256":digest,
            "X-BTA-Signature":signature,
            "Content-Type":"application/json",
        }

    def resolve(self, tenant_id, display_name=""):
        # Never send patient details, user e-mail or clinical information.
        if not self.configured():
            return LicenseDecision(status="not_configured",reason="s2s_client_not_provisioned")
        body=json.dumps({"customer_key":f"neuro-diagnosis:tenant:{tenant_id}",
                         "display_name":display_name[:120]},separators=(",",":"),ensure_ascii=False).encode("utf-8")
        try:
            headers=self.signed_headers("POST",RESOLVE_PATH,body)
            response=requests.post(self.base_url+RESOLVE_PATH,data=body,headers=headers,timeout=(4,7))
            if response.status_code!=200:
                return LicenseDecision(status="unavailable",reason=f"bta_http_{response.status_code}")
            result=response.json()
            if result.get("contract_version")!=1 or result.get("product")!="neuro-diagnosis":
                return LicenseDecision(status="unavailable",reason="unexpected_contract_or_product")
            if not result.get("licensed"):
                state=(result.get("license") or {}).get("state","")
                return LicenseDecision(status="unlicensed",state=state,reason=result.get("reason") or "not_licensed")
            license_obj=result.get("license") or {}
            state=license_obj.get("state","")
            if state not in LICENSED_STATES:
                return LicenseDecision(status="unlicensed",state=state,reason="invalid_license_state")
            # Do not persist a snapshot before implementing Ed25519 snapshot validation.
            return LicenseDecision(status="licensed",state=state,
                                   limits=result.get("limits") or {},
                                   entitlements=result.get("entitlements") or {})
        except (OSError,ValueError,requests.RequestException):
            return LicenseDecision(status="unavailable",reason="validation_unavailable")


def resolve_tenant_license(tenant_id, name=""):
    return BTAClient().resolve(tenant_id,name)

TRIAL_PATH = "/api/v1/licenses/trials/activate"


@dataclass(frozen=True)
class TrialResult:
    status: str  # activated | denied | unavailable | not_configured
    state: str = ""
    reason: str = ""
    expires_at: str = ""


def activate_tenant_trial(tenant_id, name=""):
    """Request one BTA-issued trial. The 14-day duration is BTA package metadata."""
    client = BTAClient()
    package = os.getenv("BTA_TRIAL_PACKAGE_CODE", "").strip()
    if not client.configured() or not package:
        return TrialResult("not_configured",reason="bta_product_or_trial_package_not_provisioned")
    payload = {
        "customer_key":f"neuro-diagnosis:tenant:{tenant_id}",
        "display_name":name[:120],
        "package_code":package,
        "idempotency_key":f"neuro-diagnosis:trial:tenant:{tenant_id}:v1",
    }
    body=json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    try:
        response=requests.post(
            client.base_url+TRIAL_PATH,data=body,
            headers=client.signed_headers("POST",TRIAL_PATH,body),timeout=(4,7))
        result=response.json()
        if response.status_code!=200 and response.status_code!=201:
            if response.status_code in (400,409,422):
                return TrialResult("denied",reason=str(result.get("error","trial_not_allowed")))
            return TrialResult("unavailable",reason=f"bta_http_{response.status_code}")
        lic=result.get("license") or {}
        if result.get("contract_version")!=1 or result.get("product")!="neuro-diagnosis":
            return TrialResult("unavailable",reason="unexpected_contract")
        if lic.get("modality")!="trial" or not result.get("licensed") or lic.get("state") not in LICENSED_STATES:
            return TrialResult("denied",state=lic.get("state",""),
                               reason=result.get("reason") or "trial_not_active")
        # Snapshot validity and dates are decided by BTA; do not manufacture 14 days.
        return TrialResult("activated",state=lic["state"],expires_at=lic.get("expires_at") or "")
    except (OSError,ValueError,requests.RequestException):
        return TrialResult("unavailable",reason="bta_unavailable")
