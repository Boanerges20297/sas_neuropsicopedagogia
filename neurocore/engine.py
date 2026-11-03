"""Read-only evidence organization. Does NOT implement DSM diagnostic criteria."""
import json
from functools import lru_cache
from pathlib import Path

_KNOWLEDGE = Path(__file__).with_name("knowledge.json")
VALID_STATES = frozenset({"documentado", "em_investigacao", "nao_documentado", "nao_aplicavel"})


@lru_cache(maxsize=1)
def load_knowledge():
    data = json.loads(_KNOWLEDGE.read_text(encoding="utf-8"))
    if data["schema_version"] != 1:
        raise ValueError("Unsupported NeuroCore knowledge schema")
    return data


def list_topics():
    return [{"id": k, "name": v["name"], "fields": len(v["review_fields"])}
            for k, v in load_knowledge()["topics"].items()]


def evaluate_evidence(topic, evidence):
    """Report documented/missing evidence only, without clinical conclusions.

    evidence: {field_key: "documentado"|"em_investigacao"|"nao_documentado" |
               {"status": "nao_aplicavel", "justificativa": "..."}}.
    The input must never be logged or used for model training.
    """
    knowledge = load_knowledge()
    if topic not in knowledge["topics"]:
        raise ValueError("Assunto não suportado (use tea ou tdah)")
    if not isinstance(evidence, dict):
        raise ValueError("As evidências precisam ser um objeto")
    fields = knowledge["topics"][topic]["review_fields"]
    allowed = {field["key"] for field in fields}
    unknown = set(evidence) - allowed
    if unknown:
        raise ValueError("Campos desconhecidos: " + ", ".join(sorted(unknown)))
    counts = {state: 0 for state in sorted(VALID_STATES)}
    pending, documented, not_applicable = [], [], []
    used_refs = set()
    for field in fields:
        raw = evidence.get(field["key"], "nao_documentado")
        if isinstance(raw, str):
            state, explanation = raw, ""
        elif isinstance(raw, dict):
            state, explanation = raw.get("status"), raw.get("justificativa", "")
        else:
            raise ValueError("Estado de evidência inválido em " + field["key"])
        if state not in VALID_STATES:
            raise ValueError("Estado de evidência inválido em " + field["key"])
        if state == "nao_aplicavel" and (not isinstance(explanation, str) or
                                        len(explanation.strip()) < 10):
            raise ValueError("Não aplicável exige justificativa em " + field["key"])
        counts[state] += 1
        base = {"key": field["key"], "label": field["label"], "state": state}
        if state == "documentado":
            documented.append(base)
        elif state == "nao_aplicavel":
            not_applicable.append({**base, "justificativa": explanation.strip()})
        else:
            pending.append({**base, "orientacao": field["reason"],
                            "references": field["refs"]})
            used_refs.update(field["refs"])
    refs = [{"id": row["id"], "title": row["title"], "url": row["url"]}
            for row in knowledge["references"] if row["id"] in used_refs]
    return {
        "topic": topic, "name": knowledge["topics"][topic]["name"],
        "version": knowledge["version"], "scope": knowledge["scope"],
        "status": "revisao_profissional_necessaria",
        "counts": counts, "fields_total": len(fields),
        "documented": documented, "pending": pending,
        "not_applicable": not_applicable, "references": refs,
        "clinical_conclusion": None,
        "warning": "Somente organização documental; não confirma, exclui ou prediz TEA/TDAH.",
    }
