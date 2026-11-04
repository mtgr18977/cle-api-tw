"""Cleaning and deduplication (plan sections 4.2 and 4.3)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable

from .extract import DOMAIN_KINDS, TextItem

_FENCE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
_INLINE = re.compile(r"`([^`\n]*)`")
_IDENT = re.compile(r"^[A-Za-z_][\w.\-]*$")
_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_REFLINK = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
_URL = re.compile(r"https?://\S+|www\.\S+")
_HTML = re.compile(r"<[^>]+>")
_LITERAL = re.compile(r"(?<!\w)(\"[^\"\s]+\"|'[^'\s]+')(?!\w)")
_BOLD = re.compile(r"(\*\*|__)(.+?)\1")
_ITALIC_STAR = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_ITALIC_US = re.compile(r"(?<![\w])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w])")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_BLOCKISH = re.compile(r"^\s*(?:[-*+>]|\d+[.)]|#{1,6}|\|)")
_END_PUNCT = re.compile(r"[.!?:;]$")
_WS = re.compile(r"\s+")


def clean_text(raw: str) -> str:
    """Strip Markdown/HTML/code/URLs/literal values; keep prose.

    Inline code that looks like an identifier (``access_token``) is kept without
    backticks so the annotator can treat it as an atomic identifier; other inline
    code (values, paths, JSON) is dropped.
    """
    s = _FENCE.sub(" ", raw)
    s = _INLINE.sub(lambda m: f" {m.group(1).strip()} " if _IDENT.match(m.group(1).strip()) else " ", s)
    s = _IMG.sub(" ", s)
    s = _LINK.sub(r"\1", s)
    s = _REFLINK.sub(r"\1", s)
    s = _URL.sub(" ", s)
    s = _HTML.sub(" ", s)
    s = _LITERAL.sub(" ", s)
    s = _BOLD.sub(r"\2", s)
    s = _ITALIC_STAR.sub(r"\1", s)
    s = _ITALIC_US.sub(r"\1", s)
    # Lines: bullets/headings/table rows are their own sentence; plain wrapped lines join.
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            text = " ".join(buf).strip()
            if text:
                out.append(text if _END_PUNCT.search(text) else text + ".")
            buf.clear()

    for line in s.splitlines():
        if not line.strip():
            flush()
            continue
        if _BLOCKISH.match(line):
            flush()
            line = _HEADING.sub("", _BULLET.sub("", line)).replace("|", " ").lstrip("> ")
            if line.strip():
                buf.append(line.strip())
            flush()
        else:
            buf.append(line.strip())
    flush()
    return _WS.sub(" ", " ".join(out)).strip()


_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_VERSION = re.compile(r"^v\d+$", re.I)


def split_identifier(name: str) -> list[str]:
    """``createAccessToken`` / ``create_access_token`` -> ['create','access','token'].

    All-uppercase acronyms (``API``) are kept as is; version tokens (``v1``) are dropped.
    """
    words: list[str] = []
    for part in re.split(r"[^A-Za-z0-9]+", name):
        for w in _CAMEL.split(part):
            if not w or _VERSION.match(w) or w.isdigit():
                continue
            words.append(w if (w.isupper() and len(w) > 1) else w.lower())
    return words


def norm_key(text: str) -> str:
    return _WS.sub(" ", text.strip().lower())


def text_hash(text: str) -> str:
    return hashlib.sha1(norm_key(text).encode("utf-8")).hexdigest()


@dataclass
class CorpusText:
    text: str
    key: str                       # hash of normalised text
    kinds: set[str] = field(default_factory=set)
    contexts: set[str] = field(default_factory=set)
    n_raw: int = 0                 # occurrences before deduplication


@dataclass
class DedupStats:
    items_before: int = 0          # domain items with non-empty text after cleaning
    items_after: int = 0           # unique texts
    chars_before: int = 0
    chars_after: int = 0

    @property
    def removed(self) -> int:
        return self.items_before - self.items_after


def deduplicate(items: Iterable[TextItem], kinds: tuple[str, ...] = DOMAIN_KINDS
                ) -> tuple[list[CorpusText], DedupStats]:
    """Clean domain texts and drop identical ones, remembering where they occurred."""
    uniq: dict[str, CorpusText] = {}
    st = DedupStats()
    for it in items:
        if it.kind not in kinds:
            continue
        txt = clean_text(it.text)
        if not any(c.isalpha() for c in txt):
            continue
        st.items_before += 1
        st.chars_before += len(txt)
        h = text_hash(txt)
        ct = uniq.get(h)
        if ct is None:
            ct = uniq[h] = CorpusText(txt, h)
            st.items_after += 1
            st.chars_after += len(txt)
        ct.n_raw += 1
        ct.kinds.add(it.kind)
        ct.contexts.add(it.context)
    return list(uniq.values()), st
