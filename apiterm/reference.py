"""Reference corpus as a table of pre-computed counts (plan sections 3.2 and 7.2).

Only counts are stored (method, pattern, candidate, frequency) plus totals, never the
text. Format: SQLite.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Iterable, Iterator

from .annotate import annotate_strings
from .candidates import METHODS, Cand, extract_from_sentence

SCHEMA = """
CREATE TABLE IF NOT EXISTS counts(method TEXT, pattern TEXT, key TEXT, n INTEGER,
                                  PRIMARY KEY(method, pattern, key));
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""


class Reference:
    def __init__(self, path: str | Path):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"reference table not found: {path}")
        self.path = path
        self._db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        self._totals = {m: int(self.meta(f"total_{m}", 0)) for m in METHODS}

    def meta(self, k: str, default=None):
        row = self._db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return row[0] if row else default

    def total(self, method: str) -> int:
        return self._totals[method]

    def count(self, method: str, cand: Cand) -> int:
        row = self._db.execute("SELECT n FROM counts WHERE method=? AND pattern=? AND key=?",
                               (method, cand.pattern, cand.key)).fetchone()
        return row[0] if row else 0

    def describe(self) -> dict:
        return {"path": self.path.name, "source": self.meta("source", "unknown"),
                "citation": self.meta("citation", ""), "min_count": int(self.meta("min_count", 1)),
                "texts": int(self.meta("texts", 0)),
                **{f"total_{m}": self._totals[m] for m in METHODS}}

    def close(self) -> None:
        self._db.close()


def iter_texts(paths: Iterable[str | Path]) -> Iterator[str]:
    """Yield text units from ``.txt`` (one per line) and ``.jsonl`` (``text`` field) files."""
    for p in map(Path, paths):
        files = sorted(p.rglob("*")) if p.is_dir() else [p]
        for f in files:
            if f.suffix == ".jsonl":
                with f.open(encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            t = json.loads(line).get("text")
                            if isinstance(t, str):
                                yield t
            elif f.suffix == ".txt":
                with f.open(encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            yield line.strip()


def build_reference(texts: Iterable[str], out_path: str | Path, nlp, *, source: str = "unspecified",
                    dedup: bool = True, batch_size: int = 64, citation: str = "",
                    min_count: int = 1, processes: int = 1) -> dict:
    """Annotate ``texts`` with the SAME model/patterns as the domain corpus and store counts.

    Exact duplicate text units are skipped (``dedup``), as for the domain corpus.
    Counts are kept in memory until the end: process very large corpora in shards.
    ``min_count`` drops rarer candidates from the stored table (totals still include them),
    which keeps a publishable table small. ``citation`` is stored in the table metadata.
    """
    seen: set[bytes] = set()

    def unique() -> Iterator[str]:
        for t in texts:
            if dedup:
                h = hashlib.blake2b(t.strip().lower().encode(), digest_size=12).digest()
                if h in seen:
                    continue
                seen.add(h)
            yield t

    counters = {m: Counter() for m in METHODS}
    totals = {m: 0 for m in METHODS}
    n_texts = 0
    # count texts on the fly while streaming through the pipeline
    def counted() -> Iterator[str]:
        nonlocal n_texts
        for t in unique():
            n_texts += 1
            yield t

    for sents in annotate_strings(counted(), nlp, batch_size, n_process=processes):
        for s in sents:
            for m in METHODS:
                for c in extract_from_sentence(s, m):
                    counters[m][c] += 1
                    totals[m] += 1

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    db = sqlite3.connect(out_path)
    db.executescript(SCHEMA)
    for m in METHODS:
        db.executemany("INSERT INTO counts VALUES (?,?,?,?)",
                       ((m, c.pattern, c.key, n) for c, n in counters[m].items() if n >= min_count))
    meta = {"source": source, "citation": citation, "min_count": min_count, "texts": n_texts, "model": getattr(nlp, "meta", {}).get("name", ""),
            **{f"total_{m}": totals[m] for m in METHODS}}
    db.executemany("INSERT INTO meta VALUES (?,?)", ((k, str(v)) for k, v in meta.items()))
    db.commit()
    db.close()
    return meta
