import csv
import json

import pytest

from apiterm.cli import main
from apiterm.evaluation import evaluate, make_sample
from apiterm.report import render_report


def fake_rows(n=120):
    tiers = ["1"] * 30 + ["2"] * 20 + ["general"] * 30 + ["noise"] * 40
    return [{"rank": str(i + 1), "tier": tiers[i], "pattern": "N+N", "candidate": f"w{i} x", "freq": "5",
             "contexts": "2", "t_score": "2.5", "log_likelihood": "9", "example": "e"} for i in range(n)]


def test_sample_is_stratified_seeded_and_contains_topk():
    a = make_sample(fake_rows(), n=60, seed=1, top_k=20)
    b = make_sample(fake_rows(), n=60, seed=1, top_k=20)
    assert a == b and 55 <= len(a) <= 66
    assert [int(r["rank"]) for r in a[:20]] == list(range(1, 21))
    assert {r["tier"] for r in a} == {"1", "2", "general", "noise"}
    assert all(r["label"] == "" for r in a)


def test_evaluate_precision_per_tier_and_at_k():
    rows = make_sample(fake_rows(), n=60, seed=1, top_k=20)
    for r in rows:
        r["label"] = {"1": "cle", "2": "doubtful", "general": "not", "noise": "not"}[r["tier"]]
    for r in rows[:5]:
        r["label"] = "not"                                  # 5 errors in the top 5 (all tier 1)
    ev = evaluate(rows)
    t1 = ev["per_tier"]["1"]
    assert t1["precision_strict"] == pytest.approx(t1["cle"] / t1["annotated"])
    assert ev["per_tier"]["2"]["precision_strict"] == 0 and ev["per_tier"]["2"]["precision_lenient"] == 1
    assert ev["precision_at_k"][10] == 0.5 and ev["precision_at_k"][20] == pytest.approx(15 / 20)
    assert ev["precision_at_k"][50] is None                # top 50 not fully annotated


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
    assert main(["sample", str(out), "--n", "30", "--top-k", "5"]) == 0
    assert (out / "annotation_sample_surface.csv").exists()
    assert main(["analyze", str(tmp_path / "missing.yaml")]) == 1


def test_report_without_reference(tmp_path, sample_spec, nlp):
    from apiterm.pipeline import analyze, write_outputs
    write_outputs(analyze(sample_spec, None, nlp), tmp_path)
    p = render_report(tmp_path, tmp_path / "r.html")
    assert "no reference" in p.read_text().lower() or "No reference" in p.read_text()
