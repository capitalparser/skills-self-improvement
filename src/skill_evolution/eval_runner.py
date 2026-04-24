from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dspy


@dataclass
class EvalCase:
    id: int
    prompt: str
    expected_output: str
    assertions: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalCase":
        return cls(
            id=int(data["id"]),
            prompt=str(data["prompt"]),
            expected_output=str(data.get("expected_output", "")),
            assertions=list(data.get("assertions", [])),
        )


def load_evals(evals_path: Path) -> list[EvalCase]:
    if not evals_path.exists():
        return []
    data = json.loads(evals_path.read_text(encoding="utf-8"))
    return [EvalCase.from_dict(e) for e in data.get("evals", [])]


def evals_to_trainset(
    evals: list[EvalCase],
    *,
    current_skill_content: str,
    root_cause: str,
    improvement_direction: str,
    affected_sections: str,
) -> list[dspy.Example]:
    """Map eval cases to dspy.Examples matching SkillImprover's inputs.

    Every example shares the same skill context; the eval prompt and
    assertions are carried as metadata so the metric can retrieve them.
    """
    trainset: list[dspy.Example] = []
    for case in evals:
        example = dspy.Example(
            current_skill_content=current_skill_content,
            root_cause=root_cause,
            improvement_direction=improvement_direction,
            affected_sections=affected_sections,
            eval_prompt=case.prompt,
            eval_assertions="\n".join(f"- {a}" for a in case.assertions),
        ).with_inputs(
            "current_skill_content",
            "root_cause",
            "improvement_direction",
            "affected_sections",
        )
        trainset.append(example)
    return trainset


def split_trainset(
    trainset: list[dspy.Example], train_split: float
) -> tuple[list[dspy.Example], list[dspy.Example]]:
    """60/40 split in skill-creator style. Deterministic on input order."""
    if len(trainset) < 2:
        return trainset, trainset
    cut = max(1, int(round(len(trainset) * train_split)))
    return trainset[:cut], trainset[cut:]
