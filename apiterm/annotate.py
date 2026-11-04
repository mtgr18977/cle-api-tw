"""Lemma / POS / dependency annotation with spaCy (plan section 4.3)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Iterator

from .clean import CorpusText

NOUN_POS = frozenset({"NOUN", "PROPN"})
_WORD = re.compile(r"[A-Za-z][A-Za-z\-']*")
_BAD_POS = frozenset({"PUNCT", "SPACE", "X", "NUM", "SYM"})
DEFAULT_MODEL = "en_core_web_sm"


@dataclass(slots=True)
class Tok:
    text: str
    lemma: str
    pos: str
    dep: str
    head: int      # index inside the sentence
    ok: bool       # usable word: alphabetic, not an identifier, not punctuation/number


@dataclass(slots=True)
class Sent:
    text: str
    toks: list[Tok]


@dataclass(slots=True)
class AnnotatedText:
    src: CorpusText
    sents: list[Sent]


def load_model(name: str = DEFAULT_MODEL):
    import spacy
    try:
        return spacy.load(name, disable=["ner"])
    except OSError as exc:
        raise RuntimeError(
            f"spaCy model '{name}' is not installed. Run: python -m spacy download {name}"
        ) from exc


def is_identifier(text: str) -> bool:
    """snake_case, camelCase, dotted or digit-bearing tokens are atomic identifiers."""
    return ("_" in text or "." in text.strip(".") or bool(re.search(r"[a-z][A-Z]", text))
            or (any(c.isdigit() for c in text) and any(c.isalpha() for c in text)))


def norm_lemma(text: str, lemma: str) -> str:
    """Lowercase lemmas, but keep acronyms (API, URL, JWT) intact."""
    if len(text) > 1 and text.isalpha() and text.isupper():
        return text
    return lemma.lower()


# --- Known weaknesses of the small English models on API prose, with transparent fixes ------
# 1) Domain nouns that spaCy tags as ADJ/VERB ("access token" -> token/VERB). Checked on
#    en_core_web_sm 3.8 and _md 3.8; extend via ``noun_overrides`` for your own domain.
NOUN_OVERRIDES = frozenset({"token", "identifier"})
_FIXABLE_POS = frozenset({"ADJ", "VERB", "ADV", "X", "INTJ", "AUX", "PROPN"})

# 2) Text-initial verbs in summaries ("List access tokens", "Returns a list ...") are often
#    tagged NOUN/PROPN. If a text starts with one of these verbs, a throw-away "Please"/"It"
#    is prepended before parsing and dropped afterwards.
API_VERBS = frozenset("""add allow append apply assign associate attach authenticate authorize cancel capture
change check clear close confirm connect contain convert copy create define delete deliver deny
detach disable download edit enable encrypt end enumerate execute expire export fetch filter find finalize
generate get grant import include invalidate invite issue link list load lock log make mark merge modify
move notify obtain open pay post produce provide publish query read receive refresh register reject
release remove rename replace report request reset resend resolve restore retrieve return revoke rotate
run save search send set show sign specify start stop store submit subscribe suspend sync test transfer
trigger unlink unlock update upload use validate verify view void write""".split())
_NO_FIX_NEXT = frozenset({"of", "is", "are", "was", "were", "to", "and", "or", "for", "in", "on"})
_FIRST = re.compile(r"\s*([A-Za-z]+)(?:\s+([A-Za-z]+))?")


def _lead_fix(text: str) -> tuple[str, int]:
    """Return (text to parse, number of leading helper tokens to drop afterwards)."""
    m = _FIRST.match(text)
    if not m:
        return text, 0
    w = m.group(1).lower()
    nxt = (m.group(2) or "").lower()
    if nxt in _NO_FIX_NEXT or not nxt:
        return text, 0
    t = text.lstrip()
    if w in API_VERBS:
        return "Please " + t[0].lower() + t[1:], 1
    for suf in ("es", "s"):
        if w.endswith(suf) and w[: -len(suf)] in API_VERBS:
            return "It " + t[0].lower() + t[1:], 1
    return text, 0


def _force_nouns(toks: list[Tok], overrides: frozenset[str]) -> None:
    """Re-tag mis-tagged domain nouns and repair the local dependency structure."""
    for i, t in enumerate(toks):
        low = t.text.lower()
        if low not in overrides and low.rstrip("s") not in overrides:
            continue
        if t.pos not in _FIXABLE_POS or not _WORD.fullmatch(t.text):
            continue
        t.pos = "NOUN"
        t.lemma = low[:-1] if low.endswith("s") and low[:-1] in overrides else low
        t.ok = True
        if i > 0 and t.head == i - 1 and toks[i - 1].ok and toks[i - 1].pos in NOUN_POS \
                and t.dep in ("amod", "acl", "advmod", "nmod", "appos", "relcl", "advcl", "dep"):
            prev = toks[i - 1]                       # "access token": token becomes the NP head
            t.head, t.dep = (prev.head, prev.dep) if prev.head != i - 1 else (i, "ROOT")
            for k, x in enumerate(toks):
                if k not in (i, i - 1) and x.head == i - 1:
                    x.head = i
            prev.head, prev.dep = i, "compound"


def _convert(doc, drop: int = 0, overrides: frozenset[str] = NOUN_OVERRIDES) -> list[Sent]:
    sents: list[Sent] = []
    for sp in doc.sents:
        kept = [t for t in sp if t.i >= drop]
        if not kept:
            continue
        local = {t.i: k for k, t in enumerate(kept)}
        toks = []
        for k, t in enumerate(kept):
            ok = (t.pos_ not in _BAD_POS and bool(_WORD.fullmatch(t.text))
                  and not is_identifier(t.text))
            toks.append(Tok(t.text, norm_lemma(t.text, t.lemma_), t.pos_, t.dep_,
                            local.get(t.head.i, k), ok))
        if overrides:
            _force_nouns(toks, overrides)
        sents.append(Sent(doc[kept[0].i:sp.end].text.strip(), toks))
    return sents


def annotate_strings(texts: Iterable[str], nlp, batch_size: int = 64,
                     overrides: frozenset[str] = NOUN_OVERRIDES) -> Iterator[list[Sent]]:
    pairs = (_lead_fix(t) for t in texts)            # streams: the reference corpus can be huge
    for doc, drop in nlp.pipe(pairs, batch_size=batch_size, as_tuples=True):
        yield _convert(doc, drop, overrides)


def annotate_texts(texts: list[CorpusText], nlp, batch_size: int = 64,
                   overrides: frozenset[str] = NOUN_OVERRIDES) -> list[AnnotatedText]:
    return [AnnotatedText(ct, s) for ct, s in
            zip(texts, annotate_strings((t.text for t in texts), nlp, batch_size, overrides))]
