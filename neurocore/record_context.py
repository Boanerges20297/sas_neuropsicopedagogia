"""Explicit, ephemeral chart reading for a patient-scoped NeuroCore review.

No remote AI calls, derived diagnosis, learning, logging of clinical text,
or persistence of the decrypted material in a NeuroCore table.
"""
from html.parser import HTMLParser

import saas_clinical_flow as clinical
import saas_neurocore_store as patients
import saas_patient_intake as intake


class _PlainNote(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data.strip())


def _readable_note(html):
    reader = _PlainNote()
    reader.feed(html or "")
    return " ".join(reader.parts)[:3000]


def read_owned_record(user_id, tenant_id, client_id):
    """Read bounded chart excerpts after explicit professional authorization."""
    if not patients.scoped_client(user_id, tenant_id, client_id):
        raise PermissionError("Prontuário indisponível para este profissional")
    beginning = intake.scoped_summary(user_id, tenant_id, client_id)
    visits = clinical.list_encounters(
        user_id, tenant_id, client_id=client_id, limit=10)
    notes = []
    for visit in visits:
        # latest_note performs a second, encounter-level ownership check.
        note = clinical.latest_note(
            user_id, tenant_id, client_id, visit["id"])
        text = _readable_note(note.get("html", ""))
        if text:
            notes.append({
                "encounter_id": visit["id"],
                "opened_at": visit.get("opened_at"),
                "text": text,
                "truncated": len(_readable_note(note.get("html", ""))) >= 3000,
            })
    diagnoses = (clinical.list_diagnoses(
        user_id, tenant_id, client_id, visits[0]["id"])[:25] if visits else [])
    return {
        "intake_text": (beginning.get("initial_report") or "")[:2000]
                       if beginning else "",
        "visits_count": len(visits),
        "notes": notes,
        "prior_records": [
            {"label": row.get("label"), "certainty": row.get("certainty"),
             "recorded_at": row.get("recorded_at")}
            for row in diagnoses],
        "limit_notice": "Exibidas até 10 consultas recentes e 25 registros de hipótese ou classificação.",
        "warning": "Trechos do prontuário para leitura profissional; nenhuma conclusão foi inferida.",
    }
