# skills-self-improvement

> English: [README.md](README.md)

Claude Code `SKILL.md` 파일을 **대역 외(out-of-band)로 스스로 진화**시키는 시스템.

에이전트는 코딩 세션 중 skill의 한계를 감지해 **토큰 0으로**(순수 파일 I/O) 관찰만 기록하고, 세션 종료 후 별도 DSPy/GEPA 루프가 개선안을 생성한다. 모든 개선안은 검증 게이트를 통과한 뒤 `.skill-evolution/reports/`에 기록되며, **사람이 검토하고 수동 반영**한다.

```
┌────── 세션 중 (토큰 0) ──────┐     ┌──── 세션 종료 후 ────┐
│                              │     │                       │
│  에이전트가 skill 한계 감지  │     │  evolve CLI           │
│         │                    │     │    │                  │
│         ▼                    │     │    ▼                  │
│  observe                     │     │  DSPy / GEPA          │
│   → traces/*.jsonl           │     │    │                  │
│                              │     │    ▼                  │
└──────────────────────────────┘     │  검증 게이트 (3단계)   │
                                     │    │                  │
                                     │    ▼                  │
                                     │  reports/*.md         │
                                     │  ↓ 사람 검토 후 반영 ↓ │
                                     └───────────────────────┘
```

- **세션 중**: `observe`가 JSON 한 줄만 추가. API 호출 없음.
- **세션 후**: `evolve`가 DSPy `ChainOfThought` + `GEPA` 옵티마이저 실행. 점수 신호는 skill-creator의 `evals.json`에서 얻음.
- **Human Gate**: 자동으로 `SKILL.md`를 수정하지 않음. 사람이 검토 후 직접 `cp`하고 커밋.

---

## 요구사항

| 도구 / 서비스 | 버전 | 비고 |
|---|---|---|
| Python | ≥ 3.11 | 3.12도 가능 |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.4 | 패키지 + 가상환경 관리자 |
| Git | 최근 버전 | |
| Anthropic API 키 | — | **`evolve`(Phase 1) 전용**. observe/status/compress에는 불필요. |

---

## 설치

### 1. `uv` 설치

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

설치 확인:

```bash
uv --version
```

### 2. 저장소 클론

```bash
git clone https://github.com/capitalparser/skills-self-improvement.git
cd skills-self-improvement
```

### 3. 의존성 설치

```bash
uv sync --extra dev
```

`.venv/` 생성 + 아래 패키지 설치:

- `dspy-ai` (ChainOfThought + GEPA 옵티마이저)
- `anthropic` (API SDK)
- `typer` + `rich` (CLI)
- `python-dotenv`, `pyyaml`
- `pytest`, `pytest-cov` (개발)

### 4. Anthropic API 키 설정

`evolve` 실행 시에만 필요. 두 가지 방법:

**방법 A — `.env` 파일 (로컬 개발 권장):**

```bash
cp .env.example .env
# .env 편집 후:
# ANTHROPIC_API_KEY=sk-ant-...
```

`.env`는 `.gitignore`에 포함되어 있어 커밋되지 않는다.

**방법 B — 환경변수 (CI, Codespaces, Claude Code on the web):**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Claude Code on the web에서는 Codespaces secret으로 등록하면 된다. SessionStart 훅(`.claude/hooks/session-start.sh`)이 매 세션 시작 시 키 감지 상태를 출력한다.

API 키 발급: <https://console.anthropic.com/>. `evolve` 비용은 GEPA 예산(`auto: light`는 낮음) 기준이며, Phase 0 명령들은 모두 무료.

### 5. 설치 확인

```bash
uv run skill-evolution --help
uv run pytest
```

테스트 20개가 모두 통과해야 한다.

### 6. 최초 동작 확인 (end-to-end)

```bash
# 관찰 기록 (API 비용 0)
uv run skill-evolution observe \
  --skill example-docx --type undertrigger \
  --context "사용자가 '워드로 만들어줘'라고 요청" \
  --reason "description에 한국어 키워드 없음" \
  --hypothesis "description에 한국어 표현 추가"

uv run skill-evolution status
uv run skill-evolution compress --all

# trace 5건 + eval 3건 + ANTHROPIC_API_KEY 갖춰진 뒤 실행
uv run skill-evolution evolve --skill example-docx
```

---

## CLI 레퍼런스

```bash
uv run skill-evolution <명령어> [옵션]
```

