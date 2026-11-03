"""STI-only training: TF-IDF retrieval of reviewed SOURCE METADATA.

Command (STI):
    python -m neurocore.train_index

scikit-learn is a DEVELOPMENT dependency only. Output index.json supports
inference through stdlib; no patient records, DSM text, instrument item text.
"""
import json
from pathlib import Path


def train():
    from sklearn.feature_extraction.text import TfidfVectorizer
    base = Path(__file__).parent
    knowledge = json.loads((base / "knowledge.json").read_text(encoding="utf-8"))
    references = knowledge["references"]
    if len({ref["id"] for ref in references}) != len(references):
        raise ValueError("IDs de referências duplicados")
    if any(ref["rights"] not in ("link_and_original_metadata_only",
                                 "metadata_only_pending_reuse_check") for ref in references):
        raise ValueError("Referência sem política de uso permitida")
    # Search only original descriptive summaries and public bibliographic metadata.
    texts = [f'{ref["title"]}. {ref["notes"]}' for ref in references]
    vectorizer = TfidfVectorizer(strip_accents="unicode", lowercase=True,
                                 ngram_range=(1, 2), sublinear_tf=True, norm="l2")
    matrix = vectorizer.fit_transform(texts)
    features = list(vectorizer.get_feature_names_out())
    output = {"schema_version": 1, "method": "tfidf",
              "training_kind": "retrieval_of_bibliographic_metadata_not_clinical_prediction",
              "knowledge_version": knowledge["version"],
              "idf": {term: round(float(idf), 9)
                      for term, idf in zip(features, vectorizer.idf_)},
              "references": []}
    for rownum, ref in enumerate(references):
        vector = matrix.getrow(rownum)
        weights = {features[int(col)]: round(float(value), 9)
                   for col, value in zip(vector.indices, vector.data)}
        output["references"].append({
            "id": ref["id"], "title": ref["title"], "url": ref["url"],
            "topics": ref["topic"], "weights": weights})
    destination = base / "index.json"
    destination.write_text(json.dumps(output, ensure_ascii=False,
                                      separators=(",", ":"), sort_keys=True) + "\n",
                           encoding="utf-8")
    print("NEUROCORE_INDEX_OK", "sources=", len(references),
          "features=", len(features), "bytes=", destination.stat().st_size)


if __name__ == "__main__":
    train()
