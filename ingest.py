"""
ingest.py — Nahrání studií do ChromaDB

Zpracuje:
- PDF soubory ze složky studies/
- Textové abstrakty ze složky studies/abstracts/

Použití:
    python ingest.py
"""

import os
import hashlib
from pathlib import Path
from dotenv import load_dotenv

import fitz  # pymupdf
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

load_dotenv()

STUDIES_DIR = Path("studies")
ABSTRACTS_DIR = STUDIES_DIR / "abstracts"
CHROMA_DIR = "./chroma_storage"
COLLECTION_NAME = "nutrition_studies"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    ef = OpenAIEmbeddingFunction(
        api_key=os.environ["OPENAI_API_KEY"],
        model_name="text-embedding-3-small"
    )
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )


def already_ingested(collection, filename: str) -> bool:
    results = collection.get(where={"filename": filename}, limit=1)
    return len(results["ids"]) > 0


def extract_pdf(path: Path) -> str:
    doc = fitz.open(str(path))
    return "\n".join(page.get_text() for page in doc)


def extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        if chunk.strip():
            chunks.append(chunk)
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def ingest_file(collection, path: Path, source_type: str):
    filename = path.name

    if already_ingested(collection, filename):
        print(f"  ↷ Přeskakuji: {filename}")
        return

    print(f"  → {filename}")

    if source_type == "pdf":
        text = extract_pdf(path)
    else:
        text = extract_txt(path)

    if not text.strip():
        print(f"  ✗ Prázdný soubor: {filename}")
        return

    chunks = chunk_text(text)

    ids, documents, metadatas = [], [], []
    for i, chunk in enumerate(chunks):
        chunk_id = hashlib.md5(f"{filename}-{i}".encode()).hexdigest()
        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({
            "filename": filename,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "source_type": source_type,
        })

    batch_size = 50
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i:i+batch_size],
            documents=documents[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size],
        )

    print(f"     ✓ {len(chunks)} úseků ({source_type})")


def main():
    STUDIES_DIR.mkdir(exist_ok=True)
    ABSTRACTS_DIR.mkdir(exist_ok=True)

    collection = get_collection()

    pdfs = sorted(STUDIES_DIR.glob("*.pdf"))
    txts = sorted(ABSTRACTS_DIR.glob("*.txt"))

    if not pdfs and not txts:
        print("Žádné soubory k nahrání.")
        return

    print(f"Nalezeno: {len(pdfs)} PDF, {len(txts)} abstraktů\n")

    for path in pdfs:
        ingest_file(collection, path, "pdf")

    for path in txts:
        ingest_file(collection, path, "abstract")

    print(f"\nDatabáze obsahuje celkem {collection.count()} úseků.")


if __name__ == "__main__":
    main()