"""
api.py — FastAPI server

Spuštění:
    python -m uvicorn api:app --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from query import answer, _collection

app = FastAPI(title="Nutrition RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Question(BaseModel):
    text: str


@app.post("/ask")
def ask(q: Question):
    if not q.text.strip():
        raise HTTPException(status_code=400, detail="Otázka nesmí být prázdná")
    try:
        return answer(q.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
def status():
    try:
        count = _collection.count()
        return {"status": "ok", "chunks_in_db": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# Frontend — musí být poslední
frontend_path = Path("frontend")
if frontend_path.exists():
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")