from __future__ import annotations

import re

import dspy


def _assertion_pass(improved_skill: str, assertion: str) -> bool:
    """Rule-based check: does the improved SKILL.md satisfy this assertion?

    Assertions in skill-creator's evals.json are natural language, but in
    practice many of them reduce to 'the response includes string X'. We
    approximate that by extracting the dominant literal token in the
    assertion and doing a case-insensitive substring match. This is
    intentionally shallow — GEPA only needs a monotonic signal, not a
    precise oracle.
    """
    match = re.search(r"'([^']+)'|\"([^\"]+)\"", assertion)
    needle = (match.group(1) or match.group(2)) if match else None
    if needle:
        return needle.lower() in improved_skill.lower()

    keywords = [w for w in re.findall(r"[A-Za-z_\-\.]{4,}", assertion) if w.lower() not in _STOP]
    if not keywords:
        return False
    hits = sum(1 for k in keywords if k.lower() in improved_skill.lower())
    return hits / len(keywords) >= 0.5


_STOP = frozenset(
    {
        "response",
        "mentions",
        "includes",
        "literal",
        "string",
        "calls",
        "creates",
        "produces",
        "logic",
        "file",
        "word",
        "docx",
        "the",
        "with",
        "name",
    }
)


def skill_quality_metric(
    gold: dspy.Example,
    pred: dspy.Prediction,
    trace=None,
    pred_name=None,
    pred_trace=None,
) -> dspy.Prediction:
    """GEPA-compatible metric.

    Returns dspy.Prediction(score=..., feedback=...) as required by GEPA.
    Score = fraction of assertions the improved SKILL.md appears to cover.
    """
    improved = getattr(pred, "improved_skill_content", "") or ""
    assertions_text = getattr(gold, "eval_assertions", "") or ""
    assertions = [
        line.lstrip("- ").strip()
        for line in assertions_text.splitlines()
        if line.strip()
    ]
    if not assertions:
        return dspy.Prediction(score=0.0, feedback="no assertions provided")

    passed_flags = [_assertion_pass(improved, a) for a in assertions]
    score = sum(passed_flags) / len(passed_flags)

    if all(passed_flags):
        feedback = "all assertions satisfied"
    else:
        missed = [a for a, ok in zip(assertions, passed_flags) if not ok]
        feedback = "Missed assertions:\n" + "\n".join(f"- {m}" for m in missed)

    return dspy.Prediction(score=score, feedback=feedback)
