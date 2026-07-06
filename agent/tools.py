"""Client-side tools for the investigation agent.

These run in OUR process (not Anthropic's server-side tools) precisely so we can
enforce two invariants the model cannot bypass:

  * fetch_document actually downloads, stores, and hashes each document, and
    records it in `self.fetched`;
  * write_wiki_note REJECTS a `source` note whose document was not fetched this
    run — the anti-hallucination gate, enforced here in code.

Search uses Crossref (open, keyless). Fetch is plain HTTP. Both are intentionally
simple: this is a v0 scaffold, and every place that would need hardening for
production is marked `# HARDEN:`.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import re
from pathlib import Path

import httpx

from .config import Config
from . import wiki_io

CROSSREF = "https://api.crossref.org/works"
_MAX_TEXT = 4000  # chars of extracted text returned to the model per fetch


# --- tool schemas (sent to the API) -----------------------------------------
TOOL_DEFS = [
    {
        "name": "search_sources",
        "description": (
            "Search the scholarly literature (Crossref) for works matching a "
            "query. Returns titles, authors, year, DOI, and a URL for each hit. "
            "Use this to find primary sources; then fetch_document to read one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms"},
                "rows": {"type": "integer", "description": "How many results (1-8)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_document",
        "description": (
            "Download a document by URL, store it, and return its extracted text "
            "plus a fetch_id. A `source` wiki note may ONLY be written for a URL "
            "fetched this way — fetch before you cite."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Document URL"}},
            "required": ["url"],
        },
    },
    {
        "name": "list_wiki",
        "description": "List the ids of wiki notes written so far this run.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_wiki_note",
        "description": "Read a wiki note written this run, by id.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "write_wiki_note",
        "description": (
            "Create or overwrite a wiki note. Types: claim, source, site, "
            "scholar. Link with typed edges (supports, disputes, cites, "
            "mentions). A `source` note REQUIRES a url (or fetch_id) that was "
            "fetched this run, or it will be rejected."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "kebab-case id, e.g. claim-tomb-ii-philip-ii"},
                "type": {"type": "string", "enum": ["claim", "source", "site", "scholar"]},
                "title": {"type": "string"},
                "status": {"type": "string", "description": "e.g. contested, primary, secondary, reference"},
                "confidence": {"type": "number", "description": "0.0-1.0, calibrated"},
                "body": {"type": "string", "description": "Markdown; use [[note-id]] wikilinks"},
                "links": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string"},
                            "rel": {"type": "string", "enum": ["supports", "disputes", "cites", "mentions"]},
                        },
                        "required": ["to", "rel"],
                    },
                },
                "url": {"type": "string", "description": "source notes: the fetched document URL"},
                "fetch_id": {"type": "string", "description": "source notes: id returned by fetch_document"},
                "authors": {"type": "string"},
                "year": {"type": "integer"},
                "venue": {"type": "string"},
                "doi": {"type": "string"},
                "source_kind": {"type": "string", "description": "journal-article, review-article, dataset, ..."},
            },
            "required": ["id", "type", "title", "status", "confidence", "body"],
        },
    },
]


def _norm_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def _html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _pdf_to_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader  # lazy: only needed for PDFs
    except ImportError:
        return "[pypdf not installed — cannot extract PDF text]"
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:25])


class ToolContext:
    """Executes tool calls and holds the run's provenance state."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        # provenance: everything fetched this run, keyed both ways
        self.fetched_by_url: dict[str, dict] = {}
        self.fetched_by_id: dict[str, dict] = {}
        self.fetch_count = 0
        self.notes_written: list[str] = []
        self.gate_rejections = 0
        self._http = httpx.Client(
            follow_redirects=True,
            timeout=cfg.request_timeout,
            headers={"User-Agent": cfg.user_agent},
        )
        # Provenance persists to disk so the gate works across separate
        # processes (e.g. one tool call per invocation, as a subagent drives it).
        self._load_ledger()

    def _load_ledger(self):
        p = self.cfg.run_dir / "provenance.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            self.fetched_by_url = d.get("by_url", {})
            self.fetched_by_id = d.get("by_id", {})
            self.fetch_count = d.get("fetch_count", 0)
            self.notes_written = d.get("notes_written", [])
            self.gate_rejections = d.get("gate_rejections", 0)

    def _save_ledger(self):
        self.cfg.run_dir.mkdir(parents=True, exist_ok=True)
        (self.cfg.run_dir / "provenance.json").write_text(
            json.dumps(
                {
                    "by_url": self.fetched_by_url,
                    "by_id": self.fetched_by_id,
                    "fetch_count": self.fetch_count,
                    "notes_written": self.notes_written,
                    "gate_rejections": self.gate_rejections,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    # -- dispatch -------------------------------------------------------------
    def dispatch(self, name: str, args: dict) -> tuple[str, bool]:
        """Return (result_text, is_error)."""
        handler = getattr(self, f"_t_{name}", None)
        if handler is None:
            return f"unknown tool: {name}", True
        try:
            return handler(args)
        except Exception as e:  # surfaced to the model so it can adapt
            return f"tool {name} failed: {type(e).__name__}: {e}", True

    # -- tools ----------------------------------------------------------------
    def _t_search_sources(self, args: dict) -> tuple[str, bool]:
        query = args["query"]
        rows = max(1, min(int(args.get("rows", 5)), 8))
        r = self._http.get(
            CROSSREF,
            params={
                "query": query,
                "rows": rows,
                "select": "title,author,issued,DOI,URL,container-title,type",
            },
        )
        r.raise_for_status()
        items = r.json().get("message", {}).get("items", [])
        if not items:
            return f"No results for {query!r}.", False
        out = [f"{len(items)} result(s) for {query!r}:"]
        for it in items:
            title = (it.get("title") or ["(untitled)"])[0]
            authors = ", ".join(
                f"{a.get('given','')} {a.get('family','')}".strip()
                for a in (it.get("author") or [])[:4]
            ) or "(authors n/a)"
            year = ""
            parts = it.get("issued", {}).get("date-parts", [[None]])
            if parts and parts[0] and parts[0][0]:
                year = parts[0][0]
            venue = (it.get("container-title") or [""])[0]
            out.append(
                f"\n• {title}\n  {authors} ({year}) — {venue}\n"
                f"  DOI: {it.get('DOI','')}\n  URL: {it.get('URL','')}"
            )
        return "\n".join(out), False

    def _t_fetch_document(self, args: dict) -> tuple[str, bool]:
        if self.fetch_count >= self.cfg.max_fetches:
            return (
                f"fetch limit reached ({self.cfg.max_fetches}). Work with what "
                f"you have already fetched.",
                True,
            )
        url = args["url"]
        r = self._http.get(url)
        if r.status_code != 200:
            return f"fetch {url} returned HTTP {r.status_code}.", True
        data = r.content
        ctype = r.headers.get("content-type", "").lower()
        final_url = str(r.url)

        if "pdf" in ctype or final_url.lower().endswith(".pdf"):
            text, ext = _pdf_to_text(data), "pdf"
        elif "json" in ctype:
            text, ext = json.dumps(r.json(), indent=2)[: _MAX_TEXT * 2], "json"
        else:
            text, ext = _html_to_text(r.text), "html"

        fetch_id = hashlib.sha256(data).hexdigest()[:12]
        self.cfg.corpus_dir.mkdir(parents=True, exist_ok=True)
        stored = self.cfg.corpus_dir / f"{fetch_id}.{ext}"
        stored.write_bytes(data)

        record = {
            "fetch_id": fetch_id,
            "url": url,
            "final_url": final_url,
            "content_type": ctype,
            "sha256": hashlib.sha256(data).hexdigest(),
            "stored": str(stored.relative_to(self.cfg.run_dir.parent.parent)),
            "chars": len(text),
        }
        # record under every URL spelling so the gate matches what the model cites
        for key in {_norm_url(url), _norm_url(final_url)}:
            self.fetched_by_url[key] = record
        self.fetched_by_id[fetch_id] = record
        self.fetch_count += 1
        self._save_ledger()

        excerpt = text[:_MAX_TEXT]
        more = "" if len(text) <= _MAX_TEXT else f"\n[... {len(text)-_MAX_TEXT} more chars stored on disk]"
        return (
            f"fetch_id={fetch_id}  status=200  type={ctype or 'unknown'}\n"
            f"stored={record['stored']}\n"
            f"--- extracted text ---\n{excerpt}{more}",
            False,
        )

    def _t_list_wiki(self, args: dict) -> tuple[str, bool]:
        ids = wiki_io.list_note_ids(self.cfg.out_dir)
        return ("notes written this run:\n" + "\n".join(ids)) if ids else "no notes yet.", False

    def _t_read_wiki_note(self, args: dict) -> tuple[str, bool]:
        text = wiki_io.read_note(self.cfg.out_dir, args["id"])
        return (text, False) if text is not None else (f"no note {args['id']!r}.", True)

    def _t_write_wiki_note(self, args: dict) -> tuple[str, bool]:
        ntype = args.get("type")
        if ntype not in wiki_io.VALID_TYPES:
            return f"invalid type {ntype!r}.", True
        conf = float(args.get("confidence", 0.0))
        if not 0.0 <= conf <= 1.0:
            return f"confidence must be 0.0-1.0, got {conf}.", True
        for link in args.get("links") or []:
            if link.get("rel") not in wiki_io.VALID_RELS:
                return f"invalid edge rel {link.get('rel')!r}.", True

        # --- the anti-hallucination gate ------------------------------------
        if ntype == "source":
            fid = args.get("fetch_id")
            url = args.get("url")
            grounded = (fid and fid in self.fetched_by_id) or (
                url and _norm_url(url) in self.fetched_by_url
            )
            if not grounded:
                self.gate_rejections += 1
                self._save_ledger()
                return (
                    "REJECTED: a `source` note must correspond to a document "
                    "fetched THIS RUN. Call fetch_document(url) first, then write "
                    "the source note with that same url (or the returned "
                    "fetch_id). Never create a source node from memory.",
                    True,
                )

        meta = {k: args[k] for k in (
            "id", "type", "title", "status", "url", "doi", "venue",
            "authors", "year", "source_kind", "links") if k in args}
        meta["confidence"] = conf
        path = wiki_io.write_note(self.cfg.out_dir, meta, args["body"])
        if args["id"] not in self.notes_written:
            self.notes_written.append(args["id"])
        self._save_ledger()
        return f"wrote {path.name} ({ntype}).", False

    def provenance(self) -> dict:
        return {
            "fetched": list(self.fetched_by_id.values()),
            "notes_written": self.notes_written,
            "gate_rejections": self.gate_rejections,
        }

    def close(self):
        self._http.close()
