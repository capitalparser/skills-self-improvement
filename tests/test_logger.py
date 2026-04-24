from __future__ import annotations

import json

import pytest

from skill_evolution.logger import TraceEntry, TraceLogger


def test_trace_entry_rejects_unknown_failure_type():
    with pytest.raises(ValueError):
        TraceEntry(
            skill_name="x",
            trigger_context="c",
            failure_type="bogus",
            failure_reason="r",
            hypothesis="h",
        )


def test_append_and_load_roundtrip(tmp_path):
    logger = TraceLogger(tmp_path / "traces")
    entry = TraceEntry(
        skill_name="docx",
        trigger_context="user asked for word doc",
        failure_type="undertrigger",
        failure_reason="ko keyword missing",
        hypothesis="add ko synonyms",
    )
    logger.append(entry)
    logger.append(entry)

    loaded = logger.load("docx")
    assert len(loaded) == 2
    assert loaded[0].failure_type == "undertrigger"
    assert loaded[0].skill_name == "docx"


def test_jsonl_is_valid(tmp_path):
    logger = TraceLogger(tmp_path / "traces")
    logger.append(
        TraceEntry(
            skill_name="docx",
            trigger_context="c",
            failure_type="wrong_output",
            failure_reason="r",
            hypothesis="h",
        )
    )
    path = tmp_path / "traces" / "docx.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        json.loads(line)


def test_skills_with_traces_lists_only_jsonl(tmp_path):
    traces_dir = tmp_path / "traces"
    logger = TraceLogger(traces_dir)
    logger.append(
        TraceEntry(
            skill_name="a",
            trigger_context="c",
            failure_type="incomplete",
            failure_reason="r",
            hypothesis="h",
        )
    )
    (traces_dir / "noise.txt").write_text("ignore me")
    assert logger.skills_with_traces() == ["a"]


def test_load_missing_returns_empty(tmp_path):
    logger = TraceLogger(tmp_path / "traces")
    assert logger.load("nope") == []