### `observe` — 관찰 한 건 기록

`.skill-evolution/traces/{skill}.jsonl`에 JSON 한 줄 append. LLM 호출 없음.

```bash
uv run skill-evolution observe \
  --skill SKILL_NAME \
  --type   FAILURE_TYPE \
  --context   "사용자가 요청한 내용" \
  --reason    "skill이 실패한 이유" \
  --hypothesis "개선 방향 가설" \
  [--session-id SESSION_ID] \
  [--project-root PATH]
```

`--type`은 다음 중 하나:

| 값 | 의미 |
|---|---|
| `undertrigger` | 호출됐어야 하는데 skill이 트리거되지 않음 |
| `overtrigger` | 트리거되지 말았어야 하는데 트리거됨 |
| `wrong_output` | 트리거는 됐으나 잘못된 결과 생성 |
| `incomplete` | 결과는 맞으나 중요 단계 누락 |
| `missing_pattern` | skill이 다루지 않는 새로운 패턴 발견 |

### `status` — skill별 현황 조회

```bash
uv run skill-evolution status
```

trace 개수, 대기 중인 리포트 수, `evolve` 최소 조건 충족 여부를 표로 출력.

### `compress` — trace 규칙 기반 요약

```bash
uv run skill-evolution compress --skill SKILL_NAME
uv run skill-evolution compress --all
```

`.skill-evolution/summaries/{skill}.md`에 failure_type 분포, 반복 가설, 최근 예시 기록. LLM 호출 없음.

### `evolve` — 진화 루프 실행 (Phase 1)

```bash
uv run skill-evolution evolve --skill SKILL_NAME
```

`ANTHROPIC_API_KEY` 필요. 결과는 `.skill-evolution/reports/{skill}-{ts}.md`.

동작 흐름:

1. traces + `evals.json` + 현재 `SKILL.md` 로드.
2. 최소 조건 검사 (기본값 설정): trace ≥ 5, eval ≥ 3.
3. `SkillFailureAnalyzer`(ChainOfThought)로 root_cause 파악.
4. `SkillImprover`를 `dspy.GEPA(auto="light", reflection_lm=...)`로 컴파일 (evals 60/40 train/val 분할).
5. 검증 게이트 3개 적용. 실패 시에도 리포트는 작성되고 `FAILED at {gate}` 표시.
6. unified diff 포함 리포트 기록.

---

## 저장소 구조

```
skills-self-improvement/
├── pyproject.toml                    uv 프로젝트 + 의존성
├── .env.example                      ANTHROPIC_API_KEY 템플릿
├── .gitignore
├── README.md                         영문
├── README.ko.md                      한글
│
├── .claude/
│   ├── hooks/session-start.sh        uv sync 자동 실행 + 키 상태 출력
│   └── settings.json                 훅 등록
│
├── skills/                           진화 대상 skill들 (사람만 편집)
│   └── example-docx/
│       ├── SKILL.md
│       └── evals/evals.json          skill-creator 포맷 → metric 신호
│
├── src/skill_evolution/
│   ├── __init__.py
│   ├── config.py                     기본값 + YAML 병합
│   ├── logger.py                     TraceLogger (파일 I/O, LLM 없음)
│   ├── compressor.py                 규칙 기반 요약
│   ├── validators.py                 size / frontmatter / drift 게이트
│   ├── reporter.py                   DiffReporter (unified diff → markdown)
│   ├── backends.py                   Anthropic LM 로더 (DSPy)
│   ├── signatures.py                 DSPy Signature (analyzer, improver)
│   ├── metrics.py                    GEPA 호환 assertion metric
│   ├── eval_runner.py                evals.json → dspy.Example trainset
│   ├── evolver.py                    오케스트레이션 (분석 → GEPA → 검증 → 리포트)
│   └── cli.py                        typer CLI (observe/status/compress/evolve)
│
├── tests/                            pytest (20개 테스트)
│
└── .skill-evolution/                 런타임 데이터 (*.example 외엔 gitignore)
    ├── config.yaml.example
    ├── traces/{skill}.jsonl          관찰 기록 (append-only)
    ├── summaries/{skill}.md          규칙 기반 요약
    └── reports/{skill}-{ts}.md       개선안 리포트
```

---

## 설정

기본값은 `src/skill_evolution/config.py`에 있음. 오버라이드하려면 예시 파일을 복사:

