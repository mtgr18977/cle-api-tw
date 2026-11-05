"""Blind annotation sample and evaluation (plan section 5).

``make_sample`` writes two files:

* ``annotation_sample.csv``  what the annotator sees: id, api, pattern, candidate, example,
  and empty ``label`` / ``note``. No tier, score or frequency (blind), rows shuffled.
* ``annotation_key.csv``     id -> api, stratum, tier, rank, freq, t_score, log_likelihood,
  stratum population / sample size / weight, in_surface.

``evaluate`` joins the annotated sample with the key. Strata are sampled unevenly on purpose
(they cover the frequency x tier space needed to calibrate thresholds), so the population
precision of a tier is estimated with weights ``population / sampled`` per stratum.
"""
from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path

LABELS = {"cle": "cle", "yes": "cle", "y": "cle", "1": "cle",
          "generic": "generic", "g": "generic",
          "not": "not", "not_cle": "not", "no": "not", "n": "not", "0": "not",
          "doubtful": "doubtful", "?": "doubtful", "maybe": "doubtful"}

# stratum -> number of candidates sampled per API
STRATA_SIZES = {"top": 20, "tier1_mid": 15, "tier1_high": 10, "tier2_hi": 15, "tier2_lo": 15,
                "general_noise": 5, "negative": 10, "surface_only": 10}
SAMPLE_COLS = ["id", "api", "pattern", "candidate", "example", "label", "note"]
KEY_COLS = ["id", "api", "stratum", "tier", "rank", "freq", "t_score", "log_likelihood",
            "population", "sampled", "weight", "in_surface"]


def _ikey(r: dict) -> tuple[str, str]:
    return r["pattern"], r["candidate"]


def stratify(main: list[dict], negatives: list[dict], surface: list[dict], top_k: int
             ) -> dict[str, list[dict]]:
    """Partition one API's candidates (dependency method) into disjoint strata."""
    ranked = sorted(main, key=lambda r: int(r["rank"]))
    top = ranked[:top_k]
    rest = ranked[top_k:]
    f = lambda r: int(r["freq"])
    dep_keys = {_ikey(r) for r in main}
    return {
        "top": top,
        "tier1_mid": [r for r in rest if r["tier"] == "1" and f(r) < 10],
        "tier1_high": [r for r in rest if r["tier"] == "1" and f(r) >= 10],
        "tier2_hi": [r for r in rest if r["tier"] == "2" and f(r) >= 4],
        "tier2_lo": [r for r in rest if r["tier"] == "2" and f(r) < 4],
        "general_noise": [r for r in rest if r["tier"] in ("general", "noise")],
        "negative": list(negatives),
        "surface_only": [r for r in surface if _ikey(r) not in dep_keys],
    }


def make_sample(apis: dict[str, dict], seed: int = 13, sizes: dict[str, int] | None = None
                ) -> tuple[list[dict], list[dict]]:
    """``apis``: name -> {"main": rows, "negatives": rows, "surface": rows} (CSV dict rows)."""
    sizes = {**STRATA_SIZES, **(sizes or {})}
    sample, key = [], []
    for api, d in apis.items():
        surface_keys = {_ikey(r) for r in d["surface"]}
        strata = stratify(d["main"], d["negatives"], d["surface"], sizes["top"])
        for name, pop in strata.items():
            rng = random.Random(f"{seed}/{api}/{name}")
            take = pop if name == "top" else rng.sample(pop, min(sizes[name], len(pop)))
            for r in take:
                key.append({"api": api, "stratum": name, "tier": r["tier"], "rank": r.get("rank", ""),
                            "freq": r["freq"], "t_score": r["t_score"],
                            "log_likelihood": r.get("log_likelihood", ""),
                            "population": len(pop), "sampled": len(take),
                            "weight": round(len(pop) / len(take), 4),
                            "in_surface": _ikey(r) in surface_keys,
                            "_row": r})
    order = list(range(len(key)))
    random.Random(seed).shuffle(order)
    out_key = []
    for new_id, i in enumerate(order, 1):
        k = key[i]
        r = k.pop("_row")
        sample.append({"id": new_id, "api": k["api"], "pattern": r["pattern"],
                       "candidate": r["candidate"], "example": r.get("example", ""),
                       "label": "", "note": ""})
        out_key.append({"id": new_id, **k})
    return sample, out_key


def write_csv(rows: list[dict], path: str | Path, cols: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def evaluate(sample: list[dict], key: list[dict], top_ks: tuple[int, ...] = (5, 10, 20)) -> dict:
    kmap = {int(k["id"]): k for k in key}
    ann = []
    for r in sample:
        lab = LABELS.get((r.get("label") or "").strip().lower())
        if lab:
            ann.append((kmap[int(r["id"])], lab))

    def stats(items):
        n = len(items)
        c = {l: sum(1 for _, x in items if x == l) for l in ("cle", "generic", "doubtful", "not")}
        return {"annotated": n, **c,
                "precision_strict": round(c["cle"] / n, 3) if n else None,
                "precision_with_generic": round((c["cle"] + c["generic"]) / n, 3) if n else None,
                "precision_lenient": round((c["cle"] + c["generic"] + c["doubtful"]) / n, 3) if n else None}

    by_stratum: dict[tuple, list] = defaultdict(list)
    for k, lab in ann:
        by_stratum[(k["api"], k["stratum"])].append((k, lab))
    strata = {f"{api}/{s}": stats(v) for (api, s), v in sorted(by_stratum.items())}

    # weighted precision per tier: sum(w * hit) / sum(w), w = population / sampled of the stratum
    def weighted(pred, hit):
        num = den = 0.0
        for k, lab in ann:
            if pred(k):
                w = float(k["weight"])
                num += w * (lab in hit)
                den += w
        return round(num / den, 3) if den else None

    # surface_only rows carry the tier of the *surface* list, so they are left out of the
    # per-tier estimate of the primary (dependency) list; see per_stratum for them.
    in_main = lambda k: k["stratum"] != "surface_only"
    tiers = sorted({k["tier"] for k, _ in ann if in_main(k)})
    per_tier = {t: {"n_annotated": sum(1 for k, _ in ann if in_main(k) and k["tier"] == t),
                    "weighted_precision_strict": weighted(lambda k, t=t: in_main(k) and k["tier"] == t, {"cle"}),
                    "weighted_precision_with_generic": weighted(lambda k, t=t: in_main(k) and k["tier"] == t,
                                                                {"cle", "generic"})}
                for t in tiers}

    p_at_k: dict[str, dict] = {}
    for api in sorted({k["api"] for k, _ in ann}):
        top = {int(k["rank"]): lab for k, lab in ann if k["api"] == api and k["stratum"] == "top"}
        p_at_k[api] = {k: (round(sum(top[i] == "cle" for i in range(1, k + 1)) / k, 3)
                           if all(i in top for i in range(1, k + 1)) else None) for k in top_ks}

    by_surface = {}
    for flag in (True, False):
        sub = [(k, l) for k, l in ann if str(k["in_surface"]) == str(flag)]
        by_surface[f"in_surface={flag}"] = stats(sub)
    return {"annotated_total": len(ann), "of": len(sample), "per_stratum": strata,
            "per_tier_weighted": per_tier, "precision_at_k": p_at_k,
            "by_surface_membership": by_surface}
