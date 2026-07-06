#!/usr/bin/env python3
"""
build_graph.py — parse the ArcheoLogic wiki into graph.json.

The wiki (wiki/*.md) is the single source of truth. This script derives the
graph the web app renders: one node per note, one link per typed edge.

Edges come from two places:
  1. Frontmatter `links:` — explicit, typed (supports / disputes / cites).
  2. Body [[wikilinks]] not already covered by a frontmatter link — emitted as
     faint `mentions` edges, so the reading structure shows up in the graph too.

No external dependencies: the frontmatter is a small, regular YAML subset, parsed
directly. Run from the repo root:  python3 tools/build_graph.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_WIKI = REPO / "wiki"
DEFAULT_OUT = REPO / "web" / "public" / "graph.json"

VALID_TYPES = {"claim", "source", "site", "scholar"}
VALID_RELS = {"supports", "disputes", "cites", "mentions"}
WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        raise ValueError("missing frontmatter")
    end = text.index("\n---", 3)
    fm = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    return fm, body


def parse_frontmatter(fm: str) -> dict:
    """Parse the specific YAML subset used by the wiki notes."""
    data: dict = {}
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue
        # `links:` block (list of {to, rel} maps) or inline `links: []`
        m = re.match(r"^links:\s*(.*)$", raw)
        if m:
            inline = m.group(1).strip()
            if inline in ("[]", ""):
                if inline == "[]":
                    data["links"] = []
                    i += 1
                    continue
                # block form follows on subsequent indented lines
                links = []
                i += 1
                cur: dict = {}
                while i < len(lines) and (lines[i].startswith("  ")):
                    item = lines[i].strip()
                    if item.startswith("- "):
                        if cur:
                            links.append(cur)
                        cur = {}
                        item = item[2:]
                    if ":" in item:
                        k, v = item.split(":", 1)
                        cur[k.strip()] = v.strip().strip('"')
                    i += 1
                if cur:
                    links.append(cur)
                data["links"] = links
                continue
        # plain `key: value`
        if ":" in raw:
            k, v = raw.split(":", 1)
            data[k.strip()] = v.strip().strip('"')
        i += 1
    return data


def compute_citation_metrics(nodes: list[dict], links: list[dict]) -> None:
    """Annotate nodes with citation tier + citogenesis funnels (step 3).

    Derivation follows `cites` edges: `a cites b` means a rests on b, so b is
    nearer the root. A node's *funnel* is everything that transitively cites it
    (its ancestors in the cites graph) — how much ultimately rests on it. A node
    that many chains funnel into but which itself cites little is a citation
    ROOT; a root with a large funnel is where citogenesis shows up (many claims
    tracing back to one source). Source nodes are also tiered primary vs
    secondary (a review/echo) from their frontmatter status.
    """
    # Citogenesis is about EVIDENCE: many claims tracing back to one source or
    # originating scholar. A place (site) cited by many claims is a shared hub,
    # not citogenesis — so only source/scholar nodes are eligible to be roots.
    # The signal is transitive funnel size, not direct citation count (the
    # classic case is one primary paper reached through a chain of echoes).
    ROOT_TYPES = {"source", "scholar"}
    FUNNEL_MIN = 3    # this many nodes must transitively rest on it

    type_by_id = {n["id"]: n["type"] for n in nodes}
    ids = set(type_by_id)
    cites_in: dict[str, set] = {i: set() for i in ids}
    cites_out: dict[str, set] = {i: set() for i in ids}
    for l in links:
        if l["rel"] == "cites":
            cites_out[l["source"]].add(l["target"])
            cites_in[l["target"]].add(l["source"])

    def ancestors(root: str) -> set:
        seen: set[str] = set()
        stack = list(cites_in[root])
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            stack.extend(cites_in[x] - seen)
        return seen

    funnels = {i: ancestors(i) for i in ids}
    roots = {
        i for i in ids
        if type_by_id[i] in ROOT_TYPES and len(funnels[i]) >= FUNNEL_MIN
    }

    for n in nodes:
        i = n["id"]
        n["in_cites"] = len(cites_in[i])
        n["out_cites"] = len(cites_out[i])
        n["funnel_size"] = len(funnels[i])
        n["citogenesis_root"] = i in roots
        if i in roots:
            n["funnel_members"] = sorted(funnels[i])
        if n["type"] == "source":
            n["tier"] = "secondary" if n.get("status") == "secondary" else "primary"
        n["traces_to"] = sorted(r for r in roots if i in funnels[r])


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse a wiki/ dir into graph.json")
    ap.add_argument("--wiki", type=Path, default=DEFAULT_WIKI,
                    help="directory of *.md notes (default: repo wiki/)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="output graph.json path")
    args = ap.parse_args()
    wiki_dir, out = args.wiki, args.out

    if not wiki_dir.is_dir():
        print(f"error: {wiki_dir} not found", file=sys.stderr)
        return 1

    notes: dict[str, dict] = {}
    for path in sorted(wiki_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        try:
            fm_text, body = split_frontmatter(text)
        except ValueError as e:
            print(f"error: {path.name}: {e}", file=sys.stderr)
            return 1
        fm = parse_frontmatter(fm_text)
        node_id = fm.get("id")
        if not node_id:
            print(f"error: {path.name}: missing id", file=sys.stderr)
            return 1
        if node_id in notes:
            print(f"error: duplicate id {node_id}", file=sys.stderr)
            return 1
        if fm.get("type") not in VALID_TYPES:
            print(f"error: {path.name}: bad type {fm.get('type')!r}", file=sys.stderr)
            return 1
        fm["_body"] = body
        fm["_file"] = path.name
        notes[node_id] = fm

    nodes = []
    links = []
    dangling = []
    seen_edges: set[tuple[str, str, str]] = set()

    for node_id, fm in notes.items():
        try:
            conf = float(fm.get("confidence", 0.0))
        except ValueError:
            conf = 0.0
        nodes.append(
            {
                "id": node_id,
                "type": fm["type"],
                "title": fm.get("title", node_id),
                "status": fm.get("status", ""),
                "confidence": conf,
                "body": fm["_body"],
            }
        )

        # typed edges from frontmatter
        explicit_targets = set()
        for link in fm.get("links", []) or []:
            target = link.get("to")
            rel = link.get("rel", "mentions")
            if not target:
                continue
            explicit_targets.add(target)
            if target not in notes:
                dangling.append((node_id, target, rel))
                continue
            if rel not in VALID_RELS:
                print(f"warn: {node_id}: unknown rel {rel!r}", file=sys.stderr)
            key = (node_id, target, rel)
            if key not in seen_edges:
                seen_edges.add(key)
                links.append({"source": node_id, "target": target, "rel": rel})

        # body wikilinks → faint `mentions` if not already an explicit edge
        for target in WIKILINK.findall(fm["_body"]):
            target = target.strip()
            if target == node_id or target in explicit_targets:
                continue
            if target not in notes:
                dangling.append((node_id, target, "mentions(body)"))
                continue
            key = (node_id, target, "mentions")
            if key not in seen_edges:
                seen_edges.add(key)
                links.append({"source": node_id, "target": target, "rel": "mentions"})

    if dangling:
        print("error: dangling links (target id not found):", file=sys.stderr)
        for src, tgt, rel in dangling:
            print(f"  {src} --{rel}--> {tgt}", file=sys.stderr)
        return 1

    # citation analysis (step 3): tiers + citogenesis funnels
    compute_citation_metrics(nodes, links)

    # summary counts
    by_type: dict[str, int] = {}
    for n in nodes:
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1
    by_rel: dict[str, int] = {}
    for l in links:
        by_rel[l["rel"]] = by_rel.get(l["rel"], 0) + 1

    citogenesis_roots = sorted(
        (
            {"id": n["id"], "title": n["title"], "type": n["type"],
             "funnel_size": n["funnel_size"]}
            for n in nodes if n.get("citogenesis_root")
        ),
        key=lambda d: d["funnel_size"],
        reverse=True,
    )

    graph = {
        "nodes": nodes,
        "links": links,
        "meta": {"node_count": len(nodes), "link_count": len(links),
                 "by_type": by_type, "by_rel": by_rel,
                 "citogenesis_roots": citogenesis_roots},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    rel = out.relative_to(REPO) if out.is_relative_to(REPO) else out
    print(f"ok: {len(nodes)} nodes, {len(links)} links -> {rel}")
    print(f"  nodes by type: {by_type}")
    print(f"  links by rel:  {by_rel}")
    if citogenesis_roots:
        print(f"  citogenesis roots ({len(citogenesis_roots)}):")
        for r in citogenesis_roots:
            print(f"    ◈ {r['id']} — {r['funnel_size']} notes funnel in")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
