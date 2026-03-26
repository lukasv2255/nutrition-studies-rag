"""
query.py — Vyhledávání a generování odpovědí (optimalizovaná verze)

Model a kolekce se načtou jednou při startu, pak zůstanou v paměti.
"""

import os
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv
import anthropic

load_dotenv()

CHROMA_DIR = "./chroma_storage"
COLLECTION_NAME = "nutrition_studies"
TOP_K = 6

SYSTEM_PROMPT = """Jsi odborný asistent nutričního terapeuta. Analyzuješ vědecké studie a odpovídáš na klinické otázky.

Pravidla:
- Odpovídej výhradně na základě poskytnutých úryvků ze studií
- Každé tvrzení podlož číslem zdroje [1], [2] atd.
- Buď přesný a klinicky relevantní
- Pokud studie otázku nepokrývají nebo si odporují, řekni to jasně
- Odpovídej česky"""

# ── Cache — načte se jednou při startu serveru ─────────────────────────────────
print("Připojuji se k databázi...")
_ef = OpenAIEmbeddingFunction(
    api_key=os.environ["OPENAI_API_KEY"],
    model_name="text-embedding-3-small"
)
_client = chromadb.PersistentClient(path=CHROMA_DIR)
_collection = _client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=_ef,
    metadata={"hnsw:space": "cosine"}
)
_claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
print(f"Připraveno. Databáze obsahuje {_collection.count()} úseků.")
# ──────────────────────────────────────────────────────────────────────────────


def search(question: str, top_k: int = TOP_K) -> list[dict]:
    if _collection.count() == 0:
        return []

    results = _collection.query(
        query_texts=[question],
        n_results=min(top_k, _collection.count()),
        include=["documents", "metadatas", "distances"]
    )

    sources = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        sources.append({
            "text": doc,
            "filename": meta["filename"],
            "chunk_index": meta["chunk_index"],
            "relevance": round(1 - dist, 3)
        })

    return sources


def answer(question: str) -> dict:
    sources = search(question)

    if not sources:
        return {
            "answer": "Databáze je prázdná. Spusť nejprve `python ingest.py`.",
            "sources": []
        }

    context = "\n\n---\n\n".join(
        f"[{i+1}] Zdroj: {s['filename']} (relevance: {s['relevance']})\n{s['text']}"
        for i, s in enumerate(sources)
    )

    user_message = f"""Úryvky ze studií:

{context}

---

Otázka: {question}

Odpověz strukturovaně:

**Relevantní citace ze studií:**
(uveď číslo zdroje pro každé tvrzení)

**Závěr:**
(2–3 věty shrnující co studie říkají k otázce)

**Síla důkazů:** slabá / střední / silná
(a krátké odůvodnění proč)"""

    response = _claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    return {
        "answer": response.content[0].text,
        "sources": sources
    }


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Jaký vliv má kreatin na vlasy?"
    result = answer(q)
    print(result["answer"])
    print("\n--- Zdroje ---")
    for s in result["sources"]:
        print(f"  {s['filename']} (relevance: {s['relevance']})")