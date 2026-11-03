"""Tiny pure-Python inference on an index trained offline with scikit-learn.

No dependency on numpy/scipy/scikit-learn in the Flask production environment.
Only indexes reviewed bibliographic metadata and ORIGINAL summaries.
Never indexes, persists or sends patient information.
"""
import json
from collections import Counter
from functools import lru_cache
from math import log, sqrt
from pathlib import Path
import re
import unicodedata

_INDEX = Path(__file__).with_name("index.json")


def _tokens(text):
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    words = re.findall(r"(?u)\b\w\w+\b", normalized)
    return words + [" ".join(pair) for pair in zip(words, words[1:])]


@lru_cache(maxsize=1)
def load_index():
    try:
        data = json.loads(_INDEX.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError("Índice ausente; execute neurocore/train_index.py no STI") from exc
    if data.get("schema_version") != 1 or data.get("method") != "tfidf":
        raise RuntimeError("Índice NeuroCore não reconhecido")
    return data


def search_references(query, topic, limit=5):
    """Retrieve source METADATA, not diagnostic hypotheses."""
    if topic not in ("tea", "tdah"):
        raise ValueError("Assunto inválido")
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("Consulta inválida")
    if not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("Limite inválido")
    index = load_index()
    idf = index["idf"]
    counts = Counter(term for term in _tokens(query) if term in idf)
    query_weights = {term: (1.0 + log(count)) * idf[term] for term, count in counts.items()}
    magnitude = sqrt(sum(value * value for value in query_weights.values()))
    if magnitude == 0:
        return []
    for term in query_weights:
        query_weights[term] /= magnitude
    result = []
    for ref in index["references"]:
        if topic not in ref["topics"]:
            continue
        similarity = sum(query_weights.get(term, 0.0) * weight
                         for term, weight in ref["weights"].items())
        if similarity > 1e-8:
            result.append({"id": ref["id"], "title": ref["title"], "url": ref["url"],
                           "similarity_for_retrieval_only": round(similarity, 4)})
    return sorted(result, key=lambda x: (-x["similarity_for_retrieval_only"], x["id"]))[:limit]
