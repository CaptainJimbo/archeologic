# The investigation agent (step 2)

Given a **claim**, this agent searches the scholarly literature, fetches and reads
sources, chases the citation trail, and writes interlinked wiki notes — under two
disciplines enforced in **our** code, not trusted to the model.

```
python investigate.py "Vergina Tomb II holds Philip II of Macedon"
```

It writes to `runs/<run-id>/wiki/` — deliberately **separate** from the
hand-authored `wiki/`, so its output can be diffed against the step-1 benchmark.

## The two disciplines (why this isn't just "LLM + search")

**1. A per-run token budget.** `agent/loop.py` sums `input + output` tokens after
every turn and refuses to start a new turn once `token_budget` is exceeded. It is
*our* accounting in a plain manual loop — not something the model is asked to
respect. A run that stops early on budget still leaves a valid, partial wiki
behind, because notes are written as the run proceeds.

**2. An anti-hallucination gate.** The cardinal sin in this domain is a
plausible-looking citation to a paper that was never read. So `write_wiki_note`
**rejects** any `source` note whose URL (or `fetch_id`) was not actually fetched
this run (`agent/tools.py` → the gate). The rejection is returned to the model as
a tool error, so it must go and `fetch_document` before it can cite. Source nodes
are born only from documents on disk.

Both are enforced with client-side tools — which is exactly why the agent uses
*our* `fetch_document` rather than Anthropic's server-side web tools: server-side
fetches never pass through our provenance ledger, so the gate couldn't see them.

## Tools (all client-side)

| tool | what it does |
|------|--------------|
| `search_sources` | Crossref query (open, keyless) → titles / authors / DOI / URL |
| `fetch_document` | download a URL, store + hash it, extract text, record provenance |
| `list_wiki` / `read_wiki_note` | inspect notes written this run |
| `write_wiki_note` | create a note (frontmatter-compatible with the parser); the gate applies to `source` notes |

## Prove it without spending tokens

The gate and tools run with **no LLM calls**:

```
python investigate.py --self-test
```

This searches Crossref, shows the gate **reject** an ungrounded source note,
fetches a real document, then shows the same note **accepted** once grounded.

## View a run in the graph UI

The agent's notes use the same format as the seed wiki, so the same parser and UI
render them:

```
python tools/build_graph.py --wiki runs/latest/wiki --out web/public/graph.json
cd web && npm run dev
```

## Configuration (env vars)

| var | default | meaning |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | — | required for a real run |
| `ARCHEO_MODEL` | `claude-opus-4-8` | model id |
| `ARCHEO_TOKEN_BUDGET` | `150000` | hard per-run token cap |
| `ARCHEO_MAX_ITERS` | `24` | max turns |
| `ARCHEO_MAX_FETCHES` | `15` | max documents per run |
| `ARCHEO_EFFORT` | `medium` | reasoning effort (`low`..`max`) |

## Status: v0 scaffold

Runnable and honest, but intentionally simple. Places that would need hardening
for production are marked `# HARDEN:` in the source — chiefly: HTML→text
extraction is crude, `search_sources` is Crossref-only (Pleiades / Open Context /
Zenodo adapters come next), and there is no citation-graph *depth* control yet
(step 3: follow references N levels deep + mark primary vs secondary + detect
citogenesis automatically). The next honest task is to **run this on the Vergina
claim and diff its wiki against the hand-authored one.**
