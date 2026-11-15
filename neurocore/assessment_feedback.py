"""Optional documentary feedback for a received custom questionnaire.

Never tests DSM diagnostic criteria, estimates a disorder, or copies DSM content.
Only the authenticated professional route can call this with decrypted answers.
"""
from neurocore.engine import load_knowledge
from saas_assessment_flow import parse_definition


def received_test_feedback(raw_definition, answers, topic):
    """Summarize coverage of professional-mapped review areas, without diagnosis.

    A submitted answer means material exists for human review, NOT that a
    clinical criterion or an evidence-review status has been satisfied.
    """
    knowledge = load_knowledge()
    if topic not in knowledge["topics"]:
        raise ValueError("Tema NeuroCore inválido")
    if not isinstance(answers, dict):
        raise ValueError("Respostas inválidas")
    definition = parse_definition(raw_definition)
    declared_topic = definition.get("neurocore_topic")
    if declared_topic and declared_topic != topic:
        raise ValueError("Tema diferente do definido pelo autor do instrumento")
    fields = knowledge["topics"][topic]["review_fields"]
    areas = []
    for field in fields:
        linked = [q for q in definition["questions"]
                  if q.get("neurocore_field") == field["key"]]
        received = [q for q in linked
                    if answers.get(q["key"]) not in (None, "", [])]
        areas.append({
            "key": field["key"],
            "label": field["label"],
            "guidance": field["reason"],
            "linked": len(linked),
            "answered": len(received),
            "questions": [{"label": q["label"],
                           "answered": q in received} for q in linked],
            "status": ("com_respostas" if received else
                       "sem_resposta" if linked else "sem_vinculo"),
            "references": [ref for ref in knowledge["references"]
                           if ref["id"] in field["refs"]],
        })
    linked_total = sum(a["linked"] for a in areas)
    answered_total = sum(a["answered"] for a in areas)
    return {
        "topic": topic,
        "topic_name": knowledge["topics"][topic]["name"],
        "knowledge_version": knowledge["version"],
        "areas": areas,
        "mapped_questions": linked_total,
        "answered_questions": answered_total,
        "unmapped_questions": len(definition["questions"]) - linked_total,
        "has_mapping": linked_total > 0,
        "disclaimer": (
            "A presença de respostas não comprova critérios do DSM-5-TR. "
            "Esta conferência apenas mostra o material disponível e o que "
            "ainda precisa de avaliação profissional contextualizada."
        ),
    }
