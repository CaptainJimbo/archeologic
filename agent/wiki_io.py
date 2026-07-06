"""Read/write wiki notes in the exact format tools/build_graph.py expects.

The agent's notes and the hand-authored notes are byte-compatible, so the SAME
parser and the SAME graph UI render both — which is what makes step-2 output
directly comparable to the step-1 benchmark.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

VALID_TYPES = {"claim", "source", "site", "scholar"}
VALID_RELS = {"supports", "disputes", "cites", "mentions"}
_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return _SLUG.sub("-", text.lower()).strip("-")


def _today() -> str:
    return datetime.date.today().isoformat()


def render_note(meta: dict, body: str) -> str:
    """Serialize a note to frontmatter + markdown body."""
    lines = ["---"]
    for key in ("id", "type", "title", "status"):
        val = meta.get(key, "")
        if key in ("title",):
            lines.append(f'{key}: "{val}"')
        else:
            lines.append(f"{key}: {val}")
    lines.append(f"confidence: {float(meta.get('confidence', 0.0)):.2f}")
    lines.append(f"created: {meta.get('created', _today())}")
    lines.append(f"updated: {meta.get('updated', _today())}")

    if meta.get("type") == "source":
        for key in ("source_kind", "authors", "year", "venue", "doi", "url"):
            if meta.get(key) not in (None, ""):
                val = meta[key]
                if key in ("authors", "venue", "doi", "url"):
                    lines.append(f'{key}: "{val}"')
                else:
                    lines.append(f"{key}: {val}")
        lines.append("fetched: true")

    links = meta.get("links") or []
    if not links:
        lines.append("links: []")
    else:
        lines.append("links:")
        for link in links:
            lines.append(f"  - to: {link['to']}")
            lines.append(f"    rel: {link['rel']}")

    lines.append("---")
    lines.append("")
    lines.append(body.rstrip() + "\n")
    return "\n".join(lines)


def write_note(out_dir: Path, meta: dict, body: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{meta['id']}.md"
    path.write_text(render_note(meta, body), encoding="utf-8")
    return path


def list_note_ids(out_dir: Path) -> list[str]:
    if not out_dir.is_dir():
        return []
    return sorted(p.stem for p in out_dir.glob("*.md"))


def read_note(out_dir: Path, note_id: str) -> str | None:
    path = out_dir / f"{note_id}.md"
    return path.read_text(encoding="utf-8") if path.exists() else None
