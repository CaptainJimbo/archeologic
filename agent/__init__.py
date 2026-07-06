"""ArcheoLogic investigation agent (step 2).

An agentic loop over the Claude API that investigates a claim, chases citations
to fetched documents, and writes interlinked wiki notes — under two disciplines
enforced in *our* code, not trusted to the model:

  * a per-run token budget (agent/loop.py), and
  * an anti-hallucination gate: a `source` note may only be written for a
    document actually fetched this run (agent/tools.py).
"""

__all__ = ["config", "wiki_io", "tools", "loop"]
