from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def _ensure_env_loaded(project_root: Path) -> None:
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)


def load_primary_lm(project_root: Path, backend_config: dict[str, Any]):
    """Load the primary DSPy LM (Anthropic).

    Imports dspy lazily so the Phase 0 CLI stays usable without dspy installed.
    """
    import dspy

    _ensure_env_loaded(project_root)
    anthropic_cfg = backend_config["anthropic"]
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Put it in .env or export it before running evolve."
        )

    return dspy.LM(
        model=f"anthropic/{anthropic_cfg['model']}",
        api_key=api_key,
        max_tokens=anthropic_cfg.get("max_tokens", 4096),
    )


def load_reflection_lm(project_root: Path, backend_config: dict[str, Any]):
    """GEPA's reflection_lm: same family, higher temperature works well.

    Kept as a separate function so that later a stronger/cheaper model can be
    swapped without touching the evolver.
    """
    import dspy

    _ensure_env_loaded(project_root)
    anthropic_cfg = backend_config["anthropic"]
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    return dspy.LM(
        model=f"anthropic/{anthropic_cfg['model']}",
        api_key=api_key,
        max_tokens=anthropic_cfg.get("max_tokens", 8192),
        temperature=1.0,
    )
