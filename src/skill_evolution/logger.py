from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_FAILURE_TYPES = frozenset(
    {
        "undertrigger",
        "overtrigger",
        "wrong_output",
        "incomplete",
        "missing_pattern",
    }
)


@dataclass
class TraceEntry:
    skill_name: str
    trigger_context: str
    failure_type: str
    failure_reason: str
    hypothesis: str
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.failure_type not in ALLOWED_FAILURE_TYPES:
            raise ValueError(
                f"failure_type must be one of {sorted(ALLOWED_FAILURE_TYPES)}, "
                f"got {self.failure_type!r}"
            )


class TraceLogger:
    """Append-only trace writer. Pure filesystem I/O — no LLM calls."""

    def __init__(self, traces_dir: Path) -> None:
        self.traces_dir = traces_dir
        self.traces_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, skill_name: str) -> Path:
        return self.traces_dir / f"{skill_name}.jsonl"

    def append(self, entry: TraceEntry) -> Path:
        path = self._path(entry.skill_name)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return path

    def load(self, skill_name: str) -> list[TraceEntry]:
        path = self._path(skill_name)
        if not path.exists():
            return []
        entries: list[TraceEntry] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(TraceEntry(**json.loads(line)))
        return entries

    def skills_with_traces(self) -> list[str]:
        if not self.traces_dir.exists():
            return []
        return sorted(p.stem for p in self.traces_dir.glob("*.jsonl"))
