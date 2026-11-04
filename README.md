# APITerm

Terminology (CLE) extraction from OpenAPI documentation, following the Termisul-style method:
domain corpus vs. general-language reference, frequency filter, association measures, three-tier triage.
It answers: *which word combinations are characteristic of an API's docs, and are they used consistently?*

## Install

```bash
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

## Use

```bash
python -m apiterm analyze spec.yaml --reference reference/data/news.db --out out/   # CSVs + summary.json
python -m apiterm report out/ --html report/index.html                              # static dark-theme report
python -m apiterm sample out/ && python -m apiterm evaluate out/annotation_sample_surface.csv
APITERM_REFERENCE=reference/data/news.db uvicorn app.main:app                       # webapp
```

Without `--reference` only cohesion (t-score) is computed and there is no 3-tier triage.
The webapp processes uploads in memory only; nothing is saved or logged.

## Pipeline (`apiterm/`)

| Module | Plan step |
|---|---|
| `extract.py` | YAML/JSON → description/summary/title; `operationId`, property and parameter names as separate corpora |
| `clean.py` | Markdown/code/URL removal, identifier splitting, deduplication (raw vs. dedup frequency, distinct contexts) |
| `annotate.py` | spaCy lemma/POS/deps + two documented fixes (see below) |
| `candidates.py` | Method A (surface patterns) and B (dependencies): V+N, V+Prep+N, N+N, Adj+N, N+of+N |
| `measures.py` | t-score, PMI, Dice, MLE (cohesion); Dunning log-likelihood and smoothed ratio (specificity) |
| `triage.py` | negative set (freq < 2), tiers 1 / 2 / general / noise, verb-variation report |
| `operations.py` | operationId verbs, name terms, operationId-vs-description verb agreement |
| `reference.py` | reference counts table (SQLite) and its builder |
| `evaluation.py` | stratified annotation sample, precision per tier and precision@k |
| `report.py`, `app/` | static report (M7), webapp (M8) |

Thresholds: t ≥ 2 (needs freq ≥ 4, since t ≤ √c) and log-likelihood ≥ 3.84; both configurable and meant to be calibrated.

## Known limitations

* **POS quality on API prose.** Both `en_core_web_sm` and `_md` tag *token* as VERB/ADJ, and text-initial
  verbs (*List…*, *Returns…*) as nouns. `annotate.py` applies a small noun lexicon (`token`, `identifier`) with
  dependency repair, and a helper-word trick for known API verbs. Extend `NOUN_OVERRIDES` / `API_VERBS` for your domain.
* Surface patterns require adjacency (an adjective in *create a new token* blocks V+N); that gap is the A-vs-B comparison.
* Verb "equivalence" in the variation report uses a small hand-made lexicon; it flags, a human decides.
* Identifiers in backticks (`access_token`) are kept but excluded from candidates.
* MLE is defined here as c/N; confirm against the mwetoolkit definition if you need strict parity.

## Status vs. plan milestones

| Milestone | Status |
|---|---|
| M1–M2, M4, M6, M7, M8 | Implemented and tested (tests use a small fictional spec and a synthetic news stub) |
| M5 | Tooling only (sample + evaluate); the manual annotation is yours to do |
| M0, M3 | **Not done**: real APIs, corpus choice and licence checks, and the real reference table are still open |

Because no real reference corpus is bundled, the numbers in this repo's tests are not linguistic results.
