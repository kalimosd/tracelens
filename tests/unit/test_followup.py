import tempfile
from pathlib import Path

import pytest

from tracelens.agent.followup import answer_followup
from tracelens.artifacts.store import InMemoryArtifactStore, SQLiteArtifactStore
from tracelens.llm import LLMMessage
from tracelens.types import AnalysisResult, EvidenceItem


def _make_result() -> AnalysisResult:
    return AnalysisResult(
        conclusion="Main thread blocked by binder calls",
        key_evidence=[
            EvidenceItem(title="Long slices", summary="inflate=50ms on main"),
            EvidenceItem(title="Blocked threads", summary="main: total=35ms, max_single=20ms, count=3"),
            EvidenceItem(title="Scheduling delay", summary="main=10ms"),
        ],
        analysis_chain=["Selected role-first strategy", "Process com.example.app"],
        optimization_directions=["Move binder calls off main thread"],
        uncertainties=["GPU contribution not measured"],
    )


# --- Follow-up engine tests ---

def test_followup_rule_matches_blocking_keywords():
    result = _make_result()
    answer = answer_followup("为什么线程被阻塞了？", result)
    assert "Blocked threads" in answer
    assert "35ms" in answer


def test_followup_rule_matches_long_slice():
    result = _make_result()
    answer = answer_followup("哪些操作耗时长？", result)
    assert "Long slices" in answer
    assert "inflate" in answer


def test_followup_rule_matches_optimization():
    result = _make_result()
    answer = answer_followup("有什么优化建议？", result)
    assert "binder" in answer.lower()


def test_followup_rule_returns_all_when_no_match():
    result = _make_result()
    answer = answer_followup("xyz random question", result)
    assert "Main thread blocked" in answer


def test_followup_with_fake_llm():
    class FakeLLM:
        def chat(self, messages: list[LLMMessage]) -> str:
            return "The main thread is blocked because of binder IPC latency."

    result = _make_result()
    answer = answer_followup("why is it blocked?", result, llm=FakeLLM())
    assert "binder" in answer.lower()


def test_followup_falls_back_on_llm_error():
    class BrokenLLM:
        def chat(self, messages):
            raise RuntimeError("fail")

    result = _make_result()
    answer = answer_followup("阻塞原因？", result, llm=BrokenLLM())
    assert "Blocked threads" in answer


# --- SQLite store tests ---

def test_sqlite_store_save_and_load():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        store = SQLiteArtifactStore(db_path)
        result = _make_result()
        session_id = store.save(result)
        loaded = store.load(session_id)
        assert loaded is not None
        assert loaded.conclusion == result.conclusion
        assert len(loaded.key_evidence) == 3
        store.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_sqlite_store_returns_none_for_missing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        store = SQLiteArtifactStore(db_path)
        assert store.load("nonexistent") is None
        store.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_inmemory_store_still_works():
    store = InMemoryArtifactStore()
    result = _make_result()
    sid = store.save(result)
    assert store.load(sid) is not None
    assert store.load("nope") is None
