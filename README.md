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

🚧 Private while under construction. **Build step 1 of 6 is complete** — the wiki
→ graph → interactive UI pipeline is proven end-to-end with a hand-authored seed
corpus, ahead of turning the investigation agent loose on it.

## What's built so far (step 1: de-risk the demo)

The whole visual pipeline, working locally with **zero LLM risk** — 24 hand-written,
source-verified notes across two independent claim clusters:

- **Vergina** (15 notes) — the genuinely contested question of *who lies in Tomb II*:
  Philip II (Andronikos) vs. Philip III Arrhidaios (Bartsiokas), plus the Tomb I
  lameness argument. Green-vs-dry cremation forensics, the excavator, the skeptics.
- **Thera / Santorini** (9 notes) — the *high vs. low chronology* eruption-dating
  debate: radiocarbon (~1600 BCE) vs. archaeological synchronism (~1500 BCE).

Every **source** node is backed by a real, fetched document (Bartsiokas 2000 in
*Science*, Musgrave et al. 2010, Bartsiokas et al. 2015 in *PNAS*, Friedrich et al.
2006, Pearson et al. 2018, Ehrlich et al. 2023) — the project's cardinal rule
(*no source node without a fetched document*) applied even to the hand-written seed.

![The citation graph — two claim clusters](docs/img/graph-overview.png)

Click any node to open its **dossier** — the rendered note, its confidence, and
its wikilinks (which navigate the graph):

![Dossier panel for a contested claim](docs/img/dossier-panel.png)

Note how the claim reads *"the system does not pick a side"* and holds confidence
near 0.5 — the epistemic-rigor thesis, made visible: contested claims stay
contested.

## Repository layout

```
wiki/                 the knowledge base — one markdown note per claim/source/site/scholar
                      (YAML frontmatter + typed edges + [[wikilinks]]). Source of truth.
tools/build_graph.py  parser: wiki/*.md → web/public/graph.json (validates, no deps)
web/                  Vite + React + react-force-graph-2d graph UI + dossier panel
docs/img/             screenshots
```

## Run it locally

```bash
python3 tools/build_graph.py     # wiki → web/public/graph.json
cd web && npm install && npm run dev   # open the printed localhost URL
```

The graph is fully static — no API key needed to view it. (Growing the corpus
with the investigation agent is what will use the Claude API; viewing it is free.)

## Stack (planned)

- **Agent:** Claude API (agentic investigation loop, tool use)
- **Knowledge base:** Markdown wiki + `[[wikilinks]]` → parsed to graph JSON
- **Retrieval:** embeddings + pgvector
- **Graph UI:** React + react-force-graph (WebGL), static build → GitHub Pages
- **Data:** Open Context, ADS, Pleiades, Zenodo, open-access journals

---

*Built by [Dimitris Kogias](https://captainjimbo.github.io) — physicist & AI/ML
systems engineer. Sibling project: [Ο Ήλιος — The Living Sun](https://github.com/CaptainJimbo/o-ilios).*
