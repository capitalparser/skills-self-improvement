from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .validators import ValidationReport


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


class DiffReporter:
    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def write(self, result: EvolutionResult, skill_path: Path) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = self.reports_dir / f"{result.skill_name}-{timestamp}.md"

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

Review the diff above. To accept:

```bash
# overwrite the skill file with the improved content, then commit
cp .skill-evolution/reports/{report_path.name} /tmp/proposal.md
# (extract the improved content manually, or use scripts/apply.py if present)
git add {skill_path.relative_to(skill_path.parents[2]) if len(skill_path.parents) >= 3 else skill_path.name}
git commit -m 'skill({result.skill_name}): apply evolution proposal {timestamp}'
```

To reject: delete this report file.
"""
        report_path.write_text(body, encoding="utf-8")
        return report_path
