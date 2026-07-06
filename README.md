# ArcheoLogic 🏺

**The AI archaeologist.** An LLM agent that investigates historical and
archaeological claims the way a scholar does — chasing citations back to primary
evidence, building a living knowledge base as it digs, and returning **cited
verdicts** with confidence levels and honest dissent.

> 99% of archaeology is done in the library. This is the librarian that never
> sleeps — and never repeats a claim without checking where it came from.

## What it does

Give it a claim — *"the Thera eruption destroyed Minoan civilization"*,
*"Vergina Tomb II belongs to Philip II of Macedon"* — and it:

1. **Investigates at scale** — searches open scholarly sources, excavation
   reports, gazetteers; follows citations from paper to paper.
2. **Traces claims to their roots** — separates primary evidence (excavation
   reports, radiocarbon dates) from echo (textbooks citing textbooks). Detects
   **citogenesis**: "everyone knows X" that traces to a single 1930s paper.
3. **Writes a living wiki** — one markdown note per claim / source / site /
   scholar, interlinked with `[[wikilinks]]` (Karpathy LLM-wiki style). The wiki
   *is* the knowledge graph, git-versioned, growing with every investigation.
4. **Renders the graph on the web** — an interactive force-directed graph
   (Obsidian-style): claims amber, sources cyan, sites green, scholars violet;
   *supports* solid, *disputes* red. Click a node → read the dossier.
   Citation circularity becomes a **visible shape**.
5. **Returns a cited verdict** — verdict + confidence, the evidence chain, the
   dissenting minority and why, every statement linked to its source.
6. **Scores itself honestly** — evaluated against a golden set of claims with
   known scholarly status (settled-true / settled-false / genuinely contested).

**Beachhead domain:** Greek archaeology (Thera, Vergina, Mycenae) — home
advantage in language and sources.

## Status

🚧 Early scaffold — private while under construction.

## Stack (planned)

- **Agent:** Claude API (agentic investigation loop, tool use)
- **Knowledge base:** Markdown wiki + `[[wikilinks]]` → parsed to graph JSON
- **Retrieval:** embeddings + pgvector
- **Graph UI:** React + react-force-graph (WebGL), static build → GitHub Pages
- **Data:** Open Context, ADS, Pleiades, Zenodo, open-access journals

---

*Built by [Dimitris Kogias](https://captainjimbo.github.io) — physicist & AI/ML
systems engineer. Sibling project: [Ο Ήλιος — The Living Sun](https://github.com/CaptainJimbo/o-ilios).*
