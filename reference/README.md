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

Throughput measured on 4 cores / en_core_web_sm: about 18 articles/s per process for annotation, and about
12 English articles/s per stream for download (most records are not English). Counts are held in memory
while building, so very large corpora should be built in shards.
`--min-count 2` keeps the published table small; totals still include the dropped singletons.
