"""Command line: ``apiterm analyze | build-reference | report | sample | evaluate``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .triage import Thresholds


def _cmd_analyze(a) -> int:
    from .pipeline import analyze, write_outputs
    from .reference import Reference
    ref = Reference(a.reference) if a.reference else None
    th = Thresholds(a.min_freq, a.t_min, a.ll_min)
    res = analyze(Path(a.spec).read_bytes(), ref, thresholds=th, methods=tuple(a.methods))
    paths = write_outputs(res, a.out)
    print(f"Wrote {len(paths)} files to {a.out}")
    for m, s in res.summary["methods"].items():
        print(f"  {m}: {s['main_list']} candidates ({s['by_tier']}), {s['negative_set']} in negative set")
    if ref is None:
        print("  (no --reference: specificity and 3-tier triage unavailable; cohesion only)")
    return 0


def _cmd_build_reference(a) -> int:
    from .annotate import load_model
    from .reference import build_reference, iter_texts
    meta = build_reference(iter_texts(a.inputs), a.out, load_model(), source=a.source,
                           citation=a.citation, min_count=a.min_count, processes=a.processes)
    print(json.dumps(meta, indent=2))
    return 0


def _cmd_prune_reference(a) -> int:
    from .reference import prune_reference
    print(json.dumps(prune_reference(a.src, a.out, a.min_count), indent=2))
    return 0


def _cmd_report(a) -> int:
    from .report import render_report
    p = render_report(a.out_dir, a.html, title=a.title, method=a.method)
    print(f"Wrote {p}")
    return 0


def _cmd_sample(a) -> int:
    from .evaluation import KEY_COLS, SAMPLE_COLS, make_sample, read_csv, write_csv
    apis = {}
    for d in a.out_dirs:
        d = Path(d)
        apis[d.name] = {"main": read_csv(d / "candidates_dependency.csv"),
                        "negatives": read_csv(d / "negatives_dependency.csv"),
                        "surface": read_csv(d / "candidates_surface.csv")}
    sample, key = make_sample(apis, a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(sample, out / "annotation_sample.csv", SAMPLE_COLS)
    write_csv(key, out / "annotation_key.csv", KEY_COLS)
    print(f"Wrote {len(sample)} candidates to {out}/annotation_sample.csv (blind) and annotation_key.csv.")
    print("Fill 'label' with: cle / generic / not / doubtful. See annotation/GUIDELINES.md.")
    return 0


def _cmd_evaluate(a) -> int:
    from .evaluation import evaluate, read_csv
    key = read_csv(a.key)
    print(json.dumps(evaluate(read_csv(a.annotated), key), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="apiterm", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("analyze", help="analyse an OpenAPI YAML/JSON file")
    s.add_argument("spec")
    s.add_argument("--reference", help="reference counts table (SQLite) from build-reference")
    s.add_argument("--out", default="out")
    s.add_argument("--methods", nargs="+", default=["surface", "dependency"],
                   choices=["surface", "dependency"])
    s.add_argument("--min-freq", type=int, default=2)
    s.add_argument("--t-min", type=float, default=2.0)
    s.add_argument("--ll-min", type=float, default=3.84)
    s.set_defaults(fn=_cmd_analyze)

    s = sub.add_parser("build-reference", help="build the reference counts table from text files")
    s.add_argument("inputs", nargs="+", help=".txt (one text per line) / .jsonl ({'text': ...}) files or dirs")
    s.add_argument("--out", required=True)
    s.add_argument("--source", default="unspecified", help="free-text provenance recorded in the table")
    s.add_argument("--citation", default="", help="citation string stored in the table metadata")
    s.add_argument("--min-count", type=int, default=1, help="store only candidates seen at least this often")
    s.add_argument("--processes", type=int, default=1, help="spaCy worker processes")
    s.set_defaults(fn=_cmd_build_reference)

    s = sub.add_parser("prune-reference", help="shrink a reference table to a publishable size")
    s.add_argument("src")
    s.add_argument("--out", required=True)
    s.add_argument("--min-count", type=int, required=True)
    s.set_defaults(fn=_cmd_prune_reference)

    s = sub.add_parser("report", help="render the static HTML report from an analyze output dir")
    s.add_argument("out_dir")
    s.add_argument("--html", default="report/index.html")
    s.add_argument("--title", default="APITerm report")
    s.add_argument("--method", default="dependency", choices=["surface", "dependency"])
    s.set_defaults(fn=_cmd_report)

    s = sub.add_parser("sample", help="write the blind, stratified annotation sample (3 APIs)")
    s.add_argument("out_dirs", nargs="+", help="analyze output dirs, one per API (dir name = API name)")
    s.add_argument("--out", default="annotation")
    s.add_argument("--seed", type=int, default=13)
    s.set_defaults(fn=_cmd_sample)

    s = sub.add_parser("evaluate", help="precision per stratum/tier and precision@k from an annotated sample")
    s.add_argument("annotated")
    s.add_argument("--key", default="annotation/annotation_key.csv")
    s.set_defaults(fn=_cmd_evaluate)

    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
