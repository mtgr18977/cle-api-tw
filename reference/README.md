# Reference corpus (milestone M3)

**Chosen corpus:** English sample of **CC-News** (Common Crawl news archive, collected with news-please),
via the Hugging Face mirror [`stanford-oval/ccnews`](https://huggingface.co/datasets/stanford-oval/ccnews).
Decision (repository owner): publish the *counts table* with the news-please citation, see `../CITATION.md`
for the citation and the caveats (a citation is attribution, not a licence).

```bash
pip install datasets
# 1. stream an English sample (text stays local, git-ignored)
python reference/fetch_ccnews.py --years 2019 --per-year 30000 --out reference/data/ccnews_2019.jsonl
# 2. build the counts table with the SAME spaCy model and patterns used for the API text
python -m apiterm build-reference reference/data/ --processes 4 --min-count 2 \
    --out reference/data/ccnews_en.db --source "CC-News en sample (stanford-oval/ccnews)" \
    --citation "Hamborg et al. 2017, news-please, doi:10.5281/zenodo.4120316"
```

## Built table (committed: `data/ccnews_en_min5.db`, 17.7 MB)

| Item | Value |
|---|---|
| Source | CC-News, English (`language == en`, `language_score >= 0.9`), 30,000 articles per year for 2019, 2020, 2021 (first matching records of each yearly config; not a random sample) |
| Articles after exact deduplication | 89,991 (about 234 MB of text, not published) |
| Candidate occurrences | 6,666,698 (surface), 9,366,011 (dependency) |
| Stored rows | 489,648 candidates with count >= 5 (full table: 1.64M rows with count >= 2, kept local as `*_full.db`) |
| Model | spaCy `en_core_web_sm` 3.8, same patterns and overrides as the domain corpus |

Reading the table: because of the pruning, a lookup of **0 means 0 to 4 occurrences** in the sample.
Totals include the pruned candidates, so relative frequencies stay correct.
Rebuild the pruned table from a full one with
`python -m apiterm prune-reference reference/data/ccnews_en_full.db --min-count 5 --out reference/data/ccnews_en_min5.db`.

Limits to report: 90k articles is small next to the plan's goal (millions); articles are the first records of
each yearly config, so the sample may over-represent early crawl days and some publishers; there is no per-publisher
balancing; the English filter is the dataset's own language score.

Throughput measured on 4 cores / en_core_web_sm: about 18 articles/s per process for annotation, and about
12 English articles/s per stream for download (most records are not English). Counts are held in memory
while building, so very large corpora should be built in shards.
`--min-count 2` keeps the published table small; totals still include the dropped singletons.
