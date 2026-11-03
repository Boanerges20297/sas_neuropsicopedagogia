"""Safety and contract tests for NeuroCore's TEA/TDAH experimental pilot."""
import json
import unittest
from pathlib import Path

from neurocore import evaluate_evidence, list_topics, search_references


class NeuroCoreEvidenceTests(unittest.TestCase):
    def test_two_topics_and_distinct_checklists(self):
        topics = {row["id"]: row["fields"] for row in list_topics()}
        self.assertEqual(set(topics), {"tea", "tdah"})
        self.assertGreaterEqual(topics["tea"], 7)
        self.assertGreaterEqual(topics["tdah"], 7)
        self.assertNotEqual(
            {row["key"] for row in evaluate_evidence("tea", {})["pending"]},
            {row["key"] for row in evaluate_evidence("tdah", {})["pending"]},
        )

    def test_missing_evidence_produces_gaps_not_diagnosis(self):
        data = evaluate_evidence("tea", {"historico_desenvolvimento": "documentado"})
        self.assertEqual(data["status"], "revisao_profissional_necessaria")
        self.assertEqual(data["counts"]["documentado"], 1)
        self.assertGreater(len(data["pending"]), 0)
        self.assertIsNone(data["clinical_conclusion"])
        self.assertIn("não confirma", data["warning"])
        self.assertTrue(data["references"])

    def test_documenting_everything_never_generates_diagnosis(self):
        for topic in ("tea", "tdah"):
            keys = {row["key"] for row in evaluate_evidence(topic, {})["pending"]}
            data = evaluate_evidence(topic, {key: "documentado" for key in keys})
            self.assertEqual(data["pending"], [])
            self.assertEqual(data["status"], "revisao_profissional_necessaria")
            self.assertIsNone(data["clinical_conclusion"])

    def test_invalid_evidence_fails_closed(self):
        for value in ("positivo", "diagnosticado", None, 99):
            with self.assertRaises(ValueError):
                evaluate_evidence("tdah", {"contextos_multiplos": value})
        with self.assertRaises(ValueError):
            evaluate_evidence("tea", {"paciente_id": 14})
        with self.assertRaises(ValueError):
            evaluate_evidence("tdah", {"impacto_funcional": {
                "status": "nao_aplicavel", "justificativa": "n/a"}})
        with self.assertRaises(ValueError):
            evaluate_evidence("outro", {})

    def test_not_applicable_needs_justification(self):
        data = evaluate_evidence("tea", {"informacoes_escola": {
            "status": "nao_aplicavel",
            "justificativa": "Criança ainda não frequenta escola."}})
        self.assertEqual(data["counts"]["nao_aplicavel"], 1)

    def test_reference_urls_and_review_pending(self):
        knowledge = json.loads((Path(__file__).parents[1] / "neurocore" /
                                "knowledge.json").read_text(encoding="utf-8"))
        self.assertTrue(all(ref["url"].startswith("https://") for ref in knowledge["references"]))
        self.assertTrue(all(ref["review_status"] == "reference_verified_not_clinically_curated"
                            for ref in knowledge["references"]))
        self.assertTrue(all("full_text" not in ref for ref in knowledge["references"]))


class NeuroCoreRetrievalTests(unittest.TestCase):
    def test_source_retrieval_is_topic_scoped(self):
        refs = search_references("escola atenção múltiplos ambientes", "tdah", 4)
        self.assertTrue(refs)
        self.assertLessEqual(len(refs), 4)
        self.assertTrue(all(row["similarity_for_retrieval_only"] > 0 for row in refs))
        autism_refs = search_references("desenvolvimento cuidadores interação", "tea", 4)
        self.assertTrue(autism_refs)

    def test_query_and_topic_rejected(self):
        for topic in ("outro", "diagnosticar", ""):
            with self.assertRaises(ValueError):
                search_references("texto", topic)
        with self.assertRaises(ValueError):
            search_references("x" * 501, "tea")


if __name__ == "__main__":
    unittest.main()
