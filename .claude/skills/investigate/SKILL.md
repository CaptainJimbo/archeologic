---
name: investigate
description: Investigate a historical or archaeological claim for the ArcheoLogic wiki — search scholarly sources, fetch and read them, chase citations, and write cited wiki notes. Use when the user asks to "investigate <claim>", add a claim to the knowledge base, or grow the corpus. Runs on THIS Claude Code session (no Anthropic API key needed) by driving the repo's real tool layer, so the anti-hallucination gate applies to every note.
---

# Investigate a claim (ArcheoLogic)

You are acting as the ArcheoLogic investigation agent, with **this Claude Code
session as the brain**. This is the no-API-key path: it uses the same real,
client-side tools as `investigate.py` (search / fetch / gated write), so a
`source` note can only be created for a document you actually fetched this run.
The paid, reproducible equivalent is `python investigate.py "<claim>"`; use this
skill for interactive, subscription-covered corpus growth.

## 1. Setup (once per session)

```bash
python3 -m venv .venv 2>/dev/null; .venv/bin/pip install -q httpx pypdf
```

Pick a short RUN id (a slug of the claim, e.g. `linear-b`). To let the
investigation link into the existing corpus, seed the run dir with it:

```bash
mkdir -p runs/<RUN>/wiki && cp wiki/*.md runs/<RUN>/wiki/
```

## 2. Drive the tools — one call per command

Every search, fetch, and write MUST go through the repo's tool CLI (do **not** use
your own WebSearch/WebFetch/Write for the investigation record — the point is the
real gate + provenance ledger):

```bash
ARCHEO_RUN_ID=<RUN> PYTHONPATH=. .venv/bin/python -m agent.toolcall <TOOL> '<JSON>'
```

Tools: `search_sources {"query","rows"}` · `fetch_document {"url"}` ·
`list_wiki {}` · `read_wiki_note {"id"}` · `write_wiki_note {...}`.

For `write_wiki_note`, note bodies are long — write JSON to a temp file and pass
`@file` to avoid shell-quoting pain:

```bash
cat > /tmp/note.json <<'JSON'
{ "id": "...", "type": "claim", "title": "...", "status": "...",
  "confidence": 0.5, "body": "... [[other-note-id]] ...", "links": [...] }
JSON
ARCHEO_RUN_ID=<RUN> PYTHONPATH=. .venv/bin/python -m agent.toolcall write_wiki_note @/tmp/note.json
```

## 3. Method (non-negotiable)

1. **Primary vs echo.** Prefer excavation reports / peer-reviewed / lab sources; a
   textbook, news piece, or review repeating them is an echo. Say when a claim
   rests only on echoes.
2. **Citogenesis.** Watch for many sources tracing back to one root; record it.
3. **Evidence, not memory.** A `source` note is REJECTED unless you fetched that
   exact URL this run. Search → fetch → then write the source note with that url.
   Prefer open-access sources (PMC, open journals, DOI landing pages that return
   real text); JSTOR/publisher pages often 403 or return JS stubs — never make a
   source node from one of those.
4. **Wikipedia is a claim source, not evidence** — read it for leads, never make a
   source node for it.
5. **Contested stays contested.** If scholars genuinely disagree, set status
   `contested`, keep confidence near 0.5, and record both the majority and the
   strongest dissent. A claim refuted as literally stated gets status `refuted`
   with low confidence. Calibrate confidence 0..1 by weight of evidence.

## 4. Notes & edges

Types: `claim`, `source`, `site`, `scholar`. Edges (in `links`): `supports`,
`disputes`, `cites`, `mentions`. Sources support/dispute claims; claims cite
sources and dispute rival claims. Reference other notes in bodies with
`[[note-id]]` wikilinks. Run `list_wiki` first and give NEW notes NEW ids; don't
overwrite existing ones.

## 5. When done

Give a short verdict. View the result in the graph:

```bash
python3 tools/build_graph.py --wiki runs/<RUN>/wiki --out web/public/graph.json
cd web && npm run dev
```

If the new notes are corpus-worthy, promote them into `wiki/` by hand (move the
new files, then `python3 tools/build_graph.py`), and they become part of the
permanent, committed knowledge base.
