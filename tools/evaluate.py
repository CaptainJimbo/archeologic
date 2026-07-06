#!/usr/bin/env python3
"""ArcheoLogic evaluation layer (step 5).

Scores the wiki's verdicts against a golden set of claims whose scholarly status
is known (settled-true / settled-false / contested). Three metrics:

  * verdict accuracy  — does the note's status land in the expected bucket?
    (Crucially: a contested claim must be called "contested", not resolved.)
  * calibration       — is the confidence inside the bucket's expected band?
  * citation validity — are the source notes the claim rests on actually grounded
    in a fetched document (url + fetched: true)? This is the mechanical proxy for
    "the citation is real"; see the limitations note about the stronger check.

Writes EVALUATION.md (deterministic — no timestamps, safe to commit) and prints a
summary. Run:  python3 tools/evaluate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_graph as bg  # reuse the frontmatter parser

WIKI = REPO / "wiki"
GOLDEN = REPO / "eval" / "golden_set.json"
OUT = REPO / "EVALUATION.md"

STATUS_BUCKET = {
    "supported": "settled-true",
    "settled": "settled-true",
    "refuted": "settled-false",
    "contested": "contested",
}


def load_notes() -> dict[str, dict]:
    notes = {}
    for p in sorted(WIKI.glob("*.md")):
        fm_text, _ = bg.split_frontmatter(p.read_text(encoding="utf-8"))
        fm = bg.parse_frontmatter(fm_text)
        if fm.get("id"):
            notes[fm["id"]] = fm
    return notes


def claim_sources(cid: str, notes: dict) -> list[str]:
    """Source notes the claim rests on: sources that support it, or that it cites."""
    out = set()
    for nid, fm in notes.items():
        for link in fm.get("links", []) or []:
            if link.get("to") == cid and link.get("rel") == "supports" \
                    and notes.get(nid, {}).get("type") == "source":
                out.add(nid)
    for link in notes.get(cid, {}).get("links", []) or []:
        if link.get("rel") == "cites" and notes.get(link.get("to"), {}).get("type") == "source":
            out.add(link["to"])
    return sorted(out)


def is_grounded(fm: dict) -> bool:
    return str(fm.get("fetched", "")).lower() == "true" and bool(fm.get("url"))


def main() -> int:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    buckets = golden["buckets"]
    notes = load_notes()

    rows = []
    n_verdict_ok = n_calib_ok = 0
    cited_sources: set[str] = set()

    for entry in golden["claims"]:
        cid, expected = entry["id"], entry["expected"]
        fm = notes.get(cid)
        if fm is None:
            rows.append({"id": cid, "domain": entry["domain"], "expected": expected,
                         "status": "(missing)", "verdict_ok": False, "conf": None,
                         "calib_ok": False})
            continue
        status = fm.get("status", "")
        conf = float(fm.get("confidence", 0.0) or 0.0)
        verdict_ok = STATUS_BUCKET.get(status) == expected
        lo, hi = buckets[expected]["confidence_band"]
        calib_ok = lo <= conf <= hi
        n_verdict_ok += verdict_ok
        n_calib_ok += calib_ok
        cited_sources.update(claim_sources(cid, notes))
        rows.append({"id": cid, "domain": entry["domain"], "expected": expected,
                     "status": status, "verdict_ok": verdict_ok, "conf": conf,
                     "calib_ok": calib_ok})

    total = len(golden["claims"])
    grounded = [s for s in cited_sources if is_grounded(notes.get(s, {}))]
    ungrounded = sorted(cited_sources - set(grounded))
    cite_validity = len(grounded) / len(cited_sources) if cited_sources else 1.0

    verdict_acc = n_verdict_ok / total
    calib_acc = n_calib_ok / total

    # ---- render EVALUATION.md (deterministic) -------------------------------
    L = []
    L.append("# EVALUATION\n")
    L.append("Automated scoring of the wiki's verdicts against a golden set of "
             "claims with known scholarly status. Regenerate with "
             "`python3 tools/evaluate.py`.\n")
    L.append("## Scores\n")
    L.append(f"| metric | score |")
    L.append(f"|---|---|")
    L.append(f"| **verdict accuracy** (bucket match) | **{verdict_acc:.0%}** "
             f"({n_verdict_ok}/{total}) |")
    L.append(f"| **calibration** (confidence in band) | **{calib_acc:.0%}** "
             f"({n_calib_ok}/{total}) |")
    L.append(f"| **citation validity** (sources grounded in a fetch) | "
             f"**{cite_validity:.0%}** ({len(grounded)}/{len(cited_sources)}) |\n")

    L.append("## Per-claim\n")
    L.append("| claim | domain | expected | verdict | ✓ | conf | calib |")
    L.append("|---|---|---|---|:--:|:--:|:--:|")
    for r in rows:
        conf = "—" if r["conf"] is None else f"{r['conf']:.2f}"
        L.append(f"| `{r['id']}` | {r['domain']} | {r['expected']} | "
                 f"{r['status']} | {'✓' if r['verdict_ok'] else '✗'} | {conf} | "
                 f"{'✓' if r['calib_ok'] else '✗'} |")
    L.append("")

    if ungrounded:
        L.append("## Ungrounded sources (cited but not fetched)\n")
        for s in ungrounded:
            L.append(f"- `{s}`")
        L.append("")

    L.append("## Method & honest limitations\n")
    L.append("- **Buckets.** `settled-true` accepts status *supported/settled* "
             "with confidence ≥0.70; `settled-false` accepts *refuted* with "
             "confidence ≤0.35; `contested` accepts *contested* with confidence "
             "0.30–0.70. A system that resolves a contested claim scores it wrong "
             "even if it picks the 'popular' side — calling contested claims "
             "contested is the point.")
    L.append("- **This is a consistency / regression harness, not yet an "
             "independent test.** The current corpus scores high because the same "
             "authors (hand + agent) set both the verdicts and, here, the golden "
             "labels reflect the same scholarly reading. Its real discriminating "
             "power comes when it scores *fresh* verdicts — e.g. an unattended API "
             "agent run — against this fixed golden set. High scores now mean the "
             "corpus is internally consistent with the expert buckets and that "
             "regressions will be caught.")
    L.append("- **Citation validity is a grounding proxy.** It checks that each "
             "cited source note corresponds to a fetched document (`url` + "
             "`fetched: true`) — i.e. the source is real and was read. It does "
             "**not** yet check that the source *actually says what the claim "
             "attributes to it*; that needs an LLM-judge pass over the stored "
             "document text (future work).")
    L.append("- **Golden set is a v0 seed** (~%d claims, 3 domains). The spec "
             "targets 30–50 spanning more of the literature." % total)
    L.append("- **Calibration is coarse** (in-band / out-of-band). A finer "
             "version would score a proper calibration curve over many verdicts.")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---- stdout summary -----------------------------------------------------
    print(f"verdict accuracy : {verdict_acc:.0%} ({n_verdict_ok}/{total})")
    print(f"calibration      : {calib_acc:.0%} ({n_calib_ok}/{total})")
    print(f"citation validity: {cite_validity:.0%} ({len(grounded)}/{len(cited_sources)})")
    if ungrounded:
        print(f"ungrounded sources: {', '.join(ungrounded)}")
    fails = [r["id"] for r in rows if not r["verdict_ok"]]
    if fails:
        print(f"verdict misses: {', '.join(fails)}")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
