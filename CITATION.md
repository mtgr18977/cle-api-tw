# Citation and data notice

## Reference corpus

The reference table counts word combinations in an English sample of **CC-News**, news articles from
the Common Crawl news archive, collected with news-please. If you use or redistribute that table, cite:

```bibtex
@InProceedings{Hamborg2017,
  author     = {Hamborg, Felix and Meuschke, Norman and Breitinger, Corinna and Gipp, Bela},
  title      = {news-please: A Generic News Crawler and Extractor},
  year       = {2017},
  booktitle  = {Proceedings of the 15th International Symposium of Information Science},
  location   = {Berlin},
  doi        = {10.5281/zenodo.4120316},
  pages      = {218--223},
  month      = {March}
}
```

## What is published

Only aggregate counts `(method, pattern, lemma combination, frequency)` and totals. No article text,
URLs, titles or publisher names are stored. Rare combinations (below `min_count`) are dropped.

## Caveats

* The citation is attribution, **not a licence**. Common Crawl's
  [Terms of Use](https://commoncrawl.org/terms-of-use) do not address derived statistics, and
  the articles remain the property of their publishers. The decision to publish the counts was made
  by the repository owner; this is not legal advice. If a rights holder or Common Crawl objects, remove the table.
* Source and sampling parameters are stored in the table metadata (`Reference.describe()`).
