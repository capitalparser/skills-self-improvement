from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationReport:
    gates: list[GateResult]

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def failed_gate(self) -> str | None:
        for g in self.gates:
            if not g.passed:
                return g.name
        return None


def _parse_frontmatter(content: str) -> dict | None:
    match = FRONTMATTER_RE.match(content)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def check_size(improved: str, max_lines: int) -> GateResult:
    line_count = len(improved.splitlines())
    passed = line_count <= max_lines
    return GateResult(
        name="size",
        passed=passed,
        detail=f"{line_count} lines (limit {max_lines})",
    )


def check_frontmatter(original: str, improved: str) -> GateResult:
    orig = _parse_frontmatter(original)
    new = _parse_frontmatter(improved)
    if new is None:
        return GateResult("frontmatter", False, "YAML frontmatter missing or invalid")
    if orig is None:
        return GateResult("frontmatter", False, "original frontmatter could not be parsed")
    if orig.get("name") != new.get("name"):
        return GateResult(
            "frontmatter",
            False,
            f"name changed: {orig.get('name')!r} -> {new.get('name')!r}",
        )
    if "description" not in new or not str(new.get("description", "")).strip():
        return GateResult("frontmatter", False, "description field is empty")
    return GateResult("frontmatter", True, "name preserved, description present")


def check_description_drift(
    original: str,
    improved: str,
    ratio_min: float,
    ratio_max: float,
) -> GateResult:
    orig = _parse_frontmatter(original) or {}
    new = _parse_frontmatter(improved) or {}
    orig_desc = str(orig.get("description", ""))
    new_desc = str(new.get("description", ""))
    if not orig_desc or not new_desc:
        return GateResult("description_drift", False, "description missing on one side")
    ratio = len(new_desc) / len(orig_desc)
    if ratio < ratio_min or ratio > ratio_max:
        return GateResult(
            "description_drift",
            False,
            f"length ratio {ratio:.2f}x outside [{ratio_min}, {ratio_max}]",
        )
    return GateResult("description_drift", True, f"length ratio {ratio:.2f}x")


def validate(
    original: str,
    improved: str,
    *,
    max_lines: int,
    description_ratio_min: float,
    description_ratio_max: float,
) -> ValidationReport:
    gates = [
        check_size(improved, max_lines=max_lines),
        check_frontmatter(original, improved),
        check_description_drift(
            original,
            improved,
            ratio_min=description_ratio_min,
            ratio_max=description_ratio_max,
        ),
    ]
    return ValidationReport(gates=gates)
