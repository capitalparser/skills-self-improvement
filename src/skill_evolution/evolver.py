from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from .compressor import TraceCompressor
from .config import Config
from .logger import TraceLogger
from .reporter import DiffReporter, EvolutionResult
from .validators import validate

console = Console()


class SkillEvolver:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = TraceLogger(config.traces_dir)
        self.compressor = TraceCompressor(config.summaries_dir)
        self.reporter = DiffReporter(config.reports_dir)

    def evolve(self, skill_name: str) -> Path | None:
        import dspy  # lazy

        from .backends import load_primary_lm, load_reflection_lm
        from .eval_runner import evals_to_trainset, load_evals, split_trainset
        from .metrics import skill_quality_metric
        from .signatures import SkillFailureAnalyzer, SkillImprover

        skill_path = self.config.skill_path(skill_name)
        if not skill_path.exists():
            console.print(f"[red]skill not found[/red]: {skill_path}")
            return None

        traces = self.logger.load(skill_name)
        evals = load_evals(self.config.evals_path(skill_name))

        min_traces = self.config.raw["evolution"]["min_traces_before_evolve"]
        min_evals = self.config.raw["evolution"]["min_evals_before_evolve"]
        if len(traces) < min_traces:
            console.print(
                f"[yellow]skipped[/yellow]: need {min_traces} traces, have {len(traces)}"
            )
            return None
        if len(evals) < min_evals:
            console.print(
                f"[yellow]skipped[/yellow]: need {min_evals} evals, have {len(evals)} "
                f"at {self.config.evals_path(skill_name).relative_to(self.config.project_root)}"
            )
            return None

        current_content = skill_path.read_text(encoding="utf-8")
        traces_jsonl = "\n".join(
            json.dumps(
                {
                    "failure_type": t.failure_type,
                    "trigger_context": t.trigger_context,
                    "failure_reason": t.failure_reason,
                    "hypothesis": t.hypothesis,
                },
                ensure_ascii=False,
            )
            for t in traces
        )
        summary = self.compressor.summarise(skill_name, traces)

        backend_cfg = self.config.raw["backends"]
        auto_budget = self.config.raw["evolution"]["auto"]
        train_split = self.config.raw["evolution"]["train_split"]

        lm = load_primary_lm(self.config.project_root, backend_cfg)
        reflection_lm = load_reflection_lm(self.config.project_root, backend_cfg)
        dspy.configure(lm=lm)

        console.print("[cyan]analyzing traces...[/cyan]")
        analyzer = dspy.ChainOfThought(SkillFailureAnalyzer)
        analysis = analyzer(
            current_skill_content=current_content,
            execution_traces=traces_jsonl,
            compressed_summary=summary,
        )

        trainset = evals_to_trainset(
            evals,
            current_skill_content=current_content,
            root_cause=analysis.root_cause,
            improvement_direction=analysis.improvement_direction,
            affected_sections=analysis.affected_sections,
        )
        train, val = split_trainset(trainset, train_split)

        console.print(
            f"[cyan]optimizing SkillImprover via GEPA[/cyan] "
            f"(auto={auto_budget}, train={len(train)}, val={len(val)})"
        )
        improver = dspy.ChainOfThought(SkillImprover)
        optimizer = dspy.GEPA(
            metric=skill_quality_metric,
            auto=auto_budget,
            reflection_lm=reflection_lm,
            track_stats=False,
        )
        optimized = optimizer.compile(improver, trainset=train, valset=val)

        console.print("[cyan]running optimized improver...[/cyan]")
        result = optimized(
            current_skill_content=current_content,
            root_cause=analysis.root_cause,
            improvement_direction=analysis.improvement_direction,
            affected_sections=analysis.affected_sections,
        )

        try:
            confidence = float(getattr(result, "confidence_score", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        constraints = self.config.raw["constraints"]
        validation = validate(
            current_content,
            result.improved_skill_content,
            max_lines=constraints["max_skill_lines"],
            description_ratio_min=constraints["description_ratio_min"],
            description_ratio_max=constraints["description_ratio_max"],
        )

        evolution = EvolutionResult(
            skill_name=skill_name,
            original_content=current_content,
            improved_content=result.improved_skill_content,
            root_cause=str(analysis.root_cause),
            change_summary=str(result.change_summary),
            confidence=confidence,
            backend="anthropic",
            validation=validation,
        )

        if not validation.passed:
            console.print(
                f"[red]validation failed[/red] at gate "
                f"'{validation.failed_gate}' — report written anyway for review"
            )

        return self.reporter.write(evolution, skill_path)
