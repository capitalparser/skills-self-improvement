# skills-self-improvement

Out-of-band self-evolution system for Claude Code `SKILL.md` files.

The agent observes skill limitations during coding sessions (with zero LLM
cost — pure file I/O) and, after the session ends, a separate DSPy/GEPA loop
proposes improvements. Every proposal goes through validation gates and is
written to `.skill-evolution/reports/` for a human to review before applying.

- **In-session**: `observe` appends one line to `.skill-evolution/traces/{skill}.jsonl`.
- **Out-of-band**: `evolve` runs DSPy + GEPA with skill-creator's `evals.json` as the metric signal.
- **Human gate**: nothing mutates `SKILL.md`. Reviewers `cp` the improved content manually.

## Install

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
cp .env.example .env  # fill ANTHROPIC_API_KEY for Phase 1
```

On Claude Code on the web, skip `.env` and set `ANTHROPIC_API_KEY` as a
Codespaces secret. `.claude/hooks/session-start.sh` detects both.

## CLI

```bash
# Record an observation (no API cost)
uv run skill-evolution observe \
  --skill example-docx \
  --type undertrigger \
  --context "user asked '워드로 만들어줘'" \
  --reason "description lacks Korean triggers" \
  --hypothesis "add ko synonyms to description"

# Current state
uv run skill-evolution status

# Summarise raw traces (rule-based, no API cost)
uv run skill-evolution compress --all

# Run the evolution loop (requires ANTHROPIC_API_KEY)
uv run skill-evolution evolve --skill example-docx
```

`observe --type` must be one of: `undertrigger`, `overtrigger`,
`wrong_output`, `incomplete`, `missing_pattern`.

## Layout

```
skills/{name}/SKILL.md           # target skill (edited by humans only)
skills/{name}/evals/evals.json   # skill-creator format, metric signal
.skill-evolution/traces/         # append-only JSONL per skill
.skill-evolution/summaries/      # rule-based compression
.skill-evolution/reports/        # proposed diffs for human review
.skill-evolution/config.yaml     # overrides; defaults in src/skill_evolution/config.py
```

## How the evolve loop works

1. Load traces + `evals.json` + current `SKILL.md`.
2. Enforce minimums: ≥5 traces and ≥3 evals (configurable).
3. `SkillFailureAnalyzer` (DSPy ChainOfThought) identifies the root cause.
4. `SkillImprover` is compiled by `dspy.GEPA(auto="light", reflection_lm=...)`
   against the evals split 60/40 into train/val.
5. Three validation gates: size (≤500 lines), frontmatter integrity (name
   unchanged, description valid), description length drift (0.2x–3.0x).
6. `DiffReporter` writes `reports/{skill}-{timestamp}.md` with unified diff,
   gate results, confidence, and apply/reject instructions.

Reports are never applied automatically. Review, then `cp` the improved
content into `SKILL.md` and commit.

## Scope

- **In**: trace logging, rule-based compression, Anthropic-backed DSPy/GEPA
  loop, validation gates, diff reporting.
- **Out (future)**: local LLM parallel backend, agent auto-observation,
  LLM-based compression.

## Tests

```bash
uv run pytest
```
