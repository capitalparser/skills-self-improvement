# skills-self-improvement

> 한국어 문서: [README.ko.md](README.ko.md)

An **out-of-band self-evolution system** for Claude Code `SKILL.md` files.

The agent observes skill limitations during a coding session (with **zero LLM
cost** — pure file I/O), and after the session ends a separate DSPy/GEPA loop
proposes improvements. Every proposal passes through validation gates and is
written to `.skill-evolution/reports/` for a human to review before applying.

```
┌─────────── in-session (no tokens) ───────────┐   ┌──── out-of-band ────┐
│                                              │   │                     │
│  agent detects skill limit                   │   │  evolve CLI         │
│         │                                    │   │    │                │
│         ▼                                    │   │    ▼                │
│  observe → .skill-evolution/traces/*.jsonl   │   │  DSPy / GEPA        │
│                                              │   │    │                │
└──────────────────────────────────────────────┘   │    ▼                │
                                                   │  validation gates   │
                                                   │    │                │
                                                   │    ▼                │
                                                   │  reports/*.md       │
                                                   │  ↓ human review ↓   │
                                                   └─────────────────────┘
```

- **In-session**: `observe` appends one JSON line. No API calls.
- **Out-of-band**: `evolve` runs DSPy `ChainOfThought` + `GEPA` optimizer, using
  skill-creator's `evals.json` as the metric signal.
- **Human gate**: nothing mutates `SKILL.md` automatically. After review,
  `apply` swaps the file in and archives the report.

---

## Requirements

| Tool / Service | Version | Notes |
|---|---|---|
| Python | ≥ 3.11 | 3.12 works too |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.4 | Package + virtualenv manager |
| Git | any recent | |
| Anthropic API key | — | Only required for `evolve` (Phase 1). Not needed for observe/status/compress. |

---

## Installation

### 1. Install `uv`

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Confirm:

```bash
uv --version
```

### 2. Clone the repository

```bash
git clone https://github.com/capitalparser/skills-self-improvement.git
cd skills-self-improvement
```

### 3. Install dependencies

```bash
uv sync --extra dev
```

This creates `.venv/` and installs:

- `dspy-ai` (ChainOfThought + GEPA optimizer)
- `anthropic` (API SDK)
- `typer` + `rich` (CLI)
- `python-dotenv`, `pyyaml`
- `pytest`, `pytest-cov` (dev)

### 4. Configure the Anthropic API key

Required only when you run `evolve`. Two options:

**Option A — `.env` file (local development, recommended):**

```bash
cp .env.example .env
# edit .env and set:
# ANTHROPIC_API_KEY=sk-ant-...
```

`.env` is in `.gitignore` and will never be committed.

**Option B — environment variable (CI, Codespaces, Claude Code on the web):**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

On Claude Code on the web, set it as a Codespaces secret. The SessionStart
hook (`.claude/hooks/session-start.sh`) prints whether the key is detected
at the start of every session.

Get a key at <https://console.anthropic.com/>. Pricing for `evolve` depends
on GEPA budget (`auto: light` ≈ low). Phase 0 commands are free.

### 5. Verify the installation

```bash
uv run skill-evolution --help
uv run pytest
```

20 tests should pass.

### 6. First end-to-end smoke

```bash
# record observations (no API cost)
uv run skill-evolution observe \
  --skill example-docx --type undertrigger \
  --context "user said 'make a word doc'" \
  --reason "description lacks Korean triggers" \
  --hypothesis "add ko synonyms to description"

uv run skill-evolution status
uv run skill-evolution compress --all

# run evolve once you have ≥5 traces and ≥3 evals and ANTHROPIC_API_KEY set
uv run skill-evolution evolve --skill example-docx
```

---

## CLI reference

```bash
uv run skill-evolution <command> [options]
```

### `observe` — record a single observation

Append a JSON line to `.skill-evolution/traces/{skill}.jsonl`. No LLM calls.

```bash
uv run skill-evolution observe \
  --skill SKILL_NAME \
  --type   FAILURE_TYPE \
  --context   "what the user asked" \
  --reason    "why the skill fell short" \
  --hypothesis "proposed improvement direction" \
  [--session-id SESSION_ID] \
  [--project-root PATH]
```

