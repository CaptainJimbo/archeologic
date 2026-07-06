"""Run configuration for the investigation agent.

Everything is overridable by environment variable so the same code runs locally
and in GitHub Actions without edits. Defaults are deliberately budget-conscious:
this is a demo agent whose whole point is disciplined, capped investigation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass
class Config:
    # Model. Defaults to the current most-capable Opus; override with ARCHEO_MODEL.
    model: str = os.environ.get("ARCHEO_MODEL", "claude-opus-4-8")
    effort: str = os.environ.get("ARCHEO_EFFORT", "medium")  # low|medium|high|max

    # --- the hard per-run budget, enforced by us in the loop -----------------
    # Cumulative (input + output) tokens across every turn of one investigation.
    # The loop refuses to start a new turn once this is exceeded. This is the
    # cost ceiling for a run; it is OUR accounting, not something we ask the
    # model to respect.
    token_budget: int = _env_int("ARCHEO_TOKEN_BUDGET", 150_000)
    max_iterations: int = _env_int("ARCHEO_MAX_ITERS", 24)
    max_fetches: int = _env_int("ARCHEO_MAX_FETCHES", 15)
    max_tokens_per_turn: int = _env_int("ARCHEO_MAX_TOKENS_TURN", 8_000)

    # HTTP
    request_timeout: float = float(os.environ.get("ARCHEO_HTTP_TIMEOUT", "30"))
    user_agent: str = os.environ.get(
        "ARCHEO_UA",
        "ArcheoLogic/0.2 (research prototype; +https://github.com/CaptainJimbo/archeologic)",
    )

    # --- output --------------------------------------------------------------
    # The agent writes to runs/<run_id>/, kept SEPARATE from the hand-authored
    # wiki/ so step-2 output can be diffed against the step-1 benchmark.
    run_id: str = os.environ.get("ARCHEO_RUN_ID", "latest")

    @property
    def run_dir(self) -> Path:
        return REPO / "runs" / self.run_id

    @property
    def out_dir(self) -> Path:
        return self.run_dir / "wiki"

    @property
    def corpus_dir(self) -> Path:
        return self.run_dir / "corpus"
