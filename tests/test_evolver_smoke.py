"""Smoke test for the evolver orchestration.

Mocks dspy.ChainOfThought, dspy.GEPA, and the LM loaders so we exercise
the full analyze -> compile -> validate -> report pipeline without any
network calls or API key.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

dspy = pytest.importorskip("dspy")

from skill_evolution import backends, evolver  # noqa: E402
from skill_evolution.config import ensure_runtime_dirs, load_config  # noqa: E402
from skill_evolution.logger import TraceEntry, TraceLogger  # noqa: E402

ORIGINAL_SKILL = """---
name: sample
description: A sample skill for smoke testing the evolver.
---

# sample

Body.
"""

IMPROVED_SKILL = """---
name: sample
description: A sample skill for smoke testing the evolver, now with extra context.
---

# sample

Body, expanded with additional guidance.
"""


@pytest.fixture
def project(tmp_path):
    skill_dir = tmp_path / "skills" / "sample"
    (skill_dir / "evals").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(ORIGINAL_SKILL, encoding="utf-8")
    (skill_dir / "evals" / "evals.json").write_text(
        json.dumps(
            {
                "skill_name": "sample",
                "evals": [
                    {
                        "id": i,
                        "prompt": f"prompt {i}",
                        "expected_output": "out",
                        "assertions": [
                            "The response includes 'extra context'",
                            "The response includes 'expanded'",
                        ],
                    }
                    for i in range(1, 5)
                ],
            }
        ),
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    ensure_runtime_dirs(config)

    logger = TraceLogger(config.traces_dir)
    for i in range(5):
        logger.append(
            TraceEntry(
                skill_name="sample",
                trigger_context=f"context {i}",
                failure_type="undertrigger",
                failure_reason=f"reason {i}",
                hypothesis="add more context",
            )
        )
    return tmp_path, config


def _patch_evolver_dspy(monkeypatch):
    """Replace LM loaders + dspy.ChainOfThought + dspy.GEPA with fakes."""
    monkeypatch.setattr(backends, "load_primary_lm", lambda *a, **k: object())
    monkeypatch.setattr(backends, "load_reflection_lm", lambda *a, **k: object())
    monkeypatch.setattr(dspy, "configure", lambda *a, **k: None)

    def _fake_chain_of_thought(signature):
        sig_name = signature.__name__

        def _call(**kwargs):
            if sig_name == "SkillFailureAnalyzer":
                return SimpleNamespace(
                    root_cause="description lacks specificity",
                    affected_sections="description",
                    improvement_direction="add concrete trigger keywords",
                )
            if sig_name == "SkillImprover":
                return SimpleNamespace(
                    improved_skill_content=IMPROVED_SKILL,
                    change_summary="expanded description and body",
                    confidence_score=0.83,
                )
            raise AssertionError(f"unexpected signature {sig_name}")

        return _call

    monkeypatch.setattr(dspy, "ChainOfThought", _fake_chain_of_thought)

    class _FakeGEPA:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def compile(self, program, trainset, valset):
            # GEPA would return an optimised version; for the smoke test
            # we hand back the same callable. We also stash inputs so the
            # test can assert them.
            self.compiled_with = (program, trainset, valset)
            return program

    monkeypatch.setattr(dspy, "GEPA", _FakeGEPA)


def test_evolve_writes_report_and_sidecar(project, monkeypatch):
    tmp_path, config = project
    _patch_evolver_dspy(monkeypatch)

    written = evolver.SkillEvolver(config).evolve("sample")
    assert written is not None

    assert written.report_path.exists()
    assert written.proposed_path.exists()
    # sidecar holds full improved SKILL.md
    assert written.proposed_path.read_text(encoding="utf-8") == IMPROVED_SKILL

    # report mentions the canned root cause and confidence
    text = written.report_path.read_text(encoding="utf-8")
    assert "description lacks specificity" in text
    assert "83%" in text
    assert "PASSED" in text  # validation should pass: name preserved, size ok


def test_evolve_skips_when_traces_below_min(tmp_path, monkeypatch):
    skill_dir = tmp_path / "skills" / "sample"
    (skill_dir / "evals").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(ORIGINAL_SKILL, encoding="utf-8")
    (skill_dir / "evals" / "evals.json").write_text(
        json.dumps(
            {
                "skill_name": "sample",
                "evals": [
                    {"id": 1, "prompt": "p", "expected_output": "o", "assertions": ["a"]}
                ],
            }
        ),
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    ensure_runtime_dirs(config)
    _patch_evolver_dspy(monkeypatch)

    # zero traces, min is 5 -> should return None without invoking GEPA
    assert evolver.SkillEvolver(config).evolve("sample") is None


def test_evolve_skips_when_evals_below_min(project, monkeypatch):
    tmp_path, config = project
    # blank out evals.json so the eval count is 0
    (tmp_path / "skills" / "sample" / "evals" / "evals.json").write_text(
        json.dumps({"skill_name": "sample", "evals": []}), encoding="utf-8"
    )
    _patch_evolver_dspy(monkeypatch)

    assert evolver.SkillEvolver(config).evolve("sample") is None


def test_evolve_returns_none_for_unknown_skill(tmp_path, monkeypatch):
    config = load_config(tmp_path)
    ensure_runtime_dirs(config)
    _patch_evolver_dspy(monkeypatch)
    assert evolver.SkillEvolver(config).evolve("does-not-exist") is None