`--type` must be one of:

| Type | Meaning |
|---|---|
| `undertrigger` | Skill should have triggered but didn't. |
| `overtrigger` | Skill triggered but shouldn't have. |
| `wrong_output` | Skill triggered, but produced wrong result. |
| `incomplete` | Result is correct but missing important steps. |
| `missing_pattern` | Skill doesn't cover a newly observed pattern. |

### `status` — show per-skill state

```bash
uv run skill-evolution status
```

Displays a table with trace count, pending report count, and whether the
minimum threshold for `evolve` is met.

### `compress` — rule-based summary of raw traces

```bash
uv run skill-evolution compress --skill SKILL_NAME
uv run skill-evolution compress --all
```

Writes `.skill-evolution/summaries/{skill}.md` with failure-type counts,
recurring hypotheses, and recent examples. No LLM calls.

### `evolve` — run the out-of-band evolution loop (Phase 1)

```bash
uv run skill-evolution evolve --skill SKILL_NAME
```

Requires `ANTHROPIC_API_KEY`. Writes two sibling files:

- `.skill-evolution/reports/{skill}-{ts}.md` — human-readable report (diff,
  gate results, root cause, confidence).
- `.skill-evolution/reports/{skill}-{ts}.proposed.md` — the full improved
  SKILL.md, ready to be copied verbatim by `apply`.

Behaviour:

1. Loads traces + `evals.json` + current `SKILL.md`.
2. Enforces minimums (configurable): ≥5 traces and ≥3 evals.
3. Runs `SkillFailureAnalyzer` (ChainOfThought) to identify the root cause.
4. Compiles `SkillImprover` via `dspy.GEPA(auto="light", reflection_lm=...)`
   against a 60/40 train/val split of the evals.
5. Applies three validation gates. If any fails, the report is still written
   but marked as `FAILED at {gate}`.
6. Writes the proposal report and sidecar.

### `apply` — accept a proposal (Human Gate)

```bash
# explicit: apply a specific report
uv run skill-evolution apply --report .skill-evolution/reports/<skill>-<ts>.md

# implicit: apply the most recent unapplied report for a skill
uv run skill-evolution apply --skill SKILL_NAME
```

Behaviour:

1. Reads `{skill}-{ts}.proposed.md` (the full improved SKILL.md).
2. Overwrites `skills/{skill}/SKILL.md`.
3. Moves both files to `.skill-evolution/reports/applied/`.
4. Prints a suggested `git add && git commit` command.

To reject a proposal instead, just delete both files:

```bash
rm .skill-evolution/reports/<skill>-<ts>.md \
   .skill-evolution/reports/<skill>-<ts>.proposed.md
```

---

## Repository layout

```
skills-self-improvement/
├── pyproject.toml                    uv project + deps
├── .env.example                      template for ANTHROPIC_API_KEY
├── .gitignore
├── README.md                         English
├── README.ko.md                      Korean
│
├── .claude/
│   ├── hooks/session-start.sh        auto-runs uv sync, prints API key status
│   └── settings.json                 registers the hook
│
├── skills/                           target skills (edited by humans only)
│   └── example-docx/
│       ├── SKILL.md
│       └── evals/evals.json          skill-creator format → metric signal
│
├── src/skill_evolution/
│   ├── __init__.py
│   ├── config.py                     defaults + YAML merge
│   ├── logger.py                     TraceLogger (file I/O, no LLM)
│   ├── compressor.py                 rule-based summaries
│   ├── validators.py                 size / frontmatter / drift gates
│   ├── reporter.py                   DiffReporter (unified diff → markdown)
│   ├── backends.py                   Anthropic LM loader (DSPy)
│   ├── signatures.py                 DSPy Signatures (analyzer, improver)
│   ├── metrics.py                    GEPA-compatible assertion metric
│   ├── eval_runner.py                evals.json → dspy.Example trainset
│   ├── evolver.py                    orchestration (analyze → GEPA → validate → report)
│   └── cli.py                        typer CLI (observe/status/compress/evolve)
│
├── tests/                            pytest (20 tests)
│
└── .skill-evolution/                 runtime data (gitignored except *.example)
    ├── config.yaml.example
    ├── traces/{skill}.jsonl                 append-only observations
    ├── summaries/{skill}.md                 rule-based compression
    ├── reports/{skill}-{ts}.md              proposed diff + metadata
    ├── reports/{skill}-{ts}.proposed.md     full improved SKILL.md
    └── reports/applied/                     archived after `apply`
```

