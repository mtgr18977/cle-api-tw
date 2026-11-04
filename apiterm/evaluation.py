"""Manual-annotation sample and evaluation (plan section 5).

Workflow: ``make_sample`` -> annotate the ``label`` column by hand (cle / not / doubtful)
-> ``evaluate``. Precision is reported per tier (the sample is stratified, so there is no
single population precision) and precision@k over the full ranked list for every k whose
top-k rows were all annotated (the top ``top_k`` rows are always included in the sample).
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

LABELS = {"cle": "cle", "yes": "cle", "y": "cle", "1": "cle",
          "not": "not", "not_cle": "not", "no": "not", "n": "not", "0": "not",
          "doubtful": "doubtful", "?": "doubtful", "maybe": "doubtful"}
SAMPLE_COLS = ["rank", "tier", "pattern", "candidate", "freq", "contexts", "t_score",
               "log_likelihood", "example", "label"]
STRATA = ("1", "2", "general", "noise", "n/a")


def make_sample(rows: list[dict], n: int = 200, seed: int = 13, top_k: int = 50) -> list[dict]:
    rng = random.Random(seed)
    ranked = sorted(rows, key=lambda r: int(r["rank"]))
    chosen = {int(r["rank"]): r for r in ranked[:top_k]}
    rest = [r for r in ranked if int(r["rank"]) not in chosen]
    budget = max(n - len(chosen), 0)
    by_tier = {t: [r for r in rest if r["tier"] == t] for t in STRATA}
    live = {t: v for t, v in by_tier.items() if v}
    if live and budget:
        share = {t: max(min(5, len(v)), round(budget * len(v) / sum(map(len, live.values()))))
                 for t, v in live.items()}
        for t, v in live.items():
            for r in rng.sample(v, min(share[t], len(v))):
                chosen[int(r["rank"])] = r
    out = [{c: r.get(c, "") for c in SAMPLE_COLS[:-1]} | {"label": ""}
           for _, r in sorted(chosen.items())]
    return out[:max(n, top_k)]


def write_csv(rows: list[dict], path: str | Path, cols: list[str] | None = None) -> None:
    cols = cols or (list(rows[0]) if rows else SAMPLE_COLS)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def evaluate(rows: list[dict], ks: tuple[int, ...] = (10, 20, 50, 100)) -> dict:
    lab = {}
    for r in rows:
        v = LABELS.get((r.get("label") or "").strip().lower())
        if v:
            lab[int(r["rank"])] = (r["tier"], v)
    per_tier: dict[str, dict] = {}
    for tier, v in lab.values():
        d = per_tier.setdefault(tier, {"annotated": 0, "cle": 0, "doubtful": 0, "not": 0})
        d["annotated"] += 1
        d[v] += 1
    for d in per_tier.values():
        d["precision_strict"] = round(d["cle"] / d["annotated"], 3)
        d["precision_lenient"] = round((d["cle"] + d["doubtful"]) / d["annotated"], 3)
    p_at_k = {}
    for k in ks:
        if all(i in lab for i in range(1, k + 1)):
            p_at_k[k] = round(sum(lab[i][1] == "cle" for i in range(1, k + 1)) / k, 3)
        else:
            p_at_k[k] = None   # top-k not fully annotated
    return {"annotated_total": len(lab), "per_tier": per_tier, "precision_at_k": p_at_k}
