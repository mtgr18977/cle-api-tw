import csv
import json

import pytest

from apiterm.candidates import Cand, collect
from apiterm.annotate import annotate_texts
from apiterm.clean import deduplicate
from apiterm.extract import extract
from apiterm.pipeline import analyze, write_outputs
from apiterm.reference import Reference
from apiterm.triage import Thresholds, score_collection, variation_report


@pytest.fixture(scope="module")
def result(sample_spec, nlp, reference_db):
    return analyze(sample_spec, Reference(reference_db), nlp)


def test_reference_table_has_counts_not_text(reference_db):
    ref = Reference(reference_db)
    assert ref.total("surface") > 0 and ref.describe()["source"] == "synthetic test news"
    assert ref.count("surface", Cand("V+N", ("file", "lawsuit"))) == 30
    assert ref.count("surface", Cand("V+N", ("create", "token"))) == 0
    import sqlite3
    tables = {r[0] for r in sqlite3.connect(reference_db).execute("select name from sqlite_master")}
    assert "counts" in tables and not any("text" in t for t in tables)


def test_dedup_effect_visible_in_frequencies(sample_spec, nlp):
    texts, st = deduplicate(extract(sample_spec))
    assert st.removed >= 0
    col = collect(annotate_texts(texts, nlp), "dependency")
    assert all(s.raw >= s.count for s in col.stats.values())


def test_frequency_filter_and_negative_set(result):
    for m in ("surface", "dependency"):
        assert all(r["freq"] >= 2 for r in result.rows[m])
        assert result.negatives[m] and all(r["freq"] < 2 for r in result.negatives[m])
        assert all(r["tier"] == "negative" for r in result.negatives[m])


def test_three_tiers_and_thresholds(result):
    rows = result.rows["dependency"]
    for r in rows:
        assert r["tier"] in {"1", "2", "general", "noise"}
        cohesive = r["t_score"] >= 2.0
        specific = (r["log_likelihood"] or 0) >= 3.84
        want = ("1" if specific else "general") if cohesive else ("2" if specific else "noise")
        assert r["tier"] == want
        if cohesive:
            assert r["freq"] >= 4                      # t <= sqrt(c)
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
    tiers = [r["tier"] for r in rows]
    assert tiers == sorted(tiers, key=lambda t: {"1": 0, "2": 1, "general": 3, "noise": 4}[t])
    assert any(r["tier"] == "1" and r["candidate"] == "access token" for r in rows)


def test_without_reference_only_cohesion(sample_spec, nlp):
    res = analyze(sample_spec, None, nlp, methods=("surface",))
    assert {r["tier"] for r in res.rows["surface"]} == {"n/a"}
    assert res.rows["surface"][0]["log_likelihood"] is None


def test_variation_report_flags_equivalent_verbs(result):
    var = {v["noun"]: v for v in result.variation["dependency"]}
    assert "token" in var and var["token"]["equivalent_class"] == "create"
    assert var["token"]["suggested_preferred"] == "create"        # most frequent of create/generate
    assert "create:" in var["token"]["verbs"] and "generate:" in var["token"]["verbs"]


def test_variation_unit():
    base = dict(pattern="V+N", tier="1", contexts=1, log_likelihood=5.0)
    rows = [dict(base, candidate="create token", freq=41), dict(base, candidate="generate token", freq=12),
            dict(base, candidate="revoke token", freq=3), dict(base, candidate="get file", freq=9),
            dict(base, candidate="general noun", freq=9, tier="general")]
    (v,) = variation_report(rows)
    assert v["noun"] == "token" and v["verbs"] == "create:41; generate:12; revoke:3"
    assert v["equivalent_class"] == "create" and v["suggested_preferred"] == "create"


def test_operationid_corpus_and_agreement(result):
    assert {"verb": "create", "object": "access token"}.items() <= next(
        r for r in result.opid_verbs if r["object"] == "access token" and r["verb"] == "create").items()
    assert result.summary["verb_agreement"].get("same") == 11
    names = {r["term"] for r in result.name_terms}
    assert "token type" in names and "client id" in names


def test_method_overlap_and_outputs(result, tmp_path):
    ov = result.summary["method_overlap"]["main_list"]
    assert ov["both"] > 0 and 0 <= ov["jaccard"] <= 1
    paths = write_outputs(result, tmp_path)
    assert (tmp_path / "candidates_surface.csv").exists()
    with open(tmp_path / "candidates_dependency.csv", newline="") as fh:
        assert "log_likelihood" in next(csv.reader(fh))
    assert json.loads((tmp_path / "summary.json").read_text())["reference"]["source"] == "synthetic test news"
    assert len(paths) == 10


def test_reference_min_count_and_citation(tmp_path, nlp):
    from apiterm.reference import build_reference
    texts = ["The company will file a lawsuit."] * 3 + ["The mayor will delete the record."]
    db = tmp_path / "r.db"
    meta = build_reference(texts, db, nlp, source="s", citation="Hamborg2017", dedup=False, min_count=2)
    ref = Reference(db)
    d = ref.describe()
    assert d["citation"] == "Hamborg2017" and d["min_count"] == 2
    assert ref.count("surface", Cand("V+N", ("file", "lawsuit"))) == 3
    assert ref.count("surface", Cand("V+N", ("delete", "record"))) == 0       # pruned
    assert ref.total("surface") == meta["total_surface"] > 3                  # totals keep pruned counts


def test_prune_reference_keeps_totals(tmp_path, nlp):
    from apiterm.reference import build_reference, prune_reference
    texts = ["The company will file a lawsuit."] * 5 + ["The mayor will delete the record."]
    full, small = tmp_path / "f.db", tmp_path / "s.db"
    build_reference(texts, full, nlp, source="s", citation="c", dedup=False)
    info = prune_reference(full, small, 5)
    a, b = Reference(full), Reference(small)
    assert info["rows_kept"] < sum(1 for _ in a._db.execute("select 1 from counts"))
    assert b.count("surface", Cand("V+N", ("file", "lawsuit"))) == 5
    assert b.count("surface", Cand("V+N", ("delete", "record"))) == 0
    assert b.total("surface") == a.total("surface")
    assert b.describe()["citation"] == "c" and b.describe()["min_count"] == 5


@pytest.mark.parametrize("op_id,words", [
    ("repos/list-for-org", ["list", "for", "org"]),                  # GitHub: group/verb-...
    ("PostAccountLinks", []),                                        # Stripe: HTTP method prefix, no verb
    ("GetAccounts", []),
    ("listCoreV1ComponentStatus", ["list", "core", "component", "status"]),   # Kubernetes
    ("getCoreAPIVersions", ["get", "core", "API", "versions"]),      # lower-case get IS a verb here
    ("createAccessToken", ["create", "access", "token"]),
])
def test_operation_id_verb_conventions(op_id, words):
    from apiterm.operations import operation_id_words
    assert operation_id_words(op_id) == words
