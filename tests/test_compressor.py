from __future__ import annotations

from skill_evolution.compressor import TraceCompressor
from skill_evolution.logger import TraceEntry


def _entry(ft: str, h: str = "h") -> TraceEntry:
    return TraceEntry(
        skill_name="docx",
        trigger_context="c",
        failure_type=ft,
        failure_reason="r",
        hypothesis=h,
    )


def test_summary_contains_failure_type_counts(tmp_path):
    compressor = TraceCompressor(tmp_path / "summaries")
    traces = [_entry("undertrigger"), _entry("undertrigger"), _entry("wrong_output")]
    out = compressor.summarise("docx", traces)
    assert "undertrigger`: 2" in out
    assert "wrong_output`: 1" in out
    assert "Trace count: 3" in out


def test_summary_ranks_hypotheses(tmp_path):
    compressor = TraceCompressor(tmp_path / "summaries")
    traces = [
        _entry("undertrigger", h="add korean keywords"),
        _entry("undertrigger", h="add korean keywords"),
        _entry("wrong_output", h="fix cell merging"),
    ]
    out = compressor.summarise("docx", traces)
    assert "(2) add korean keywords" in out


def test_empty_returns_empty(tmp_path):
    compressor = TraceCompressor(tmp_path / "summaries")
    assert compressor.summarise("docx", []) == ""
