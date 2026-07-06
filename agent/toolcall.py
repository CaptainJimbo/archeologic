"""Run a single agent tool call from the command line.

This exposes the real tool layer (agent/tools.py) one call at a time, so an
external driver — a human, a script, or a subagent standing in for the model —
can perform an investigation step by step while the anti-hallucination gate and
provenance ledger are enforced across calls (the ledger persists to disk).

Usage:
    PYTHONPATH=. python -m agent.toolcall <tool_name> '<json-args>'

Examples:
    python -m agent.toolcall search_sources '{"query": "Thera eruption Minoan collapse", "rows": 5}'
    python -m agent.toolcall fetch_document '{"url": "https://..."}'
    python -m agent.toolcall write_wiki_note '{"id": "...", "type": "claim", ...}'

Exit code is non-zero if the tool returned an error (e.g. the gate rejected a
source note), so callers can detect failures.
"""

from __future__ import annotations

import json
import sys

from .config import Config
from .tools import ToolContext


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m agent.toolcall <tool_name> '<json-args>'", file=sys.stderr)
        return 2
    name = sys.argv[1]
    # args come from: '@path' (read file), literal JSON argv, or stdin if piped.
    raw = "{}"
    if len(sys.argv) > 2:
        raw = sys.argv[2]
        if raw.startswith("@"):
            with open(raw[1:], encoding="utf-8") as f:
                raw = f.read()
    elif not sys.stdin.isatty():
        raw = sys.stdin.read() or "{}"
    try:
        args = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"bad JSON args: {e}", file=sys.stderr)
        return 2

    ctx = ToolContext(Config())
    result, is_error = ctx.dispatch(name, args)
    ctx.close()
    print(result)
    return 1 if is_error else 0


if __name__ == "__main__":
    sys.exit(main())
