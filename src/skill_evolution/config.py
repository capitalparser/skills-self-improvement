from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "backends": {
        "primary": "anthropic",
        "anthropic": {"model": "claude-sonnet-4-6", "max_tokens": 4096},
    },
    "evolution": {
        "auto": "light",
        "min_traces_before_evolve": 5,
        "min_evals_before_evolve": 3,
        "train_split": 0.6,
    },
    "constraints": {
        "max_skill_lines": 500,
        "description_ratio_min": 0.2,
        "description_ratio_max": 3.0,
    },
    "paths": {
        "skills_dir": "skills",
        "runtime_dir": ".skill-evolution",
    },
}


@dataclass(frozen=True)
class Config:
    project_root: Path
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def skills_dir(self) -> Path:
        return self.project_root / self.raw["paths"]["skills_dir"]

    @property
    def runtime_dir(self) -> Path:
        return self.project_root / self.raw["paths"]["runtime_dir"]

    @property
    def traces_dir(self) -> Path:
        return self.runtime_dir / "traces"

    @property
    def summaries_dir(self) -> Path:
        return self.runtime_dir / "summaries"

    @property
    def reports_dir(self) -> Path:
        return self.runtime_dir / "reports"

    def skill_path(self, skill_name: str) -> Path:
        return self.skills_dir / skill_name / "SKILL.md"

    def evals_path(self, skill_name: str) -> Path:
        return self.skills_dir / skill_name / "evals" / "evals.json"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(project_root: Path) -> Config:
    config_path = project_root / ".skill-evolution" / "config.yaml"
    raw = dict(DEFAULTS)
    if config_path.exists():
        overrides = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        raw = _deep_merge(raw, overrides)
    return Config(project_root=project_root, raw=raw)


def ensure_runtime_dirs(config: Config) -> None:
    for directory in (config.traces_dir, config.summaries_dir, config.reports_dir):
        directory.mkdir(parents=True, exist_ok=True)
