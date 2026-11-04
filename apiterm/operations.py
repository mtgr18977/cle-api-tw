"""operationId corpus, name corpus and verb agreement (research questions 3-4)."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from .annotate import AnnotatedText, Sent
from .clean import clean_text, split_identifier, text_hash
from .extract import TextItem
from .triage import verb_class


HTTP_WORDS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "trace"})


def operation_id_words(op_id: str) -> list[str]:
    """Words of an operationId whose first word is its verb; [] if it carries no verb.

    Conventions seen in real specs:
    * GitHub ``repos/list-for-org``: the verb is in the segment after the last ``/``
      (the first segment is the API group).
    * Stripe ``PostAccountLinks``: PascalCase with the HTTP method as prefix, which is not
      a verb of the operation, so no verb is available.
    * Kubernetes ``listCoreV1ComponentStatus``: camelCase, the first word is the verb.
    """
    seg = op_id.rsplit("/", 1)[-1]
    words = split_identifier(seg)
    if not words:
        return []
    if seg[:1].isupper() and words[0].lower() in HTTP_WORDS:
        return []
    return words


def operation_verbs(items: Iterable[TextItem], nlp) -> list[dict]:
    """operationId -> (verb, object words). The first word is taken as the verb."""
    rows: Counter = Counter()
    ctxs: dict[tuple, set] = defaultdict(set)
    for it in items:
        if it.kind != "operationId":
            continue
        words = operation_id_words(it.text)
        if len(words) < 2:
            continue
        verb = _lemma(words[0], nlp)
        key = (verb, " ".join(words[1:]).lower())
        rows[key] += 1
        ctxs[key].add(it.context)
    return [{"verb": v, "object": o, "freq": n, "contexts": len(ctxs[(v, o)])}
            for (v, o), n in rows.most_common()]


_LEMMA_CACHE: dict[tuple[int, str], str] = {}


def _lemma(word: str, nlp) -> str:
    key = (id(nlp), word.lower())
    if key not in _LEMMA_CACHE:
        doc = nlp(f"to {word.lower()} it")      # a verbal frame so the lemmatiser sees a verb
        _LEMMA_CACHE[key] = next((t.lemma_.lower() for t in doc if t.text.lower() == word.lower()),
                                 word.lower())
    return _LEMMA_CACHE[key]


def name_terms(items: Iterable[TextItem]) -> list[dict]:
    """Property/parameter names split into words: unigrams and bigrams (no syntax)."""
    cnt: Counter = Counter()
    ctx: dict[str, set] = defaultdict(set)
    for it in items:
        if it.kind not in ("property", "parameter"):
            continue
        w = split_identifier(it.text)
        grams = [" ".join(w[i:i + n]) for n in (1, 2) for i in range(len(w) - n + 1)]
        for g in set(grams):
            cnt[g] += 1
            ctx[g].add(it.context)
    return [{"term": t, "n_words": t.count(" ") + 1, "freq": n, "contexts": len(ctx[t])}
            for t, n in cnt.most_common()]


def _root_verb(sent: Sent) -> str | None:
    for i, t in enumerate(sent.toks):
        if t.head == i and t.ok and t.pos == "VERB":
            return t.lemma
    for t in sent.toks:
        if t.ok and t.pos == "VERB":
            return t.lemma
    return None


def verb_agreement(items: Iterable[TextItem], annotated: list[AnnotatedText], nlp) -> list[dict]:
    """Does the verb of summary/description match the verb of operationId? (RQ4)"""
    by_key = {a.src.key: a for a in annotated}
    ops: dict[str, dict] = defaultdict(dict)
    for it in items:
        if it.kind in ("operationId", "summary", "description") and " " in it.context \
                and it.context.split(" ", 1)[0].isupper():
            ops[it.context].setdefault(it.kind, it.text)
    rows = []
    for ctx, d in ops.items():
        if "operationId" not in d:
            continue
        words = operation_id_words(d["operationId"])
        if not words:
            rows.append({"operation": ctx, "operationId": d["operationId"], "id_verb": "",
                         "doc_source": "", "doc_verb": "", "status": "no_id_verb"})
            continue
        id_verb = _lemma(words[0], nlp)
        src_kind = "summary" if "summary" in d else "description" if "description" in d else None
        doc_verb = None
        if src_kind:
            at = by_key.get(text_hash(clean_text(d[src_kind])))
            if at and at.sents:
                doc_verb = _root_verb(at.sents[0])
        if doc_verb is None:
            status = "no_verb"
        elif doc_verb == id_verb:
            status = "same"
        elif verb_class(doc_verb) and verb_class(doc_verb) == verb_class(id_verb):
            status = "same_class"
        else:
            status = "different"
        rows.append({"operation": ctx, "operationId": d["operationId"], "id_verb": id_verb,
                     "doc_source": src_kind or "", "doc_verb": doc_verb or "", "status": status})
    return rows
