from __future__ import annotations

from pathlib import Path

import pytest

from skill_evolution.reporter import (
    DiffReporter,
    EvolutionResult,
    apply_report,
    latest_report,
)
from skill_evolution.validators import validate


def _result(skill_name: str, original: str, improved: str) -> EvolutionResult:
    validation = validate(
        original,
        improved,
        max_lines=500,
        description_ratio_min=0.2,
        description_ratio_max=3.0,
    )
    return EvolutionResult(
        skill_name=skill_name,
        original_content=original,
        improved_content=improved,
        root_cause="body was too brief",
        change_summary="expanded body",
        confidence=0.8,
        backend="anthropic",
        validation=validation,
    )


ORIGINAL = """---
name: t
description: original description text here.
---

# t
old body
"""

IMPROVED = """---
name: t
description: slightly expanded description text here.
---

# t
new body
"""


def test_report_includes_diff_gates_and_sidecar(tmp_path):
    reports_dir = tmp_path / "reports"
    reporter = DiffReporter(reports_dir)

    skill_path = tmp_path / "skills" / "t" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(ORIGINAL, encoding="utf-8")

    written = reporter.write(_result("t", ORIGINAL, IMPROVED), skill_path)
    assert written.report_path.exists()
    assert written.proposed_path.exists()
    assert written.proposed_path.name.endswith(".proposed.md")

    text = written.report_path.read_text(encoding="utf-8")
    assert "Diff" in text
    assert "-old body" in text
    assert "+new body" in text
    assert "80%" in text
    assert "Validation gates" in text
    assert written.proposed_path.name in text  # report points at sidecar
    assert "skill-evolution apply --report" in text

    # sidecar holds the full improved SKILL.md, byte-for-byte
    assert written.proposed_path.read_text(encoding="utf-8") == IMPROVED


def test_report_marks_failed_validation(tmp_path):
    reporter = DiffReporter(tmp_path / "reports")
    bad = IMPROVED.replace("name: t", "name: CHANGED")
    written = reporter.write(_result("t", ORIGINAL, bad), Path(tmp_path / "SKILL.md"))
    assert "FAILED at frontmatter" in written.report_path.read_text(encoding="utf-8")


def test_apply_report_overwrites_skill_and_archives(tmp_path):
    skills_dir = tmp_path / "skills"
    reports_dir = tmp_path / "reports"
    reporter = DiffReporter(reports_dir)

    skill_path = skills_dir / "t" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(ORIGINAL, encoding="utf-8")

    written = reporter.write(_result("t", ORIGINAL, IMPROVED), skill_path)

    result = apply_report(
        written.report_path, skills_dir=skills_dir, reports_dir=reports_dir
    )

    # SKILL.md replaced
    assert skill_path.read_text(encoding="utf-8") == IMPROVED
    # report and sidecar moved into applied/
    assert not written.report_path.exists()
    assert not written.proposed_path.exists()
    assert result.archived_report.exists()
    assert result.archived_proposed.exists()
    assert result.archived_report.parent.name == "applied"
    # commit hint mentions skill name and timestamp
    assert "skill(t)" in result.suggested_commit
    assert "git add" in result.suggested_commit


def test_apply_missing_sidecar_raises(tmp_path):
    skills_dir = tmp_path / "skills"
    reports_dir = tmp_path / "reports"
    skill_path = skills_dir / "t" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(ORIGINAL, encoding="utf-8")
    reports_dir.mkdir()

    orphan = reports_dir / "t-20260424_120000.md"
    orphan.write_text("body", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="proposal sidecar missing"):
        apply_report(orphan, skills_dir=skills_dir, reports_dir=reports_dir)


def test_apply_bad_report_name_raises(tmp_path):
    skills_dir = tmp_path / "skills"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    bad = reports_dir / "not-a-report.md"
    bad.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="unrecognised report filename"):
        apply_report(bad, skills_dir=skills_dir, reports_dir=reports_dir)


def test_latest_report_picks_most_recent(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    older = reports_dir / "t-20260101_000000.md"
    newer = reports_dir / "t-20260424_120000.md"
    other = reports_dir / "u-20260424_120000.md"
    sidecar = reports_dir / "t-20260424_120000.proposed.md"
    for p in (older, newer, other, sidecar):
        p.write_text("x", encoding="utf-8")

    # bump mtime so 'newer' really is newer regardless of write order
    import os
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_800_000_000, 1_800_000_000))

    assert latest_report(reports_dir, "t") == newer
    assert latest_report(reports_dir, "missing") is None


def test_latest_report_skips_sidecars(tmp_path):
    """A skill whose only file is a stranded .proposed.md returns None."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "t-20260424_120000.proposed.md").write_text("x", encoding="utf-8")
    assert latest_report(reports_dir, "t") is None
