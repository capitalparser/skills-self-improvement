from __future__ import annotations

# Imports are lazy: defining Signature classes requires dspy at import time,
# so this module must only be imported from Phase 1 paths.

import dspy


class SkillFailureAnalyzer(dspy.Signature):
    """Diagnose why a skill fell short based on execution traces.

    Do not just restate what failed — identify the root cause in the
    SKILL.md itself (missing keyword, overly rigid rule, missing pattern,
    etc.) and propose a direction of improvement.
    """

    current_skill_content: str = dspy.InputField(desc="Full text of the current SKILL.md.")
    execution_traces: str = dspy.InputField(
        desc="Observation log entries as JSON Lines."
    )
    compressed_summary: str = dspy.InputField(
        desc="Rule-based summary of past traces (may be empty)."
    )

    root_cause: str = dspy.OutputField(
        desc="Concrete root cause of the failures in the SKILL.md (<=200 chars)."
    )
    affected_sections: str = dspy.OutputField(
        desc="Comma-separated section names in SKILL.md that need edits."
    )
    improvement_direction: str = dspy.OutputField(
        desc="Action-oriented improvement direction (<=300 chars)."
    )


class SkillImprover(dspy.Signature):
    """Produce an improved SKILL.md.

    Keep the original purpose, name, and general structure. Prefer
    explaining WHY over adding rigid MUSTs. Do not overfit to a single
    trace — aim for a generalisable fix.
    """

    current_skill_content: str = dspy.InputField(desc="Current SKILL.md.")
    root_cause: str = dspy.InputField(desc="Root cause identified by the analyzer.")
    improvement_direction: str = dspy.InputField(desc="Improvement direction.")
    affected_sections: str = dspy.InputField(desc="Sections to edit.")

    improved_skill_content: str = dspy.OutputField(
        desc="Full improved SKILL.md (markdown with YAML frontmatter preserved)."
    )
    change_summary: str = dspy.OutputField(desc="Reviewer-facing summary (<=500 chars).")
    confidence_score: float = dspy.OutputField(desc="0.0-1.0 confidence in the change.")
