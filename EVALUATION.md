# EVALUATION

Automated scoring of the wiki's verdicts against a golden set of claims with known scholarly status. Regenerate with `python3 tools/evaluate.py`.

## Scores

| metric | score |
|---|---|
| **verdict accuracy** (bucket match) | **100%** (39/39) |
| **calibration** (confidence in band) | **100%** (39/39) |
| **citation validity** (sources grounded in a fetch) | **100%** (41/41) |

## Per-claim

| claim | domain | expected | verdict | ✓ | conf | calib |
|---|---|---|---|:--:|:--:|:--:|
| `claim-tomb-ii-philip-ii` | vergina | contested | contested | ✓ | 0.55 | ✓ |
| `claim-tomb-ii-arrhidaios` | vergina | contested | contested | ✓ | 0.45 | ✓ |
| `claim-tomb-i-philip-ii` | vergina | contested | contested | ✓ | 0.40 | ✓ |
| `claim-tomb-ii-green-cremation` | vergina | contested | contested | ✓ | 0.60 | ✓ |
| `claim-thera-high-chronology` | thera | contested | contested | ✓ | 0.60 | ✓ |
| `claim-thera-low-chronology` | thera | contested | contested | ✓ | 0.40 | ✓ |
| `claim-thera-indirect-contribution` | thera | contested | contested | ✓ | 0.45 | ✓ |
| `claim-mask-authenticity-dispute` | mycenae | contested | contested | ✓ | 0.50 | ✓ |
| `claim-thera-destroyed-minoans` | thera | settled-false | refuted | ✓ | 0.20 | ✓ |
| `claim-mask-of-agamemnon` | mycenae | settled-false | refuted | ✓ | 0.05 | ✓ |
| `claim-thera-lmib-gap` | thera | settled-true | supported | ✓ | 0.82 | ✓ |
| `claim-mask-chronological-gap` | mycenae | settled-true | supported | ✓ | 0.95 | ✓ |
| `claim-troy-is-hisarlik` | troy | settled-true | supported | ✓ | 0.85 | ✓ |
| `claim-trojan-war-historical` | troy | contested | contested | ✓ | 0.45 | ✓ |
| `claim-wilusa-is-troy` | troy | contested | contested | ✓ | 0.50 | ✓ |
| `claim-troy-vi-viia-war-destruction` | troy | contested | contested | ✓ | 0.50 | ✓ |
| `claim-linear-b-greek` | aegean | settled-true | supported | ✓ | 0.92 | ✓ |
| `claim-norse-precolumbian-america` | norse | settled-true | supported | ✓ | 0.92 | ✓ |
| `claim-lanse-aux-meadows-ad1021` | norse | settled-true | supported | ✓ | 0.90 | ✓ |
| `claim-lbac-multicausal` | collapse | settled-true | supported | ✓ | 0.70 | ✓ |
| `claim-sea-peoples-egyptian-attestation` | collapse | settled-true | supported | ✓ | 0.85 | ✓ |
| `claim-exodus-historical` | levant | settled-false | refuted | ✓ | 0.15 | ✓ |
| `claim-exodus-small-kernel` | levant | contested | contested | ✓ | 0.50 | ✓ |
| `claim-minoan-human-sacrifice` | minoan | contested | contested | ✓ | 0.50 | ✓ |
| `claim-sea-peoples-collapse` | collapse | contested | contested | ✓ | 0.40 | ✓ |
| `claim-antikythera-astronomical-computer` | greek-science | settled-true | supported | ✓ | 0.93 | ✓ |
| `claim-dorian-no-population-signature` | collapse | settled-true | supported | ✓ | 0.72 | ✓ |
| `claim-cleopatra-greek-ancestry` | ptolemaic | settled-true | supported | ✓ | 0.78 | ✓ |
| `claim-king-arthur-historical` | britain | settled-false | refuted | ✓ | 0.15 | ✓ |
| `claim-dorian-invasion-dark-age` | collapse | settled-false | refuted | ✓ | 0.22 | ✓ |
| `claim-cleopatra-maternal-uncertain` | ptolemaic | contested | contested | ✓ | 0.50 | ✓ |
| `claim-gobekli-tepe-pre-agricultural` | neolithic | settled-true | supported | ✓ | 0.88 | ✓ |
| `claim-kensington-runestone-genuine` | norse | settled-false | refuted | ✓ | 0.12 | ✓ |
| `claim-shroud-turin-first-century` | relics | settled-false | refuted | ✓ | 0.15 | ✓ |
| `claim-etruscan-anatolian-origin` | etruscan | settled-false | refuted | ✓ | 0.25 | ✓ |
| `claim-shroud-repair-sample-objection` | relics | contested | contested | ✓ | 0.40 | ✓ |
| `claim-nebra-iron-age-challenge` | bronze-age | contested | contested | ✓ | 0.30 | ✓ |
| `claim-etruscan-language-origin` | etruscan | contested | contested | ✓ | 0.50 | ✓ |
| `claim-phaistos-forgery-hypothesis` | minoan | contested | contested | ✓ | 0.30 | ✓ |

## Method & honest limitations

- **Buckets.** `settled-true` accepts status *supported/settled* with confidence ≥0.70; `settled-false` accepts *refuted* with confidence ≤0.35; `contested` accepts *contested* with confidence 0.30–0.70. A system that resolves a contested claim scores it wrong even if it picks the 'popular' side — calling contested claims contested is the point.
- **This is a consistency / regression harness, not yet an independent test.** The current corpus scores high because the same authors (hand + agent) set both the verdicts and, here, the golden labels reflect the same scholarly reading. Its real discriminating power comes when it scores *fresh* verdicts — e.g. an unattended API agent run — against this fixed golden set. High scores now mean the corpus is internally consistent with the expert buckets and that regressions will be caught.
- **Citation validity is a grounding proxy.** It checks that each cited source note corresponds to a fetched document (`url` + `fetched: true`) — i.e. the source is real and was read. It does **not** yet check that the source *actually says what the claim attributes to it*; that needs an LLM-judge pass over the stored document text (future work).
- **Golden set is a v0 seed** (~39 claims, 3 domains). The spec targets 30–50 spanning more of the literature.
- **Calibration is coarse** (in-band / out-of-band). A finer version would score a proper calibration curve over many verdicts.
