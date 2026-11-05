import csv
import json

import pytest

from apiterm.cli import main
from apiterm.report import render_report


def fake_api(n_main=200):
    rows = []
    for i in range(n_main):
        tier = "1" if i < 60 else "2" if i < 160 else "noise"
        freq = 12 if i < 40 else 5 if i < 100 else 2
        rows.append({"rank": str(i + 1), "tier": tier, "pattern": "N+N", "candidate": f"a{i} b{i}",
                     "freq": str(freq), "t_score": "2.5", "log_likelihood": "9", "example": f"ex {i}"})
    neg = [{"rank": "", "tier": "negative", "pattern": "N+N", "candidate": f"n{i} x", "freq": "1",
            "t_score": "0.5", "log_likelihood": "5", "example": "e"} for i in range(40)]
    surf = rows[:50] + [{"rank": str(900 + i), "tier": "2", "pattern": "V+N", "candidate": f"s{i} y", "freq": "3",
                         "t_score": "1.0", "log_likelihood": "6", "example": "e"} for i in range(30)]
    return {"main": rows, "negatives": neg, "surface": surf}


def test_sample_is_blind_shuffled_seeded_and_stratified():
    from apiterm.evaluation import make_sample
    apis = {"x": fake_api(), "y": fake_api()}
    s1, k1 = make_sample(apis, seed=1)
    s2, k2 = make_sample(apis, seed=1)
    assert s1 == s2 and k1 == k2
    assert set(s1[0]) == {"id", "api", "pattern", "candidate", "example", "label", "note"}   # blind
    assert all(r["label"] == "" for r in s1)
    strata = {(k["api"], k["stratum"]) for k in k1}
    assert len(strata) == 2 * 8
    assert [int(r["rank"]) for r in k1 if r["api"] == "x" and r["stratum"] == "top"].__len__() == 20
    w = next(k for k in k1 if k["stratum"] == "tier2_lo" and k["api"] == "x")
    assert float(w["weight"]) == pytest.approx(int(w["population"]) / int(w["sampled"]))
    assert all(k["in_surface"] is True for k in k1 if k["stratum"] == "top" and int(k["rank"]) <= 20)
    ids = [r["id"] for r in s1]
    assert ids == list(range(1, len(ids) + 1)) and [r["api"] for r in s1[:12]] != ["x"] * 12   # shuffled


def test_evaluate_weighted_precision_and_p_at_k():
    from apiterm.evaluation import evaluate, make_sample
    sample, key = make_sample({"x": fake_api()}, seed=1)
    kmap = {int(k["id"]): k for k in key}
    for r in sample:
        k = kmap[int(r["id"])]
        r["label"] = {"1": "cle", "2": "not", "noise": "not", "negative": "not"}[k["tier"]]
    top = sorted((k for k in key if k["stratum"] == "top"), key=lambda k: int(k["rank"]))
    for k in top[:2]:                                         # two errors in the top 5 positions
        next(r for r in sample if int(r["id"]) == int(k["id"]))["label"] = "generic"
    ev = evaluate(sample, key)
    assert ev["annotated_total"] == len(sample)
    assert ev["per_tier_weighted"]["1"]["weighted_precision_strict"] < 1.0
    assert ev["per_tier_weighted"]["2"]["weighted_precision_strict"] == 0.0
    assert ev["per_tier_weighted"]["1"]["weighted_precision_with_generic"] == 1.0
    assert ev["precision_at_k"]["x"][5] == pytest.approx(3 / 5)
    assert ev["precision_at_k"]["x"][20] == pytest.approx(18 / 20)
    assert "x/tier2_lo" in ev["per_stratum"]


def test_evaluate_ignores_unlabelled_rows():
    from apiterm.evaluation import evaluate, make_sample
    sample, key = make_sample({"x": fake_api()}, seed=1)
    sample[0]["label"] = "cle"
    ev = evaluate(sample, key)
    assert ev["annotated_total"] == 1 and ev["of"] == len(sample)
    assert ev["precision_at_k"] == {"x": {5: None, 10: None, 20: None}}   # top ranks not annotated


def test_cli_end_to_end_and_report(tmp_path, capsys, sample_spec, reference_db):
    spec = tmp_path / "s.yaml"
    spec.write_bytes(sample_spec)
    out = tmp_path / "out"
    assert main(["analyze", str(spec), "--reference", str(reference_db), "--out", str(out)]) == 0
    html = tmp_path / "r.html"
    assert main(["report", str(out), "--html", str(html), "--title", "T <x>"]) == 0
    page = html.read_text()
    assert "<svg" in page and "T &lt;x&gt;" in page and "Verb variation" in page
    assert "http://" not in page.replace("http://www.w3.org/2000/svg", "")   # no external assets
    ann = tmp_path / "ann"
    assert main(["sample", str(out), "--out", str(ann)]) == 0
    assert (ann / "annotation_sample.csv").exists() and (ann / "annotation_key.csv").exists()
    assert main(["analyze", str(tmp_path / "missing.yaml")]) == 1


def test_report_without_reference(tmp_path, sample_spec, nlp):
    from apiterm.pipeline import analyze, write_outputs
    write_outputs(analyze(sample_spec, None, nlp), tmp_path)
    p = render_report(tmp_path, tmp_path / "r.html")
    assert "no reference" in p.read_text().lower() or "No reference" in p.read_text()
