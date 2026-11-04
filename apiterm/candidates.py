"""Candidate extraction (plan section 4.4).

Method A, "surface": POS/lemma sequences with an optional determiner (mwetoolkit style).
Method B, "dependency": relations from the spaCy parser; robust to intervening words.

Both return the same ``Cand`` objects so counting, measures and triage are shared.
In a noun run (``access token``) the head is the last noun; patterns that need a single
noun (V+N, V+Prep+N, N+of+N) use the head.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from .annotate import NOUN_POS, AnnotatedText, Sent, Tok

PATTERNS = ("V+N", "V+Prep+N", "N+N", "Adj+N", "N+of+N")
METHODS = ("surface", "dependency")
MAX_RUN = 3          # longer noun runs are usually lists/noise


@dataclass(frozen=True, slots=True)
class Cand:
    pattern: str
    words: tuple[str, ...]

    @property
    def key(self) -> str:
        return " ".join(self.words)


def _n(t: Tok) -> bool:
    return t.ok and t.pos in NOUN_POS


def _v(t: Tok) -> bool:
    return t.ok and t.pos == "VERB"


def surface_candidates(sent: Sent) -> set[Cand]:
    toks, n = sent.toks, len(sent.toks)
    out: set[Cand] = set()

    def run_end(i: int) -> int:
        j = i
        while j + 1 < n and _n(toks[j + 1]):
            j += 1
        return j

    def noun_at(k: int) -> Tok | None:
        """Head noun of the noun run starting at k (None if not a short run)."""
        if k < n and _n(toks[k]):
            e = run_end(k)
            if e - k + 1 <= MAX_RUN:
                return toks[e]
        return None

    for i, t in enumerate(toks):
        if _v(t):
            k = i + 1
            if k < n and toks[k].ok and toks[k].pos == "DET":
                k += 1
            head = noun_at(k)
            if head is not None:
                out.add(Cand("V+N", (t.lemma, head.lemma)))
            elif i + 1 < n and toks[i + 1].ok and toks[i + 1].pos == "ADP":
                k = i + 2
                if k < n and toks[k].ok and toks[k].pos == "DET":
                    k += 1
                head = noun_at(k)
                if head is not None:
                    out.add(Cand("V+Prep+N", (t.lemma, toks[i + 1].lemma, head.lemma)))
        if _n(t):
            if i + 1 < n and _n(toks[i + 1]):
                out.add(Cand("N+N", (t.lemma, toks[i + 1].lemma)))
            elif i + 2 < n and toks[i + 1].ok and toks[i + 1].pos == "ADP" and toks[i + 1].lemma == "of":
                k = i + 2
                if toks[k].ok and toks[k].pos == "DET" and k + 1 < n:
                    k += 1
                head = noun_at(k)
                if head is not None:
                    out.add(Cand("N+of+N", (t.lemma, "of", head.lemma)))
        if t.ok and t.pos == "ADJ" and i + 1 < n and _n(toks[i + 1]) and not (i + 2 < n and _n(toks[i + 2])):
            out.add(Cand("Adj+N", (t.lemma, toks[i + 1].lemma)))
    return out


def dependency_candidates(sent: Sent) -> set[Cand]:
    toks, n = sent.toks, len(sent.toks)
    out: set[Cand] = set()
    for i, t in enumerate(toks):
        if not t.ok or not (0 <= t.head < n) or t.head == i:
            continue
        h = toks[t.head]
        if t.dep in ("dobj", "nsubjpass") and _n(t) and _v(h):
            verbs = {t.head}
            if h.dep == "conj" and _v(toks[h.head]):
                verbs.add(h.head)                       # "create or update a token"
            verbs.update(j for j, x in enumerate(toks) if x.dep == "conj" and x.head == t.head and _v(x))
            for j in verbs:
                out.add(Cand("V+N", (toks[j].lemma, t.lemma)))
        elif t.dep == "pobj" and _n(t) and h.ok and h.pos == "ADP" and 0 <= h.head < n:
            hh = toks[h.head]
            if h.lemma == "of" and _n(hh):
                out.add(Cand("N+of+N", (hh.lemma, "of", t.lemma)))
            elif _v(hh):
                out.add(Cand("V+Prep+N", (hh.lemma, h.lemma, t.lemma)))
        elif t.dep == "compound" and _n(t) and _n(h):
            out.add(Cand("N+N", (t.lemma, h.lemma)))
        elif t.dep == "amod" and t.pos == "ADJ" and _n(h):
            out.add(Cand("Adj+N", (t.lemma, h.lemma)))
    return out


def extract_from_sentence(sent: Sent, method: str) -> set[Cand]:
    if method == "surface":
        return surface_candidates(sent)
    if method == "dependency":
        return dependency_candidates(sent)
    raise ValueError(f"unknown method {method!r}")


@dataclass
class CandStat:
    count: int = 0                       # frequency after deduplication
    raw: int = 0                         # frequency before deduplication
    contexts: set[str] = field(default_factory=set)
    example: str = ""


@dataclass
class Collection:
    method: str
    stats: dict[Cand, CandStat] = field(default_factory=dict)
    unigrams: Counter = field(default_factory=Counter)   # lemma -> count (dedup corpus)
    n_tokens: int = 0                    # usable tokens, dedup corpus
    n_tokens_raw: int = 0                # usable tokens, before dedup
    n_cands: int = 0                     # total candidate occurrences (all patterns)


def collect(annotated: Iterable[AnnotatedText], method: str) -> Collection:
    col = Collection(method)
    for at in annotated:
        raw = max(at.src.n_raw, 1)
        for sent in at.sents:
            usable = [t.lemma for t in sent.toks if t.ok]
            col.unigrams.update(usable)
            col.n_tokens += len(usable)
            col.n_tokens_raw += len(usable) * raw
            for c in extract_from_sentence(sent, method):
                st = col.stats.get(c)
                if st is None:
                    st = col.stats[c] = CandStat(example=sent.text[:300])
                st.count += 1
                st.raw += raw
                st.contexts |= at.src.contexts
                col.n_cands += 1
    return col
