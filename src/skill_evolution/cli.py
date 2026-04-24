from __future__ import annotations

import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .compressor import TraceCompressor
from .config import ensure_runtime_dirs, load_config
from .logger import ALLOWED_FAILURE_TYPES, TraceEntry, TraceLogger

app = typer.Typer(help="Skill Self-Evolution CLI")
console = Console()


def _config(project_root: Path | None):
    root = (project_root or Path.cwd()).resolve()
    config = load_config(root)
    ensure_runtime_dirs(config)
    return config


@app.command()
def observe(
    skill: str = typer.Option(..., help="Target skill name (directory under skills/)"),
    type: str = typer.Option(  # noqa: A002 - CLI naming matches plan
        ...,
        "--type",
        help=f"Failure type, one of: {', '.join(sorted(ALLOWED_FAILURE_TYPES))}",
    ),
    context: str = typer.Option(..., help="What user request triggered the skill call"),
    reason: str = typer.Option(..., help="Why the skill fell short"),
    hypothesis: str = typer.Option(..., help="Proposed improvement direction"),
    session_id: str = typer.Option("", help="Optional session identifier"),
    project_root: Path | None = typer.Option(None, help="Project root (defaults to CWD)"),
) -> None:
    """Append a single observation to the skill's trace log."""
    config = _config(project_root)
    logger = TraceLogger(config.traces_dir)
    entry = TraceEntry(
        skill_name=skill,
        trigger_context=context,
        failure_type=type,
        failure_reason=reason,
        hypothesis=hypothesis,
        session_id=session_id or f"session_{uuid.uuid4().hex[:8]}",
    )
    path = logger.append(entry)
    console.print(f"[green]ok[/green] appended to {path.relative_to(config.project_root)}")


@app.command()
def status(
    project_root: Path | None = typer.Option(None, help="Project root (defaults to CWD)"),
) -> None:
    """Show how many traces and pending reports exist per skill."""
    config = _config(project_root)
    logger = TraceLogger(config.traces_dir)

    table = Table(title="Skill evolution status")
    table.add_column("skill")
    table.add_column("traces", justify="right")
    table.add_column("pending reports", justify="right")
    table.add_column("min met?", justify="center")

    min_traces = config.raw["evolution"]["min_traces_before_evolve"]
    pending_reports: dict[str, int] = {}
    if config.reports_dir.exists():
        for report in config.reports_dir.glob("*.md"):
            skill_name = report.stem.rsplit("-", 1)[0]
            pending_reports[skill_name] = pending_reports.get(skill_name, 0) + 1

    skills = set(logger.skills_with_traces()) | set(pending_reports.keys())
    if not skills:
        console.print("[yellow]no traces or reports yet[/yellow]")
        return

    for skill_name in sorted(skills):
        traces = logger.load(skill_name)
        met = "yes" if len(traces) >= min_traces else "no"
        table.add_row(
            skill_name,
            str(len(traces)),
            str(pending_reports.get(skill_name, 0)),
            met,
        )
    console.print(table)


@app.command()
def compress(
    skill: str | None = typer.Option(None, help="Skill name (omit for --all)"),
    all_skills: bool = typer.Option(False, "--all", help="Compress every skill with traces"),
    project_root: Path | None = typer.Option(None, help="Project root (defaults to CWD)"),
) -> None:
    """Write rule-based summaries from raw traces."""
    config = _config(project_root)
    logger = TraceLogger(config.traces_dir)
    compressor = TraceCompressor(config.summaries_dir)

    targets: list[str]
    if all_skills:
        targets = logger.skills_with_traces()
    elif skill:
        targets = [skill]
    else:
        raise typer.BadParameter("provide --skill NAME or --all")

    for name in targets:
        traces = logger.load(name)
        if not traces:
            console.print(f"[yellow]{name}[/yellow]: no traces, skipped")
            continue
        path = compressor.write(name, traces)
        console.print(
            f"[green]ok[/green] {name}: {len(traces)} traces -> "
            f"{path.relative_to(config.project_root)}"
        )


@app.command()
def evolve(
    skill: str = typer.Option(..., help="Target skill name"),
    project_root: Path | None = typer.Option(None, help="Project root (defaults to CWD)"),
) -> None:
    """Run the out-of-band evolution loop for a skill (Phase 1).

    Requires ANTHROPIC_API_KEY in environment or .env file.
    """
    from .evolver import SkillEvolver  # lazy import keeps Phase 0 CLI dspy-free

    config = _config(project_root)
    evolver = SkillEvolver(config)
    report_path = evolver.evolve(skill)
    if report_path is None:
        console.print("[yellow]no report produced[/yellow] (see messages above)")
        raise typer.Exit(code=1)
    console.print(f"[green]report written[/green] {report_path.relative_to(config.project_root)}")


if __name__ == "__main__":
    app()
