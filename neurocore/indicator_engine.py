"""Exploratory DSM-aligned indicator patterns for clinician-only NeuroCore use.

High-level domains are based on public CDC/APA guidance. This is NOT a DSM
criteria engine, a validated screening test, a diagnostic model or a classifier.
No external calls, training, persistence or raw clinical logging occur here.
"""
import re

from neurocore.engine import load_knowledge

# Conservative Portuguese phrase patterns: potential mentions, never findings.
# More specific than single-word disorder labels to avoid circular reasoning.
_PATTERNS = {
    "tea": {
        "comunicacao_interacao": [
            ("Interação social", r"\bdificuldade[s]? (?:de|na|em|para) intera[cç][aã]o\b"),
            ("Contato visual", r"\b(?:evita|dificuldade com|pouco) contato visual\b"),
            ("Comunicação não verbal", r"\bdificuldade[s]? (?:com|de entender) gesto[s]?\b"),
        ],
        "interesses_comportamentos": [
            ("Repetição", r"\b(?:movimento[s]? repetitivo[s]?|estereotipia[s]?|ecolalia)\b"),
            ("Rotinas e flexibilidade", r"\b(?:rigidez (?:de|na) rotina|dificuldade com mudan[cç]as)\b"),
            ("Sensibilidade sensorial", r"\b(?:hipersensibilidade (?:sensorial|a sons)|inc[oô]modo intenso com sons)\b"),
            ("Interesses", r"\binteresse[s]? restrito[s]?\b"),
        ],
        "historico_desenvolvimento": [
            ("Desenvolvimento", r"\b(?:atraso na fala|atraso do desenvolvimento)\b"),
        ],
        "funcionamento_necessidades": [
            ("Impacto funcional", r"\b(?:preju[ií]zo social|dificuldade persistente na escola)\b"),
        ],
        "condicoes_associadas": [
            ("Contexto alternativo", r"\b(?:dificuldade auditiva|defici[eê]ncia auditiva|ansiedade intensa)\b"),
        ],
    },
    "tdah": {
        "atencao_atividade": [
            ("Desatenção", r"\b(?:desaten[cç][aã]o|dificuldade[s]? de concentra[cç][aã]o|dificuldade[s]? para se concentrar)\b"),
            ("Impulsividade", r"\b(?:impulsividade|age sem pensar)\b"),
            ("Atividade motora", r"\b(?:inquieta[cç][aã]o|agita[cç][aã]o motora|n[aã]o consegue ficar sentado)\b"),
        ],
        "contextos_multiplos": [
            ("Ambientes", r"\b(?:em casa e na escola|na escola e em casa|em v[aá]rios ambientes)\b"),
        ],
        "curso_temporal": [
            ("Persistência relatada", r"\b(?:h[aá] mais de seis meses|desde a inf[aâ]ncia|h[aá] anos)\b"),
        ],
        "impacto_funcional": [
            ("Impacto funcional", r"\b(?:preju[ií]zo escolar|dificuldade[s]? (?:persistentes )?nas tarefas)\b"),
        ],
        "outras_explicacoes": [
            ("Contexto alternativo", r"\b(?:priva[cç][aã]o de sono|sono insuficiente|ansiedade intensa)\b"),
        ],
        "fontes_multiplas": [
            ("Informantes", r"\b(?:professor(?:a)? relata|familiares relatam)\b"),
        ],
    },
}
_DIFFERENTIAL = {
    "tea": {"condicoes_associadas"},
    "tdah": {"outras_explicacoes"},
}
_NEGATION = re.compile(
    r"\b(?:n[aã]o|sem|nega|nunca|aus[eê]ncia de)\b[^.!?;,]{0,38}$", re.I)


