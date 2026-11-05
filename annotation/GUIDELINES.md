# Annotation guide (M5, plan section 5)

`annotation_sample.csv` has 300 candidates (100 per API: Stripe, GitHub, Kubernetes), shuffled and **blind**: no tier,
score or frequency is shown. Please do not open `annotation_key.csv` until you have finished.
Fill the `label` column (and `note` when useful), then run:

```bash
python -m apiterm evaluate annotation/annotation_sample.csv --key annotation/annotation_key.csv
```

Estimated effort: about 20-30 seconds per row, so around 2 hours; the ids can be done in sittings (1-100, 101-200, 201-300).
Decide once and do not go back to edit earlier rows; if your rule changes, note it in `note` and tell me.

## What you are judging

The **lemma combination as a unit** (`create token` stands for *creates a token*), read in the example sentence.
Use the sentence only to understand the sense. Ignore inflection and word order of the example.

## Labels

| Label | Meaning | Test | Examples |
|---|---|---|---|
| `cle` | A terminological combination of API/domain documentation: a concept name or a domain verb+object a writer should use consistently | Would it belong in the project glossary or style guide? Does replacing a word change the conventional wording? | *access token*, *payment method*, *pull request*, *webhook endpoint*, *attach payment method* |
| `generic` | A real, well-formed collocation typical of documentation writing, but not specific to the API's domain | Natural in any technical text; useful for a style guide, not for a glossary | *return list*, *more information*, *see for information*, *contain detail* |
| `not` | Not a unit | Accidental adjacency, free combination, parse or lemma artifact | *configuration specifie* (lemma error), *part of group* (free phrase), *parameter field* (invalid parse) |
| `doubtful` | You cannot decide | Say why in `note` | domain unclear, depends on sense |

`generic` is its own label on purpose. The first run showed tier 1 mixing generic documentation phrasing with true
terms, and I need your judgement to decide whether those should count as CLE. Evaluation reports precision both
strict (`cle` only) and with `generic`.

## Tie-breakers

* Proper names of the product (*Acme Auth*, *south korea*) are `not` unless they name a concept inside the API.
* Truncated or wrongly lemmatised forms (*datum* for *data*) are `not`; mention the artifact in `note`.
* One sense is enough: if it is a term in one common use in this API, label `cle` even if it is general elsewhere.
* A candidate that is part of a longer term (*personal access* from *personal access token*) is `not`, and the note
  "partial" helps me measure that pattern.

## Optional

A second annotator on ~10% of the rows (any 30 ids) would let us report agreement (Cohen's kappa).

## LLM pre-annotation (provisional)

At your request I (Claude) annotated all 300 rows **blind** (before opening `annotation_key.csv`) using the guide above:
`annotation_llm.csv` (labels 67 cle, 57 generic, 173 not, 3 doubtful; notes prefixed `[LLM]`) and the evaluation in
`eval_llm_provisional.json`. `annotation_sample.csv` is still empty for you.

This is **not a gold standard**: one annotator, the same one that helped define the rules, and no domain expertise
beyond what the examples show. Thresholds calibrated on it would measure agreement with me, not truth.
The cheapest way to find out how far to trust it:

1. Annotate `annotation_review60.csv` (60 random rows of the 300, about 25 minutes) without looking at `annotation_llm.csv`.
2. Run `python -m apiterm agree annotation/annotation_review60.csv annotation/annotation_llm.csv`.
   Cohen's kappa on `cle` vs. the rest tells us whether my labels are usable; the confusion counts show where we differ
   (probably `generic` and the partial terms).
3. Use your labels on those 60 to correct mine, or annotate more if the kappa is low.
