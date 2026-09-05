"""
In-memory dataset + conversation session store.

Explicitly an MVP shortcut: fine for a single-process demo/resume
deployment, called out in the README as the first thing to swap for
Redis/Postgres in a "real" production version (session affinity /
horizontal scaling would otherwise break).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.data.ingestion import Dataset


@dataclass
class ConversationTurn:
    question: str
    sql: str | None
    answer: str
    facts: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    session_id: str
    dataset_id: str
    turns: list[ConversationTurn] = field(default_factory=list)


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._datasets: dict[str, Dataset] = {}
        self._suggestions: dict[str, list[dict[str, str]]] = {}
        self._sessions: dict[str, Session] = {}

    # --- datasets ---------------------------------------------------------
    def put_dataset(self, dataset: Dataset) -> None:
        with self._lock:
            self._datasets[dataset.dataset_id] = dataset

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        with self._lock:
            return self._datasets.get(dataset_id)

    def put_suggestions(self, dataset_id: str, suggestions: list[dict[str, str]]) -> None:
        with self._lock:
            self._suggestions[dataset_id] = suggestions

    def get_suggestions(self, dataset_id: str) -> list[dict[str, str]]:
        with self._lock:
            return self._suggestions.get(dataset_id, [])

    # --- sessions -----------------------------------------------------------
    def get_or_create_session(self, session_id: str, dataset_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.dataset_id != dataset_id:
                session = Session(session_id=session_id, dataset_id=dataset_id)
                self._sessions[session_id] = session
            return session

    def add_turn(self, session_id: str, turn: ConversationTurn, max_turns: int) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return
            session.turns.append(turn)
            if len(session.turns) > max_turns:
                session.turns = session.turns[-max_turns:]

    def history_text(self, session_id: str) -> str:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or not session.turns:
                return "(no prior turns)"
            lines = []
            for t in session.turns:
                lines.append(f"Q: {t.question}\nA: {t.answer}" + (f"\nSQL: {t.sql}" if t.sql else ""))
            return "\n\n".join(lines)


store = Store()
