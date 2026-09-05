"""
FastAPI entrypoint. Wires together ingestion, the LangGraph orchestrator,
and the in-memory session store behind a small REST API consumed by the
React frontend.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.agents.llm_client import LLMClient
from app.agents.orchestrator import run_pipeline
from app.agents.question_generator import generate_suggestions
from app.config import get_settings
from app.data.ingestion import Dataset, IngestionError, ingest_dataframe, ingest_file
from app.data.sample_data import generate_sales_dataset
from app.models import ChatRequest, ChatResponse, ExecutionStep, ProfileResponse
from app.session_store import ConversationTurn, store

settings = get_settings()
llm_client = LLMClient()

app = FastAPI(title="AI Data Analyst Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_sample_dataset_id: str | None = None


def _profile_response(dataset: Dataset) -> ProfileResponse:
    suggestions = store.get_suggestions(dataset.dataset_id)
    if not suggestions:
        suggestions = generate_suggestions(dataset.profile, llm_client)
        store.put_suggestions(dataset.dataset_id, suggestions)
    return ProfileResponse(
        dataset_id=dataset.dataset_id, name=dataset.name, profile=dataset.profile, suggestions=suggestions
    )


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_enabled": llm_client.enabled,
    }


@app.get("/api/sample", response_model=ProfileResponse)
def get_sample_dataset() -> ProfileResponse:
    global _sample_dataset_id
    if _sample_dataset_id is None or store.get_dataset(_sample_dataset_id) is None:
        df = generate_sales_dataset()
        dataset = ingest_dataframe(df, "Sample Sales Dataset")
        store.put_dataset(dataset)
        _sample_dataset_id = dataset.dataset_id
    dataset = store.get_dataset(_sample_dataset_id)
    assert dataset is not None
    return _profile_response(dataset)


@app.post("/api/upload", response_model=ProfileResponse)
async def upload_dataset(file: UploadFile = File(...)) -> ProfileResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        dataset = ingest_file(tmp_path, file.filename)
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    store.put_dataset(dataset)
    return _profile_response(dataset)


@app.get("/api/datasets/{dataset_id}/profile", response_model=ProfileResponse)
def get_profile(dataset_id: str) -> ProfileResponse:
    dataset = store.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return _profile_response(dataset)


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    dataset = store.get_dataset(req.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload or load the sample dataset first.")

    store.get_or_create_session(req.session_id, req.dataset_id)
    history = store.history_text(req.session_id)

    final_state = run_pipeline(
        question=req.message,
        profile=dataset.profile,
        parquet_path=str(dataset.parquet_path),
        history=history,
        llm=llm_client,
    )

    turn = ConversationTurn(
        question=req.message,
        sql=final_state.get("sql"),
        answer=final_state.get("answer", ""),
        facts=final_state.get("facts", {}),
    )
    store.add_turn(req.session_id, turn, max_turns=settings.max_history_turns)

    return ChatResponse(
        answer=final_state.get("answer", ""),
        sql=final_state.get("sql"),
        chart=final_state.get("chart"),
        facts=final_state.get("facts"),
        execution_trace=[ExecutionStep(**t) for t in final_state.get("trace", [])],
        execution_ms=final_state.get("execution_ms"),
        low_confidence=final_state.get("low_confidence", False),
        error=final_state.get("error") if not final_state.get("result") else None,
    )
