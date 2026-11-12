"""Build the data files of the static analysis site (``site/``).

``site/index.html``, ``app.js`` and ``style.css`` are hand-written and committed; this module only
writes ``site/data/<api>.js`` and ``site/data/annotation.js`` from ``apiterm analyze`` output
directories, so the page works from Netlify and from ``file://`` (plain ``<script src>``, no fetch).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .evaluation import derived_stats, evaluate, read_csv

COLS = ["rank", "tier", "pattern", "candidate", "freq", "raw", "contexts", "t", "ll", "ref", "example"]
EXAMPLE_CHARS = 150


def _num(v: str):
    if v in ("", None):
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


def _rows(path: Path) -> list[list]:
    out = []
    for r in read_csv(path):
        out.append([int(r["rank"]), r["tier"], r["pattern"], r["candidate"], int(r["freq"]),
                    int(r["raw_freq"]), int(r["contexts"]), _num(r["t_score"]), _num(r["log_likelihood"]),
                    _num(r["ref_freq"]), r["example"][:EXAMPLE_CHARS]])
    return out


def _write_js(path: Path, expr: str, payload) -> None:
    path.write_text(f"{expr} = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n",
                    encoding="utf-8")


def build_api(out_dir: Path, name: str, site_data: Path, meta: dict) -> dict:
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    agreement = read_csv(out_dir / "verb_agreement.csv")
    payload = {
        "meta": meta, "summary": summary, "cols": COLS,
        "surface": _rows(out_dir / "candidates_surface.csv"),
        "dependency": _rows(out_dir / "candidates_dependency.csv"),
        "variation": {m: read_csv(out_dir / f"variation_{m}.csv") for m in ("surface", "dependency")},
        "agreement": {"counts": summary.get("verb_agreement", {}),
                      "rows": [[r["operationId"], r["id_verb"], r["doc_verb"], r["status"]]
                               for r in agreement if r["status"] not in ("same", "no_id_verb")]},
    }
    _write_js(site_data / f"{name}.js", f"window.APITERM.data[{json.dumps(name)}]", payload)
    return payload


def build_annotation(ann_dir: Path, site_data: Path) -> dict:
    sample = read_csv(ann_dir / "annotation_llm.csv")
    key = read_csv(ann_dir / "annotation_key.csv")
    kmap = {int(k["id"]): k for k in key}
    payload = {
        "rows": [{"api": r["api"], "pattern": r["pattern"], "candidate": r["candidate"], "label": r["label"],
                  "note": r["note"].removeprefix("[LLM] "), "stratum": kmap[int(r["id"])]["stratum"],
                  "tier": kmap[int(r["id"])]["tier"]} for r in sample],
        "evaluation": evaluate(sample, key),
        "derived": derived_stats(sample, key),
    }
    _write_js(site_data / "annotation.js", "window.APITERM.annotation", payload)
    return payload


def build_site(out_dirs: list[Path], ann_dir: Path | None, site_dir: Path, manifest: Path | None = None) -> list[Path]:
    site_data = site_dir / "data"
    site_data.mkdir(parents=True, exist_ok=True)
    specs = {}
    if manifest and manifest.exists():
        specs = {s["name"]: s for s in json.loads(manifest.read_text(encoding="utf-8"))["specs"]}
    written = []
    for d in out_dirs:
        name = d.name
        s = specs.get(name, {})
        build_api(d, name, site_data, {"domain": s.get("domain", ""), "repo": s.get("repo", ""),
                                       "commit": s.get("commit", "")[:7], "license": s.get("license", ""),
                                       "copyright": s.get("copyright", "")})
        written.append(site_data / f"{name}.js")
    if ann_dir and (ann_dir / "annotation_llm.csv").exists():
        build_annotation(ann_dir, site_data)
        written.append(site_data / "annotation.js")
    (site_data / "index.js").write_text(
        "window.APITERM = window.APITERM || {data: {}};\n"
        f"window.APITERM.apis = {json.dumps([d.name for d in out_dirs])};\n", encoding="utf-8")
    written.append(site_data / "index.js")
    return written
