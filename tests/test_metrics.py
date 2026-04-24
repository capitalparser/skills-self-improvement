from __future__ import annotations

import pytest

dspy = pytest.importorskip("dspy")

from skill_evolution.metrics import skill_quality_metric  # noqa: E402


def _example(assertions):
    return dspy.Example(
        eval_assertions="\n".join(f"- {a}" for a in assertions),
    )


def _prediction(text):
    return dspy.Prediction(improved_skill_content=text)


def test_quoted_literal_match_counts_as_pass():
    gold = _example(["The response includes the literal string 'Q1 Report'"])
    pred = _prediction("... Q1 Report ...")
    result = skill_quality_metric(gold, pred)
    assert result.score == 1.0


def test_missed_assertion_surfaces_in_feedback():
    gold = _example(
        [
            "The response includes the literal string 'Q1 Report'",
            "The response includes the literal string '회의록'",
        ]
    )
    pred = _prediction("only Q1 Report here")
    result = skill_quality_metric(gold, pred)
    assert result.score == 0.5
    assert "회의록" in result.feedback


def test_empty_assertions_scores_zero():
    gold = _example([])
    pred = _prediction("anything")
    result = skill_quality_metric(gold, pred)
    assert result.score == 0.0
