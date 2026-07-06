"""The manual agentic investigation loop.

We use the manual loop (not the SDK tool runner) on purpose: the two disciplines
that define this project live in the loop itself —

  * BUDGET: cumulative input+output tokens are summed after every turn, and the
    loop refuses to start a new turn once cfg.token_budget is exceeded.
  * PROVENANCE: tool results (including the gate's rejections) are fed back so
    the model must ground every source note in a real fetch.

Notes are written to disk as the run proceeds (tools.write_wiki_note), so a run
that stops early on budget still leaves a partial, valid wiki behind.
"""

from __future__ import annotations

import json

from .config import Config
from .tools import TOOL_DEFS, ToolContext

SYSTEM = """\
You are ArcheoLogic, an AI archaeologist. You investigate a historical or
archaeological CLAIM by chasing it toward primary evidence and recording what you
find as a wiki of interlinked notes.

METHOD (non-negotiable):
1. PRIMARY vs ECHO. An excavation report or a dated laboratory analysis is
   primary evidence; a textbook, news article, or review repeating it is an echo.
   Ten echoes of one report are still one piece of evidence. Prefer primary
   sources and say so when a claim rests only on echoes.
2. CITOGENESIS. Watch for many sources that all trace back to a single root. If
   you see it, record it explicitly in the relevant note.
3. EVIDENCE, NOT MEMORY. You may only create a `source` note for a document you
   have actually fetched this run with fetch_document. The system will REJECT a
   source note that is not grounded in a fetch. If you recall a paper, fetch it
   first; if you cannot fetch it, do not create a source node for it.
4. CONTESTED STAYS CONTESTED. When scholars genuinely disagree, set the claim's
   status to `contested`, keep confidence near 0.5, and record BOTH the majority
   view and the strongest dissent. Do not pick a side the evidence does not
   support.
5. CALIBRATE. confidence is 0..1 and reflects the weight of evidence, not
   enthusiasm.

NOTE TYPES: claim (an assertion under investigation), source (a fetched
document), site (a place), scholar (a person who argues a position).
EDGES: supports, disputes, cites, mentions. Sources support/dispute claims;
claims cite sources and dispute rival claims; everything can mention sites and
scholars. Reference other notes in bodies with [[note-id]] wikilinks.

WORKFLOW: search_sources -> fetch_document (read it) -> extract the claims and
citations it makes -> write_wiki_note for the claim(s), the source(s) you
fetched, and the sites/scholars involved -> follow the citation trail with more
searches and fetches until it is exhausted or your budget runs low. Write notes
as you go, not all at the end. When you have a cited picture of the claim,
including its dissent, stop and give a one-paragraph summary.
"""


def _text_blocks(content) -> str:
    return "".join(b.text for b in content if getattr(b, "type", "") == "text")


def run(claim: str, claim_id: str, cfg: Config) -> dict:
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "anthropic SDK not installed. Run: pip install -r agent/requirements.txt"
        ) from e

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    ctx = ToolContext(cfg)
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    messages = [
        {
            "role": "user",
            "content": (
                f'Investigate this claim and build the wiki:\n\n"{claim}"\n\n'
                f"Use `{claim_id}` as the id of the root claim note. Begin by "
                f"searching for the primary literature, then fetch and read it."
            ),
        }
    ]

    tokens_used = 0
    stop = "completed"
    turn = 0

    while True:
        if turn >= cfg.max_iterations:
            stop = "max_iterations"
            break
        if tokens_used >= cfg.token_budget:
            stop = "budget_exhausted"
            break
        turn += 1

        try:
            resp = client.messages.create(
                model=cfg.model,
                max_tokens=cfg.max_tokens_per_turn,
                system=SYSTEM,
                tools=TOOL_DEFS,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": cfg.effort},
            )
        except anthropic.APIStatusError as e:  # pragma: no cover
            stop = f"api_error:{e.status_code}"
            print(f"[api error] {e.status_code}: {getattr(e, 'message', e)}")
            break

        tokens_used += resp.usage.input_tokens + resp.usage.output_tokens
        messages.append({"role": "assistant", "content": resp.content})

        say = _text_blocks(resp.content).strip()
        if say:
            print(f"\n[turn {turn} · {tokens_used:,} tok] {say}")

        if resp.stop_reason != "tool_use":
            stop = "completed"
            break

        tool_results = []
        for block in resp.content:
            if getattr(block, "type", "") != "tool_use":
                continue
            result, is_error = ctx.dispatch(block.name, dict(block.input))
            flag = " ERROR" if is_error else ""
            print(f"    → {block.name}({_brief(block.input)}){flag}")
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    ctx.close()
    summary = {
        "claim": claim,
        "claim_id": claim_id,
        "model": cfg.model,
        "stop_reason": stop,
        "turns": turn,
        "tokens_used": tokens_used,
        "token_budget": cfg.token_budget,
        **ctx.provenance(),
    }
    (cfg.run_dir / "run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _brief(inp) -> str:
    d = dict(inp)
    for k in ("query", "url", "id", "title"):
        if k in d:
            v = str(d[k])
            return f"{k}={v[:48]}"
    return ""
