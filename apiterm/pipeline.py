"""End-to-end analysis: spec -> candidates, tiers, variation (plan section 4)."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from .annotate import annotate_texts, load_model
from .candidates import METHODS, PATTERNS, collect
from .clean import DedupStats, deduplicate
from .extract import extract
from .operations import name_terms, operation_verbs, verb_agreement
from .reference import Reference
from .triage import Thresholds, score_collection, variation_report


@dataclass
class Result:
    summary: dict
    rows: dict[str, list[dict]] = field(default_factory=dict)         # method -> ranked rows
    negatives: dict[str, list[dict]] = field(default_factory=dict)
    variation: dict[str, list[dict]] = field(default_factory=dict)
    opid_verbs: list[dict] = field(default_factory=list)
    verb_agreement: list[dict] = field(default_factory=list)
    name_terms: list[dict] = field(default_factory=list)


def analyze(spec: bytes | str, reference: Reference | None = None, nlp=None,
            thresholds: Thresholds = Thresholds(), methods: tuple[str, ...] = METHODS) -> Result:
    nlp = nlp or load_model()
    items = extract(spec)
    texts, dd = deduplicate(items)
    annotated = annotate_texts(texts, nlp)

    summary: dict = {
        "items_total": len(items),
        "items_by_kind": _count(i.kind for i in items),
        "dedup": _dedup_dict(dd),
        "thresholds": thresholds.__dict__,
        "reference": reference.describe() if reference else None,
        "methods": {},
    }
    res = Result(summary)
    for m in methods:
        col = collect(annotated, m)
        rows, neg = score_collection(col, reference, thresholds)
        res.rows[m], res.negatives[m] = rows, neg
        res.variation[m] = variation_report(rows)
        summary["methods"][m] = {
            "tokens_dedup": col.n_tokens, "tokens_raw": col.n_tokens_raw,
            "candidate_occurrences": col.n_cands,
            "distinct_candidates": len(col.stats),
            "main_list": len(rows), "negative_set": len(neg),
            "by_pattern": {p: sum(1 for r in rows if r["pattern"] == p) for p in PATTERNS},
            "by_tier": _count(r["tier"] for r in rows),
            "by_pattern_tier1": {p: sum(1 for r in rows if r["pattern"] == p and r["tier"] == "1")
                                 for p in PATTERNS},
            "variation_groups": len(res.variation[m]),
            "variation_equivalent": sum(1 for v in res.variation[m] if v["equivalent_class"]),
        }
    if len(methods) == 2:
        a = {(r["pattern"], r["candidate"]) for r in res.rows[methods[0]]}
        b = {(r["pattern"], r["candidate"]) for r in res.rows[methods[1]]}
        a1 = {(r["pattern"], r["candidate"]) for r in res.rows[methods[0]] if r["tier"] == "1"}
        b1 = {(r["pattern"], r["candidate"]) for r in res.rows[methods[1]] if r["tier"] == "1"}
        summary["method_overlap"] = {
            "main_list": _overlap(a, b), "tier1": _overlap(a1, b1),
            "labels": list(methods),
        }
    res.opid_verbs = operation_verbs(items, nlp)
    res.verb_agreement = verb_agreement(items, annotated, nlp)
    res.name_terms = name_terms(items)
    summary["verb_agreement"] = _count(r["status"] for r in res.verb_agreement)
    return res


def _count(it) -> dict:
    d: dict = {}
    for x in it:
        d[x] = d.get(x, 0) + 1
    return d


def _overlap(a: set, b: set) -> dict:
    inter, union = len(a & b), len(a | b)
    return {"a_only": len(a - b), "b_only": len(b - a), "both": inter,
            "jaccard": round(inter / union, 3) if union else None}


def _dedup_dict(dd: DedupStats) -> dict:
    return {"items_before": dd.items_before, "items_after": dd.items_after,
            "removed": dd.removed, "chars_before": dd.chars_before, "chars_after": dd.chars_after}


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def write_outputs(res: Result, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for m in res.rows:
        for name, rows in ((f"candidates_{m}.csv", res.rows[m]),
                           (f"negatives_{m}.csv", res.negatives[m]),
                           (f"variation_{m}.csv", res.variation[m])):
            _write_csv(out / name, rows)
            written.append(out / name)
    for name, rows in (("operationId_verbs.csv", res.opid_verbs),
                       ("verb_agreement.csv", res.verb_agreement),
                       ("name_terms.csv", res.name_terms)):
        _write_csv(out / name, rows)
        written.append(out / name)
    (out / "summary.json").write_text(json.dumps(res.summary, indent=2), encoding="utf-8")
    written.append(out / "summary.json")
    return written
