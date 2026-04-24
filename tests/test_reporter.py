from __future__ import annotations

from pathlib import Path

from skill_evolution.reporter import DiffReporter, EvolutionResult
from skill_evolution.validators import validate


def test_report_includes_diff_and_gates(tmp_path):
    reports_dir = tmp_path / "reports"
    reporter = DiffReporter(reports_dir)

    original = """---
name: t
description: original description text here.
---

# t
old body
"""
    improved = """---
name: t
description: slightly expanded description text here.
---

# t
new body
"""

    validation = validate(
        original,
        improved,
        max_lines=500,
        description_ratio_min=0.2,
        description_ratio_max=3.0,
    )
    result = EvolutionResult(
        skill_name="t",
        original_content=original,
        improved_content=improved,
        root_cause="body was too brief",
        change_summary="expanded body",
        confidence=0.8,
        backend="anthropic",
        validation=validation,
    )

    skill_path = tmp_path / "skills" / "t" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(original, encoding="utf-8")

    report_path = reporter.write(result, skill_path)
    assert report_path.exists()

    text = report_path.read_text(encoding="utf-8")
    assert "t" in text
    assert "Diff" in text
    assert "-old body" in text
    assert "+new body" in text
    assert "80%" in text  # confidence
    assert "Validation gates" in text


def test_report_marks_failed_validation(tmp_path):
    reporter = DiffReporter(tmp_path / "reports")
    original = """---
name: t
description: desc.
---
body
"""
    improved = """---
name: CHANGED
description: desc.
---
body
"""
    validation = validate(
        original,
        improved,
        max_lines=500,
        description_ratio_min=0.2,
        description_ratio_max=3.0,
    )
    result = EvolutionResult(
        skill_name="t",
        original_content=original,
        improved_content=improved,
        root_cause="x",
        change_summary="x",
        confidence=0.1,
        backend="anthropic",
        validation=validation,
    )
    report_path = reporter.write(result, Path(tmp_path / "SKILL.md"))
    assert "FAILED at frontmatter" in report_path.read_text(encoding="utf-8")
