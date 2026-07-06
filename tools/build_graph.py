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

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WIKI_DIR = REPO / "wiki"
OUT = REPO / "web" / "public" / "graph.json"

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


def main() -> int:
    if not WIKI_DIR.is_dir():
        print(f"error: {WIKI_DIR} not found", file=sys.stderr)
        return 1

    notes: dict[str, dict] = {}
    for path in sorted(WIKI_DIR.glob("*.md")):
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

    # summary counts
    by_type: dict[str, int] = {}
    for n in nodes:
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1
    by_rel: dict[str, int] = {}
    for l in links:
        by_rel[l["rel"]] = by_rel.get(l["rel"], 0) + 1

    graph = {
        "nodes": nodes,
        "links": links,
        "meta": {"node_count": len(nodes), "link_count": len(links),
                 "by_type": by_type, "by_rel": by_rel},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"ok: {len(nodes)} nodes, {len(links)} links -> {OUT.relative_to(REPO)}")
    print(f"  nodes by type: {by_type}")
    print(f"  links by rel:  {by_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
