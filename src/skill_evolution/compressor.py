from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .logger import TraceEntry


class TraceCompressor:
    """Rule-based trace summarisation. No LLM calls.

    Produces a markdown summary that an analyzer LLM can consume in Phase 1
    without re-scanning all raw traces.
    """

    def __init__(self, summaries_dir: Path) -> None:
        self.summaries_dir = summaries_dir
        self.summaries_dir.mkdir(parents=True, exist_ok=True)

    def summarise(self, skill_name: str, traces: list[TraceEntry]) -> str:
        if not traces:
            return ""

        by_type: Counter[str] = Counter(t.failure_type for t in traces)
        hypotheses = [t.hypothesis for t in traces if t.hypothesis]
        hypothesis_counts = Counter(hypotheses)

        lines = [
            f"# {skill_name} — trace summary",
            "",
            f"> Last compressed: {datetime.now(timezone.utc).date().isoformat()}",
            f"> Trace count: {len(traces)}",
            "",
            "## Failure type distribution",
            "",
        ]
        for failure_type, count in by_type.most_common():
            lines.append(f"- `{failure_type}`: {count}")

        lines += ["", "## Recurring hypotheses (top 5)", ""]
        for hypothesis, count in hypothesis_counts.most_common(5):
            lines.append(f"- ({count}) {hypothesis}")

        lines += ["", "## Recent examples", ""]
        for entry in traces[-3:]:
            lines.append(f"### {entry.timestamp} — {entry.failure_type}")
            lines.append(f"- **Context**: {entry.trigger_context}")
            lines.append(f"- **Reason**: {entry.failure_reason}")
            lines.append(f"- **Hypothesis**: {entry.hypothesis}")
            lines.append("")

        return "\n".join(lines)

    def write(self, skill_name: str, traces: list[TraceEntry]) -> Path:
        path = self.summaries_dir / f"{skill_name}.md"
        path.write_text(self.summarise(skill_name, traces), encoding="utf-8")
        return path

    def load(self, skill_name: str) -> str:
        path = self.summaries_dir / f"{skill_name}.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""
