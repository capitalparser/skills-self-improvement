---
name: skill-self-observation
description: Record an observation whenever another skill underperforms in a coding session — undertriggered, overtriggered, produced wrong output, was incomplete, or missed a pattern. Use this skill silently in the background; it costs zero tokens beyond the CLI call and feeds the out-of-band evolution loop.
---

# skill-self-observation

This skill teaches you to **notice when another skill fell short** in the
current session and write it down for the offline evolution loop.

## When to invoke

Trigger this skill the moment any of the following happens:

| Situation | Failure type |
|---|---|
| You realised a skill should have been triggered but wasn't (you ended up doing the task by hand) | `undertrigger` |
| A skill triggered for a request that didn't actually need it | `overtrigger` |
| A skill triggered and produced an output that the user rejected, corrected, or that you noticed was wrong | `wrong_output` |
| The output was on-track but missed an obvious step (e.g. forgot to save the file) | `incomplete` |
| You discovered a use case the skill clearly doesn't cover | `missing_pattern` |

If the user explicitly corrects you ("no, use python-docx, not docx2txt"),
that is almost always a `wrong_output` or `missing_pattern` event for
whatever skill (or absence of skill) led to the mistake.

## How to invoke

Run the `skill-evolution observe` CLI from the repo root. It appends one
JSON line to `.skill-evolution/traces/{skill}.jsonl` and exits. **No LLM
call happens inside the tool**, so calling it does not increase your
session's token usage beyond the bash overhead.

```bash
uv run skill-evolution observe \
  --skill <SKILL_NAME> \
  --type  <FAILURE_TYPE> \
  --context   "<one sentence: what the user asked / what you tried>" \
  --reason    "<one sentence: why the skill fell short>" \
  --hypothesis "<one sentence: what change to SKILL.md might fix it>"
```

`<SKILL_NAME>` is the directory name under `skills/`. If the failure was
that **no skill exists yet** for the use case, name a plausible new skill
(e.g. `pdf-form-fill`) and use `--type missing_pattern`.

## What to write

Each field should be **one concrete sentence**, not a paragraph. The
analyzer downstream prefers density over prose.

- `--context`: include the actual user phrasing if it's short. For Korean
  / non-English requests, include the original.
- `--reason`: name the specific gap. "description lacks Korean keywords"
  is good; "trigger failed" is not.
- `--hypothesis`: propose a concrete edit. "Add 워드, 문서 파일 to
  description" is good; "improve description" is not.

## What NOT to do

- Do **not** edit any `SKILL.md` directly — that's the human reviewer's
  job, post-`apply`.
- Do **not** invoke `skill-evolution evolve` mid-session. It is an
  out-of-band command that costs API credits and runs for minutes.
- Do **not** record observations for situations the user is happy with.
  Empty signal is worse than no signal — it dilutes the trace set.
- Do **not** try to be exhaustive. One tight observation per event is
  enough; the compressor and analyzer aggregate across sessions.

## Examples

User asked "워드 파일로 만들어줘" and the `example-docx` skill didn't trigger:

```bash
uv run skill-evolution observe \
  --skill example-docx --type undertrigger \
  --context "user said '워드 파일로 만들어줘'" \
  --reason "description has only English keywords (Word, .docx)" \
  --hypothesis "add 워드, 문서 파일, .docx to description"
```

The `xlsx` skill ran but generated a numbered list instead of bullets the
user asked for:

```bash
uv run skill-evolution observe \
  --skill xlsx --type wrong_output \
  --context "user asked for bullet list of Item 1/2/3" \
  --reason "skill defaults to numbered lists, no bullet branch" \
  --hypothesis "add explicit branch on 'bullet'/'•' in user prompt"
```

You realised there's no skill at all for filling PDF forms:

```bash
uv run skill-evolution observe \
  --skill pdf-form-fill --type missing_pattern \
  --context "user asked to populate W-9 PDF form fields" \
  --reason "no existing skill targets PDF AcroForm fields" \
  --hypothesis "create new skill using pypdf or pdfplumber"
```

## After the session

Nothing further is required from you in-session. The repo owner runs
`skill-evolution evolve --skill <name>` later to generate proposals, then
`skill-evolution apply` after review.
