# Reference corpus (milestone M3)

APITerm compares the OpenAPI text against a table of **counts** from general-language news.
The text itself is never stored or distributed, only `(method, pattern, candidate, frequency)`.

```bash
# 1. put news text in .txt (one text per line) or .jsonl ({"text": ...}) files
# 2. build the table with the SAME spaCy model and patterns used for the API text
python -m apiterm build-reference path/to/news/ --out reference/data/news.db --source "CC-News sample 2024"
```

**Not done yet / to verify (plan sections 3.2 and 10):** choose the corpus (e.g. CC-News), check its
licence and whether counts may be redistributed, deduplicate, and start with a small sample.
Counts are held in memory while building, so process very large corpora in shards.
`reference/data/` is git-ignored.