---

## Configuration

Defaults live in `src/skill_evolution/config.py`. To override, copy the
example:

```bash
mkdir -p .skill-evolution
cp .skill-evolution/config.yaml.example .skill-evolution/config.yaml
```

Then edit `.skill-evolution/config.yaml`:

```yaml
backends:
  primary: anthropic
  anthropic:
    model: claude-sonnet-4-6
    max_tokens: 4096

evolution:
  auto: light              # GEPA budget: light | medium | heavy
  min_traces_before_evolve: 5
  min_evals_before_evolve: 3
  train_split: 0.6         # skill-creator's 60/40 convention

constraints:
  max_skill_lines: 500
  description_ratio_min: 0.2
  description_ratio_max: 3.0

paths:
  skills_dir: skills
  runtime_dir: .skill-evolution
```

Overrides merge deeply: keys not set in your YAML keep their defaults.

---

## Adding a new skill for evolution

1. Create `skills/<name>/SKILL.md` with YAML frontmatter:

   ```markdown
   ---
   name: my-skill
   description: What this skill does and when to use it.
   ---

   # my-skill

   ...
   ```

2. Add `skills/<name>/evals/evals.json` following the
   [skill-creator format](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md):

   ```json
   {
     "skill_name": "my-skill",
     "evals": [
       {
         "id": 1,
         "prompt": "User's task prompt",
         "expected_output": "Description of expected result",
         "assertions": [
           "The response includes 'some string'",
           "The response calls some function"
         ]
       }
     ]
   }
   ```

3. Record real observations with `observe` whenever the skill falls short.

4. Once you have ≥5 traces and ≥3 evals, run `evolve`.

---

## How the validation gates work

Any proposal must pass **all three gates**, in order:

| Gate | What it checks |
|---|---|
| `size` | Improved SKILL.md is ≤ `max_skill_lines` (default 500, matches skill-creator). |
| `frontmatter` | YAML frontmatter parses. `name` is unchanged. `description` is non-empty. |
| `description_drift` | New description length is within `[ratio_min, ratio_max]` × original (default 0.2x–3.0x). |

If a gate fails, the report is still written for transparency but flagged
`FAILED at {gate_name}` in the header, so a reviewer can see both the
rejected proposal and why.

---

## Troubleshooting

**`ANTHROPIC_API_KEY is not set`**
- Check `cat .env | grep ANTHROPIC_API_KEY` (local) or `echo $ANTHROPIC_API_KEY` (shell).
- The SessionStart hook prints the status each session — look at the startup log.

**`skipped: need 5 traces, have 2`**
- Add more observations with `observe`. Or lower `min_traces_before_evolve`
  in `.skill-evolution/config.yaml`.

**`skipped: need 3 evals, have 0`**
- Create `skills/<name>/evals/evals.json` first.

**Tests fail after pulling updates**
- Re-sync: `uv sync --extra dev`.

**uv not found**
- Re-run the install command in [§Installation](#installation) and ensure
  `~/.local/bin` is in `$PATH`.

**GEPA runs are expensive**
- The `auto: light` setting keeps the budget modest. For initial runs,
  stick with `light`.

---

## Scope

**In scope (MVP):**
- In-session trace logging (zero tokens)
- Rule-based trace compression
- Anthropic-backed DSPy/GEPA evolution loop
- Three-gate validation
- Human-gated diff reports

**Out of scope (future):**
- Local LLM (Ollama / OpenAI-compatible) parallel backend — Phase 2
- Agent auto-observation integration — Phase 3
- LLM-based compression — Phase 4

---

## License

See the repository for licensing details.

## References

- [Anthropic Skills — skill-creator SKILL.md](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)
- [DSPy GEPA Overview](https://dspy.ai/api/optimizers/GEPA/overview/)
- [DSPy Language Models](https://dspy.ai/learn/programming/language_models/)
