"""Stream an English sample of CC-News into a local .jsonl (one {"text": ...} per line).

Source: https://huggingface.co/datasets/stanford-oval/ccnews (yearly configs, `language` field).
Only the text needed for counting is kept; the output is NOT meant to be published
(reference/data/*.jsonl is git-ignored). Publish the counts table instead.

    python reference/fetch_ccnews.py --years 2019 2020 2021 --per-year 400000 \
        --out reference/data/ccnews_sample.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_WS = re.compile(r"\s+")


def main() -> None:
    from datasets import load_dataset
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", default=["2019", "2020", "2021"])
    ap.add_argument("--per-year", type=int, default=400_000, help="English articles kept per year")
    ap.add_argument("--min-score", type=float, default=0.9, help="min language_score")
    ap.add_argument("--max-chars", type=int, default=6000, help="truncate very long articles")
    ap.add_argument("--out", default="reference/data/ccnews_sample.jsonl")
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    seen: set[int] = set()
    with out.open("w", encoding="utf-8") as fh:
        for year in a.years:
            kept = 0
            ds = load_dataset("stanford-oval/ccnews", name=year, split="train", streaming=True)
            for r in ds:
                try:
                    score = float(r.get("language_score") or 0)     # stored as a string
                except ValueError:
                    continue
                if r.get("language") != "en" or score < a.min_score:
                    continue
                text = _WS.sub(" ", r.get("plain_text") or "").strip()[:a.max_chars]
                h = hash(text)
                if len(text) < 200 or h in seen:
                    continue
                seen.add(h)
                fh.write(json.dumps({"text": text}) + "\n")
                kept += 1
                if kept >= a.per_year:
                    break
            print(f"{year}: kept {kept}")


if __name__ == "__main__":
    main()
