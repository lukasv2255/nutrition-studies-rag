"""
embedder.py — Lokální embedding model (žádný API klíč)

Model: paraphrase-multilingual-mpnet-base-v2
- Podporuje češtinu a angličtinu
- ~400MB, stáhne se automaticky při prvním spuštění
- Pak běží offline
"""

from sentence_transformers import SentenceTransformer

MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"Načítám embedding model ({MODEL_NAME})...")
        _model = SentenceTransformer(MODEL_NAME)
        print("Model načten.")
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    model = get_model()
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return vectors.tolist()


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
