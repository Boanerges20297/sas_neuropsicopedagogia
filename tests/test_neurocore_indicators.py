"""NeuroCore exploratory indicators: convergence, negation and tenant-safe boundaries."""
import json
import unittest

from neurocore.indicator_engine import identify_indicators
from saas_assessment_flow import parse_definition, public_definition, professional_score


TEST = {
    "neurocore_topic": "tdah",
    "questions": [
        {"key": "attention", "type": "yes_no",
         "label": "Relata dificuldade persistente de concentração?",
         "neurocore_field": "atencao_atividade",
         "options": [
             {"value": "yes", "label": "Sim", "neurocore_indicator": True, "points": 3},
             {"value": "no", "label": "Não", "points": 0},
         ]},
        {"key": "daily", "type": "text", "label": "Contexto livre",
         "neurocore_field": "contextos_multiplos"},
    ],
}


class IndicatorConfigurationTests(unittest.TestCase):
    def test_author_can_explicitly_mark_one_option_and_public_payload_is_clean(self):
        normalized = parse_definition(TEST)
        marked = normalized["questions"][0]["options"][0]
        self.assertTrue(marked["neurocore_indicator"])
        self.assertEqual(marked["points"], 3)
        visible = json.dumps(public_definition(normalized))
        self.assertNotIn("neurocore", visible)
        self.assertNotIn("points", visible)

    def test_unmapped_or_invalid_marker_fails_closed(self):
        for value in (True, "true", 1):
            test = json.loads(json.dumps(TEST))
            test["questions"][0].pop("neurocore_field")
            test["questions"][0]["options"][0]["neurocore_indicator"] = value
            with self.assertRaises(ValueError):
                parse_definition(test)
        test = json.loads(json.dumps(TEST))
        test["questions"][0]["options"][0]["neurocore_indicator"] = "yes"
        with self.assertRaises(ValueError):
            parse_definition(test)

    def test_score_is_not_a_signal(self):
        test = json.loads(json.dumps(TEST))
        test["questions"][0]["options"][0].pop("neurocore_indicator")
        self.assertEqual(professional_score(test, {"attention": "yes"})["total"], 3)
        report = identify_indicators("tdah", definition=test,
                                     answers={"attention": "yes"})
        self.assertFalse(report["active_domains"])


class IndicatorPatternTests(unittest.TestCase):
    def _domain(self, report, key):
        return next(d for d in report["domains"] if d["key"] == key)

    def test_author_signaled_choice_requires_actual_selected_option(self):
        yes = identify_indicators("tdah", definition=TEST,
                                  answers={"attention": "yes"})
        self.assertEqual(self._domain(yes, "atencao_atividade")["state"],
                         "indicador_para_revisar")
        no = identify_indicators("tdah", definition=TEST,
                                 answers={"attention": "no"})
        self.assertEqual(self._domain(no, "atencao_atividade")["state"],
                         "sem_indicador_identificado")

    def test_chart_mentions_indicate_multiple_domains_without_diagnosis(self):
        chart = {"intake_text": (
            "Relata dificuldade de concentração em casa e na escola "
            "há mais de seis meses com prejuízo escolar. "
            "Também há privação de sono."), "notes": []}
        report = identify_indicators("tdah", record=chart)
        for key in ("atencao_atividade", "contextos_multiplos",
                    "curso_temporal", "impacto_funcional", "outras_explicacoes"):
            self.assertEqual(self._domain(report, key)["state"],
                             "indicador_para_revisar")
        self.assertTrue(self._domain(report, "outras_explicacoes")
                        ["requires_differential_review"])
        self.assertIsNone(report["clinical_conclusion"])
        self.assertIsNone(report["probability"])
        self.assertIsNone(report["severity"])

    def test_convergence_uses_two_sources_and_retains_provenance(self):
        report = identify_indicators(
            "tdah", definition=TEST, answers={"attention": "yes"},
            record={"intake_text": "Dificuldade de concentração relatada.",
                    "notes": []})
        area = self._domain(report, "atencao_atividade")
        self.assertEqual(area["state"], "convergencia_documental")
        self.assertEqual({s["source_type"] for s in area["signals"]},
                         {"teste", "prontuario"})

    def test_negated_chart_does_not_turn_into_positive_indicator(self):
        report = identify_indicators(
            "tdah", record={"intake_text": "Não apresenta desatenção.",
                            "notes": []})
        area = self._domain(report, "atencao_atividade")
        self.assertEqual(area["state"], "registro_de_negacao")
        self.assertEqual(area["signals"][0]["polarity"],
                         "negacao_ou_contraponto")

    def test_opposed_sources_require_context_review(self):
        report = identify_indicators(
            "tdah", definition=TEST, answers={"attention": "yes"},
            record={"intake_text": "Família nega desatenção.",
                    "notes": []})
        self.assertEqual(self._domain(report, "atencao_atividade")["state"],
                         "revisar_divergencia")

    def test_unstructured_text_without_specific_pattern_is_not_forced(self):
        report = identify_indicators(
            "tea", record={"intake_text": "Paciente compareceu à consulta.",
                           "notes": []})
        self.assertEqual(report["active_domains"], [])
        self.assertIsNone(report["clinical_conclusion"])

    def test_wrong_topic_rejected(self):
        with self.assertRaises(ValueError):
            identify_indicators("tea", definition=TEST, answers={"attention": "yes"})


if __name__ == "__main__":
    unittest.main()