def _chart_signals(topic, record):
    if not record:
        return []
    sources = []
    initial = record.get("intake_text") or ""
    if isinstance(initial, str) and initial.strip():
        sources.append(("Anamnese", initial[:2000]))
    for note in (record.get("notes") or [])[:10]:
        value = note.get("text") or ""
        if isinstance(value, str) and value.strip():
            sources.append(("Atendimento #" + str(note.get("encounter_id", "?")),
                            value[:3000]))
    signals = []
    for origin, text in sources:
        for field, patterns in _PATTERNS[topic].items():
            for label, expression in patterns:
                match = re.search(expression, text, re.I)
                if not match:
                    continue
                preceding = text[max(0, match.start()-70):match.start()]
                negated = bool(_NEGATION.search(preceding))
                snippet = text[max(0, match.start()-55):min(len(text), match.end()+55)]
                signals.append({
                    "field": field, "pattern": label,
                    "source": origin, "source_type": "prontuario",
                    "polarity": "negacao_ou_contraponto" if negated else "mencao_a_revisar",
                    "excerpt": snippet.strip(), "question": None,
                })
                if len(signals) >= 60:
                    return signals
    return signals


def _test_signals(topic, raw_definition, answers):
    if raw_definition is None:
        return []
    from saas_assessment_flow import parse_definition
    definition = parse_definition(raw_definition)
    if definition.get("neurocore_topic") not in (None, topic):
        raise ValueError("Instrumento vinculado a outro tema NeuroCore")
    if not isinstance(answers, dict):
        raise ValueError("Respostas inválidas")
    signals = []
    for q in definition["questions"]:
        field = q.get("neurocore_field")
        if not field or q["type"] not in ("single", "multiple", "yes_no"):
            continue
        marked = {opt["value"]: opt["label"] for opt in q["options"]
                  if opt.get("neurocore_indicator") is True}
        answer = answers.get(q["key"])
        selected = answer if isinstance(answer, list) else [answer]
        for value in selected:
            if isinstance(value, str) and value in marked:
                signals.append({
                    "field": field, "pattern": "Resposta sinalizadora definida pelo autor",
                    "source": "Teste personalizado", "source_type": "teste",
                    "polarity": "sinal_mapeado",
                    "excerpt": marked[value][:140], "question": q["label"][:180],
                })
    return signals


def identify_indicators(topic, *, definition=None, answers=None, record=None):
    """Return traceable review prompts; never return a diagnosis or risk score."""
    knowledge = load_knowledge()
    if topic not in knowledge["topics"]:
        raise ValueError("Tema NeuroCore inválido")
    signals = _test_signals(topic, definition, answers) if definition is not None else []
    signals.extend(_chart_signals(topic, record))
    domains = []
    for field in knowledge["topics"][topic]["review_fields"]:
        matches = [s for s in signals if s["field"] == field["key"]]
        positives = [s for s in matches
                     if s["polarity"] in ("sinal_mapeado", "mencao_a_revisar")]
        sources = {s["source_type"] for s in positives}
        has_opposition = any(s["polarity"] == "negacao_ou_contraponto" for s in matches)
        if has_opposition and positives:
            state = "revisar_divergencia"
        elif len(sources) > 1:
            state = "convergencia_documental"
        elif positives:
            state = "indicador_para_revisar"
        elif has_opposition:
            state = "registro_de_negacao"
        else:
            state = "sem_indicador_identificado"
        domains.append({
            "key": field["key"], "label": field["label"], "state": state,
            "requires_differential_review": field["key"] in _DIFFERENTIAL[topic],
            "signals": matches[:12],
        })
    return {
        "topic": topic, "topic_name": knowledge["topics"][topic]["name"],
        "engine_version": "indicadores-exploratorios-0.1",
        "domains": domains,
        "active_domains": [d for d in domains
                           if d["state"] != "sem_indicador_identificado"],
        "has_record": record is not None,
        "has_test": definition is not None,
        "clinical_conclusion": None, "probability": None, "severity": None,
        "warning": (
            "Indícios textuais e escolhas sinalizadas pelo autor exigem checagem. "
            "Convergência entre fontes não comprova critérios DSM-5-TR. "
            "A ausência de sinal automático não descarta condições clínicas."
        ),
    }