```bash
mkdir -p .skill-evolution
cp .skill-evolution/config.yaml.example .skill-evolution/config.yaml
```

`.skill-evolution/config.yaml`에서 수정:

```yaml
backends:
  primary: anthropic
  anthropic:
    model: claude-sonnet-4-6
    max_tokens: 4096

evolution:
  auto: light              # GEPA 예산: light | medium | heavy
  min_traces_before_evolve: 5
  min_evals_before_evolve: 3
  train_split: 0.6         # skill-creator 60/40 관례

constraints:
  max_skill_lines: 500
  description_ratio_min: 0.2
  description_ratio_max: 3.0

paths:
  skills_dir: skills
  runtime_dir: .skill-evolution
```

오버라이드는 깊이 병합(deep merge)된다. YAML에 지정하지 않은 키는 기본값 유지.

---

## 새 skill 등록 방법

1. `skills/<name>/SKILL.md` 생성. YAML frontmatter 필수:

   ```markdown
   ---
   name: my-skill
   description: 이 skill이 무엇을 하는지, 언제 쓸지.
   ---

   # my-skill

   ...
   ```

2. `skills/<name>/evals/evals.json` 작성 — [skill-creator 포맷](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md):

   ```json
   {
     "skill_name": "my-skill",
     "evals": [
       {
         "id": 1,
         "prompt": "사용자 요청 프롬프트",
         "expected_output": "기대 결과 설명",
         "assertions": [
           "응답에 '특정 문자열' 포함",
           "응답이 특정 함수 호출"
         ]
       }
     ]
   }
   ```

3. skill이 기대에 못 미칠 때마다 `observe`로 관찰 기록.

4. trace ≥ 5, eval ≥ 3 누적되면 `evolve` 실행.

---

## 검증 게이트 동작

개선안은 **세 게이트를 모두 통과**해야 유효:

| 게이트 | 검사 내용 |
|---|---|
| `size` | 개선된 SKILL.md가 `max_skill_lines` 이하 (기본 500줄, skill-creator 기준) |
| `frontmatter` | YAML frontmatter 파싱 가능, `name` 불변, `description` 비어있지 않음 |
| `description_drift` | description 길이가 `[ratio_min, ratio_max]` × 원본 범위 (기본 0.2x–3.0x) |

게이트 실패 시에도 리포트는 작성되지만 헤더에 `FAILED at {gate_name}`으로 표시되어 리뷰어가 거부된 개선안과 그 이유를 동시에 확인 가능.

---

## 트러블슈팅

**`ANTHROPIC_API_KEY is not set`**
- `.env` 확인: `cat .env | grep ANTHROPIC_API_KEY`
- 환경변수 확인: `echo $ANTHROPIC_API_KEY`
- SessionStart 훅이 매 세션 시작 시 키 감지 상태를 출력하니 로그 확인.

**`skipped: need 5 traces, have 2`**
- `observe`로 관찰을 더 추가. 또는 `.skill-evolution/config.yaml`에서 `min_traces_before_evolve` 낮춤.

**`skipped: need 3 evals, have 0`**
- `skills/<name>/evals/evals.json` 먼저 작성.

**업데이트 후 테스트 실패**
- 재설치: `uv sync --extra dev`.

**uv 명령을 찾을 수 없음**
- [§설치](#설치)의 설치 명령 재실행 + `~/.local/bin`이 `$PATH`에 있는지 확인.

**GEPA 실행 비용이 부담**
- 기본값 `auto: light`가 예산을 가장 낮게 유지. 초기에는 그대로 사용 권장.

---

## 범위

**MVP 포함:**
- 세션 중 trace 기록 (토큰 0)
- 규칙 기반 trace 압축
- Anthropic 기반 DSPy/GEPA 진화 루프
- 3단계 검증 게이트
- Human Gate diff 리포트

**범위 밖 (향후 Phase):**
- 로컬 LLM(Ollama / OpenAI 호환) 병행 백엔드 — Phase 2
- 에이전트 자동 관찰 통합 — Phase 3
- LLM 기반 압축 — Phase 4

---

## 라이선스

저장소 참조.

## 레퍼런스

- [Anthropic Skills — skill-creator SKILL.md](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)
- [DSPy GEPA Overview](https://dspy.ai/api/optimizers/GEPA/overview/)
- [DSPy Language Models](https://dspy.ai/learn/programming/language_models/)
