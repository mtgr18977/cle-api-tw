"""Scoring, three-tier triage (4.5, 4.7) and verb-variation report (4.8)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from . import measures as M
from .candidates import Collection
from .reference import Reference

TIER_LABELS = {
    "1": "CLE candidate",
    "2": "Human review",
    "general": "General collocation",
    "noise": "Noise",
    "negative": "Negative set (freq < min)",
    "n/a": "No reference (cohesion only)",
}
TIER_ORDER = {"1": 0, "2": 1, "n/a": 2, "general": 3, "noise": 4, "negative": 5}


@dataclass(frozen=True)
class Thresholds:
    min_freq: int = 2      # below this -> negative set
    t_min: float = 2.0     # ~95% confidence; note t <= sqrt(c), so t >= 2 needs c >= 4
    ll_min: float = 3.84   # chi2(1) p < 0.05; use 6.63 for p < 0.01


def score_collection(col: Collection, ref: Reference | None, th: Thresholds = Thresholds()
                     ) -> tuple[list[dict], list[dict]]:
    """Return (ranked rows, negative-set rows)."""
    main: list[dict] = []
    negative: list[dict] = []
    ref_total = ref.total(col.method) if ref else 0
    for cand, st in col.stats.items():
        cs = [max(col.unigrams.get(w, 0), 1) for w in cand.words]
        c = st.count
        row = {
            "pattern": cand.pattern, "candidate": cand.key,
            "freq": c, "raw_freq": st.raw, "contexts": len(st.contexts),
            "t_score": round(M.t_score(c, cs, col.n_tokens), 3),
            "pmi": round(M.pmi(c, cs, col.n_tokens), 3),
            "dice": round(M.dice(c, cs), 4),
            "mle": round(M.mle(c, col.n_tokens), 8),
            "ref_freq": None, "log_likelihood": None, "freq_ratio": None,
            "example": st.example,
        }
        cohesive = row["t_score"] >= th.t_min
        if ref is not None and ref_total > 0:
            b = ref.count(col.method, cand)
            ll = M.log_likelihood(c, b, col.n_cands, ref_total)
            over = c / col.n_cands > b / ref_total
            row["ref_freq"] = b
            row["freq_ratio"] = round(M.rel_freq_ratio(c, b, col.n_cands, ref_total), 3)
            row["log_likelihood"] = round(ll, 3) if over else round(-ll, 3)  # sign = direction
            specific = over and ll >= th.ll_min
            tier = ("1" if specific else "general") if cohesive else ("2" if specific else "noise")
        else:
            tier = "n/a"
        if c < th.min_freq:
            tier = "negative"
        row["tier"] = tier
        row["tier_label"] = TIER_LABELS[tier]
        (negative if tier == "negative" else main).append(row)

    def sort_key(r: dict):
        return (TIER_ORDER[r["tier"]], -(r["log_likelihood"] or 0), -r["t_score"], r["candidate"])

    main.sort(key=sort_key)
    for i, r in enumerate(main, 1):
        r["rank"] = i
    negative.sort(key=lambda r: (-r["freq"], r["candidate"]))
    return main, negative


# ---------------------------------------------------------------- verb variation
# Conservative, English-API specific lexicon. It only *flags* possible variation for human
# review; the author decides whether two verbs are really interchangeable in their API.
SEMANTIC_CLASSES: dict[str, frozenset[str]] = {
    "create": frozenset({"create", "generate", "issue", "make", "add", "produce", "build"}),
    "retrieve": frozenset({"retrieve", "get", "fetch", "obtain", "read"}),
    "delete": frozenset({"delete", "remove", "destroy", "erase"}),
    "update": frozenset({"update", "modify", "edit", "change", "amend"}),
    "list": frozenset({"list", "enumerate"}),
    "send": frozenset({"send", "submit", "dispatch", "deliver"}),
}
_VERB_CLASS = {v: k for k, vs in SEMANTIC_CLASSES.items() for v in vs}


def verb_class(verb: str) -> str | None:
    return _VERB_CLASS.get(verb)


def variation_report(rows: list[dict], min_verbs: int = 2) -> list[dict]:
    """Group V+N / V+Prep+N candidates by noun head and list verbs (plan 4.8)."""
    by_noun: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        if r["pattern"] not in ("V+N", "V+Prep+N") or r["tier"] in ("general", "noise"):
            # "general"/"noise" combinations are not terminology; ignore them for variation
            continue
        words = r["candidate"].split()
        verb, noun = words[0], words[-1]
        label = " ".join(words[:-1])
        cur = by_noun[noun].get(label)
        if cur is None or r["freq"] > cur["freq"]:
            by_noun[noun][label] = {"verb": verb, "label": label, "freq": r["freq"],
                                    "contexts": r["contexts"], "ll": r["log_likelihood"] or 0.0}
    out = []
    for noun, verbs in by_noun.items():
        if len(verbs) < min_verbs:
            continue
        vs = sorted(verbs.values(), key=lambda v: (-v["freq"], -v["ll"], v["label"]))
        classes: dict[str, list[dict]] = defaultdict(list)
        for v in vs:
            k = verb_class(v["verb"])
            if k:
                classes[k].append(v)
        equiv = {k: g for k, g in classes.items() if len({x["verb"] for x in g}) >= 2}
        flag = ""
        preferred = ""
        if equiv:
            k, g = max(equiv.items(), key=lambda kv: sum(x["freq"] for x in kv[1]))
            best = max(g, key=lambda v: (v["freq"], v["ll"], v["contexts"]))
            flag, preferred = k, best["label"]
        out.append({
            "noun": noun, "n_verbs": len(vs), "total_freq": sum(v["freq"] for v in vs),
            "verbs": "; ".join(f'{v["label"]}:{v["freq"]}' for v in vs),
            "contexts": "; ".join(f'{v["label"]}:{v["contexts"]}' for v in vs),
            "equivalent_class": flag, "suggested_preferred": preferred,
        })
    out.sort(key=lambda r: (r["equivalent_class"] == "", -r["total_freq"], r["noun"]))
    return out
