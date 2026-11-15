"""Clinician-sourced feedback and candidate policy for exploratory NeuroCore.

Scores rank *signal usefulness*, never diagnostic probability. Candidate models
are offline previews: feedback does not change the active indicator detector.
"""
from collections import defaultdict
from hashlib import sha256
import json

VERDICTS = {"confirmado": 1, "descartado": -1, "inconclusivo": 0}
MIN_CASES_FOR_CANDIDATE = 5


def _digest(parts):
    material = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return sha256(material.encode("utf-8")).hexdigest()


def annotate_report(report, *, assessment_id=None, existing=None):
    """Add opaque review keys to server-generated signals, no free text stored."""
    existing = existing or {}
    for domain in report.get("domains", []):
        for signal in domain.get("signals", []):
            feature = _digest([report["topic"], domain["key"],
                               signal["source_type"], signal["pattern"]])
            # Never hash chart excerpts: even a digest of patient text might
            # be vulnerable to dictionary guesses. The source and rule suffice.
            option_key = (signal.get("excerpt")
                          if signal["source_type"] == "teste" else None)
            signature = _digest([feature, signal["source"],
                                 signal.get("question"), option_key,
                                 assessment_id])
            signal["feature_key"] = feature
            signal["feedback_key"] = signature
            signal["feedback_verdict"] = existing.get(signature)
    return report


def select_signal(report, domain_key, signal_key):
    """Only accept a key actually produced by this authorized case review."""
    for domain in report.get("domains", []):
        if domain["key"] == domain_key:
            for signal in domain["signals"]:
                if signal.get("feedback_key") == signal_key:
                    return signal
    raise ValueError("Indicador inválido ou desatualizado")


def candidate_policy(rows):
    """Bayesian shrinkage candidate, pending independent clinical validation.

    Each patient contributes at most once per feature when stored feedback is
    grouped upstream. Contradictory and inconclusive evidence stays explicit.
    """
    totals = defaultdict(lambda: {"confirmado": 0, "descartado": 0,
                                   "inconclusivo": 0, "patients": set()})
    for row in rows:
        verdict = row.get("verdict")
        feature = row.get("feature_key")
        patient = row.get("client_id")
        if verdict not in VERDICTS or not isinstance(feature, str) or not feature:
            continue
        if patient is None:
            continue
        values = totals[feature]
        # One patient / feature / verdict in this candidate; updated verdicts
        # should arrive as the latest state from the database.
        key = (patient, feature)
        if key in values["patients"]:
            continue
        values["patients"].add(key)
        values[verdict] += 1
    candidates = []
    for feature, values in sorted(totals.items()):
        n = len(values["patients"])
        confirmed = values["confirmado"]
        discarded = values["descartado"]
        assessed = confirmed + discarded
        posterior = (1 + confirmed) / (2 + assessed)
        candidates.append({
            "feature_key": feature, "cases": n,
            "confirmado": confirmed, "descartado": discarded,
            "inconclusivo": values["inconclusivo"],
            "candidate_weight": round(posterior, 4),
            "ready_for_review": (n >= MIN_CASES_FOR_CANDIDATE and assessed >= 3),
            "active": False,
        })
    return candidates
