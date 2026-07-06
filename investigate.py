#!/usr/bin/env python3
"""ArcheoLogic — investigation agent CLI (step 2).

Examples:
  # full investigation (needs ANTHROPIC_API_KEY)
  python investigate.py "Vergina Tomb II holds Philip II of Macedon"

  # name the root claim note and cap the budget
  python investigate.py "The Thera eruption dates to c. 1600 BCE" \\
      --claim-id claim-thera-high-chronology --budget 80000

  # prove the tool layer + anti-hallucination gate WITHOUT spending any tokens
  python investigate.py --self-test

After a run, view its wiki in the same graph UI as the hand-authored one:
  python tools/build_graph.py --wiki runs/latest/wiki --out web/public/graph.json
"""

from __future__ import annotations

import argparse
import sys

from agent.config import Config
from agent import wiki_io
from agent.tools import ToolContext


def self_test(cfg: Config) -> int:
    """Exercise the tools and the gate with no LLM calls (hits Crossref + one URL)."""
    print("=== ArcheoLogic tool-layer self-test (no LLM) ===")
    ctx = ToolContext(cfg)
    ok = True

    print("\n[1] search_sources …")
    out, err = ctx.dispatch("search_sources", {"query": "Vergina Tomb II Philip II", "rows": 3})
    print(out[:400]); ok &= not err

    print("\n[2] gate BEFORE fetch — expect REJECTED …")
    out, err = ctx.dispatch("write_wiki_note", {
        "id": "source-bogus", "type": "source", "title": "Ungrounded source",
        "status": "primary", "confidence": 0.9, "body": "should not be written",
        "url": "https://api.crossref.org/works/10.1073/pnas.1510906112",
    })
    print("   ", out.split("\n")[0])
    gate_ok = err and "REJECTED" in out
    print("    gate rejected ungrounded source:", "PASS" if gate_ok else "FAIL")
    ok &= gate_ok

    print("\n[3] fetch_document …")
    url = "https://api.crossref.org/works/10.1073/pnas.1510906112"
    out, err = ctx.dispatch("fetch_document", {"url": url})
    print("   ", out.split("\n")[0]); ok &= not err

    print("\n[4] gate AFTER fetch — expect accepted …")
    out, err = ctx.dispatch("write_wiki_note", {
        "id": "source-selftest", "type": "source",
        "title": "Bartsiokas et al. 2015 (self-test)", "status": "primary",
        "confidence": 0.9, "url": url, "authors": "Bartsiokas et al.", "year": 2015,
        "venue": "PNAS", "source_kind": "journal-article",
        "body": "Self-test note grounded in a fetched document.",
        "links": [{"to": "claim-tomb-i-philip-ii", "rel": "supports"}],
    })
    print("   ", out); grounded_ok = not err
    print("    grounded source accepted:", "PASS" if grounded_ok else "FAIL")
    ok &= grounded_ok

    ctx.close()
    print("\n=== self-test:", "PASS ===" if ok else "FAIL ===")
    print("wrote:", ", ".join(wiki_io.list_note_ids(cfg.out_dir)) or "(none)")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="ArcheoLogic investigation agent")
    p.add_argument("claim", nargs="?", help="the claim to investigate")
    p.add_argument("--claim-id", help="id for the root claim note (default: slug of claim)")
    p.add_argument("--budget", type=int, help="token budget for the run")
    p.add_argument("--max-iters", type=int, help="max turns")
    p.add_argument("--model", help="model id (default claude-opus-4-8)")
    p.add_argument("--run-id", help="run folder name under runs/ (default: latest)")
    p.add_argument("--self-test", action="store_true", help="test tools+gate, no LLM")
    args = p.parse_args()

    cfg = Config()
    if args.model: cfg.model = args.model
    if args.budget: cfg.token_budget = args.budget
    if args.max_iters: cfg.max_iterations = args.max_iters
    if args.run_id: cfg.run_id = args.run_id

    if args.self_test:
        return self_test(cfg)

    if not args.claim:
        p.error("provide a claim to investigate, or use --self-test")

    claim_id = args.claim_id or f"claim-{wiki_io.slugify(args.claim)[:48]}"
    from agent.loop import run  # imported late so --self-test needs no anthropic SDK

    print(f"investigating: {args.claim!r}")
    print(f"  model={cfg.model}  budget={cfg.token_budget:,} tok  out={cfg.out_dir}")
    summary = run(args.claim, claim_id, cfg)

    print("\n=== run complete ===")
    print(f"  stop: {summary['stop_reason']}  turns: {summary['turns']}"
          f"  tokens: {summary['tokens_used']:,}/{summary['token_budget']:,}")
    print(f"  fetched: {len(summary['fetched'])} docs"
          f"  · notes: {len(summary['notes_written'])}"
          f"  · gate rejections: {summary['gate_rejections']}")
    print(f"  view: python tools/build_graph.py --wiki {cfg.out_dir} "
          f"--out web/public/graph.json && (cd web && npm run dev)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
