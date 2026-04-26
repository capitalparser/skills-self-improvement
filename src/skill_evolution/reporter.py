from __future__ import annotations

import difflib
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .validators import ValidationReport

REPORT_NAME_RE = re.compile(r"^(?P<skill>.+)-(?P<ts>\d{8}_\d{6})\.md$")


@dataclass
class EvolutionResult:
    skill_name: str
    original_content: str
    improved_content: str
    root_cause: str
    change_summary: str
    confidence: float
    backend: str
    validation: ValidationReport


@dataclass
class WrittenReport:
    report_path: Path     # human-readable markdown (diff + metadata)
    proposed_path: Path   # full improved SKILL.md, ready to cp


class DiffReporter:
    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def write(self, result: EvolutionResult, skill_path: Path) -> WrittenReport:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        stem = f"{result.skill_name}-{timestamp}"
        report_path = self.reports_dir / f"{stem}.md"
        proposed_path = self.reports_dir / f"{stem}.proposed.md"

        proposed_path.write_text(result.improved_content, encoding="utf-8")

        diff = "".join(
            difflib.unified_diff(
                result.original_content.splitlines(keepends=True),
                result.improved_content.splitlines(keepends=True),
                fromfile=f"a/{skill_path.name}",
                tofile=f"b/{skill_path.name}",
            )
        )

        gate_rows = "\n".join(
            f"- **{g.name}**: {'pass' if g.passed else 'FAIL'} — {g.detail}"
            for g in result.validation.gates
        )

        body = f"""# Skill evolution proposal: {result.skill_name}

> Generated: {timestamp} UTC
> Backend: {result.backend}
> Confidence: {result.confidence:.0%}
> Validation: {'PASSED' if result.validation.passed else f'FAILED at {result.validation.failed_gate}'}
> Proposed file: `{proposed_path.name}`

## Root cause

{result.root_cause}

## Change summary

{result.change_summary}

## Validation gates

{gate_rows}

## Diff

```diff
{diff}```

## Apply

Accept (one command):

```bash
uv run skill-evolution apply --report .skill-evolution/reports/{report_path.name}
```

That copies `{proposed_path.name}` over the live SKILL.md, archives both
files under `.skill-evolution/reports/applied/`, and prints a suggested
git commit.

Reject:

```bash
rm .skill-evolution/reports/{report_path.name} .skill-evolution/reports/{proposed_path.name}
```
"""
        report_path.write_text(body, encoding="utf-8")
        return WrittenReport(report_path=report_path, proposed_path=proposed_path)


@dataclass
class ApplyResult:
    skill_path: Path
    archived_report: Path
    archived_proposed: Path
    suggested_commit: str


def _parse_report_name(report_path: Path) -> tuple[str, str]:
    match = REPORT_NAME_RE.match(report_path.name)
    if not match:
        raise ValueError(
            f"unrecognised report filename {report_path.name!r}; "
            "expected '<skill>-<YYYYMMDD_HHMMSS>.md'"
        )
    return match["skill"], match["ts"]


def latest_report(reports_dir: Path, skill_name: str) -> Path | None:
    """Return the most recent unapplied report for a skill, or None."""
    if not reports_dir.exists():
        return None
    candidates = sorted(
        (
            p
            for p in reports_dir.glob(f"{skill_name}-*.md")
            if not p.name.endswith(".proposed.md")
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def apply_report(
    report_path: Path,
    *,
    skills_dir: Path,
    reports_dir: Path,
    project_root: Path | None = None,
) -> ApplyResult:
    """Overwrite the live SKILL.md from a proposal sidecar and archive both files.

    Raises FileNotFoundError if either file is missing, ValueError if the
    report filename is malformed. ``project_root`` only affects the path
    shown in ``suggested_commit``.
    """
    skill_name, timestamp = _parse_report_name(report_path)
    proposed_path = report_path.with_name(f"{skill_name}-{timestamp}.proposed.md")
    if not proposed_path.exists():
        raise FileNotFoundError(
            f"proposal sidecar missing: {proposed_path} — "
            "report cannot be applied (re-run evolve)"
        )

    skill_path = skills_dir / skill_name / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"target SKILL.md not found: {skill_path}")

    proposed_content = proposed_path.read_text(encoding="utf-8")
    skill_path.write_text(proposed_content, encoding="utf-8")

    applied_dir = reports_dir / "applied"
    applied_dir.mkdir(parents=True, exist_ok=True)
    archived_report = applied_dir / report_path.name
    archived_proposed = applied_dir / proposed_path.name
    shutil.move(str(report_path), archived_report)
    shutil.move(str(proposed_path), archived_proposed)

    if project_root is not None:
        try:
            commit_path = skill_path.relative_to(project_root)
        except ValueError:
            commit_path = skill_path
    else:
        commit_path = skill_path

    suggested_commit = (
        f"git add {commit_path}\n"
        f"git commit -m 'skill({skill_name}): apply evolution proposal {timestamp}'"
    )
    return ApplyResult(
        skill_path=skill_path,
        archived_report=archived_report,
        archived_proposed=archived_proposed,
        suggested_commit=suggested_commit,
    )
