"""Static HTML report (dark theme, inline SVG, no external assets) - plan section 6."""
from __future__ import annotations

import csv
import json
from html import escape as e
from math import log10
from pathlib import Path

from .candidates import PATTERNS

TIER_COLORS = {"1": "#56b4e9", "2": "#e69f00", "general": "#8b949e", "noise": "#4b5563", "n/a": "#56b4e9"}
TIER_NAMES = {"1": "CLE candidate", "2": "Human review", "general": "General collocation",
              "noise": "Noise", "n/a": "Cohesive-only (no reference)"}

CSS = """
:root{--bg:#0d1117;--card:#161b22;--line:#30363d;--fg:#e6edf3;--mut:#8b949e;--acc:#56b4e9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.7rem;margin:.2em 0}
h2{margin-top:2.2em;border-bottom:1px solid var(--line);padding-bottom:.3em}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.card b{display:block;font-size:1.5rem}.card span,.mut{color:var(--mut);font-size:.85rem}
table{border-collapse:collapse;width:100%;font-size:.9rem;margin:.6em 0}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto}svg{max-width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}
svg text{fill:var(--fg);font:12px system-ui,sans-serif}svg .mut{fill:var(--mut)}
.bar{display:inline-block;height:10px;border-radius:2px;background:var(--acc);vertical-align:middle;margin-right:6px}
code{background:var(--card);padding:1px 5px;border-radius:4px}
.note{border-left:3px solid var(--acc);padding:4px 12px;background:var(--card);color:var(--mut)}
"""


def _csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _table(headers: list[tuple[str, str]], rows: list[list], numeric: set[int] = frozenset()) -> str:
    th = "".join(f'<th class="{"n" if i in numeric else ""}">{e(h)}</th>' for i, (h, _) in enumerate(headers))
    body = "".join("<tr>" + "".join(f'<td class="{"n" if i in numeric else ""}">{c}</td>'
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="wrap"><table><tr>{th}</tr>{body}</table></div>'


def _pattern_chart(by_pattern: dict, by_tier1: dict) -> str:
    w, h, left, bar_h, gap = 640, 40 + 38 * len(PATTERNS), 90, 16, 22
    mx = max([by_pattern.get(p, 0) for p in PATTERNS] + [1])
    sc = (w - left - 140) / mx
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Candidates per pattern">']
    for i, p in enumerate(PATTERNS):
        y = 20 + i * 38
        tot, t1 = by_pattern.get(p, 0), by_tier1.get(p, 0)
        out.append(f'<text x="8" y="{y + 13}">{e(p)}</text>')
        out.append(f'<rect x="{left}" y="{y}" width="{max(tot * sc, 1):.1f}" height="{bar_h}" fill="#4b5563" rx="2"/>')
        if t1:
            out.append(f'<rect x="{left}" y="{y}" width="{t1 * sc:.1f}" height="{bar_h}" fill="{TIER_COLORS["1"]}" rx="2"/>')
        out.append(f'<text class="mut" x="{left + tot * sc + 6:.1f}" y="{y + 13}">{tot} ({t1} tier 1)</text>')
    out.append("</svg>")
    return "".join(out)


def _scatter(rows: list[dict], cap: int = 4000) -> str:
    pts = [(float(r["t_score"]), float(r["log_likelihood"]), r["tier"]) for r in rows if r.get("log_likelihood")]
    pts = pts[:cap]
    if not pts:
        return '<p class="note">No reference table was used, so there is no specificity axis.</p>'
    w, h, L, B, T, R = 640, 400, 56, 40, 14, 14
    sy = lambda v: (1 if v >= 0 else -1) * log10(1 + abs(v))            # symmetric log
    xs, ys = [p[0] for p in pts], [sy(p[1]) for p in pts]
    x0, x1 = min(xs + [0]), max(xs + [3])
    y0, y1 = min(ys + [-0.5]), max(ys + [1])
    X = lambda v: L + (v - x0) / (x1 - x0) * (w - L - R)
    Y = lambda v: T + (1 - (v - y0) / (y1 - y0)) * (h - T - B)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Cohesion versus specificity">']
    tx = X(2.0)
    out.append(f'<line x1="{tx:.1f}" x2="{tx:.1f}" y1="{T}" y2="{h - B}" stroke="#8b949e" stroke-dasharray="4 4"/>')
    ty = Y(sy(3.84))
    out.append(f'<line x1="{L}" x2="{w - R}" y1="{ty:.1f}" y2="{ty:.1f}" stroke="#8b949e" stroke-dasharray="4 4"/>')
    for (tv, lv, tier), yv in zip(pts, ys):
        out.append(f'<circle cx="{X(tv):.1f}" cy="{Y(yv):.1f}" r="3" fill="{TIER_COLORS.get(tier, "#8b949e")}" fill-opacity=".75"/>')
    out.append(f'<text x="{L}" y="{h - 10}" class="mut">t-score (cohesion) →   dashed: t = 2</text>')
    out.append(f'<text x="8" y="{T + 10}" class="mut" transform="rotate(-90 12 {h / 2})" text-anchor="middle">signed log-likelihood (symlog) ↑</text>')
    out.append("</svg>")
    legend = " ".join(f'<span><span class="bar" style="width:10px;background:{TIER_COLORS[t]}"></span>{e(TIER_NAMES[t])}</span>'
                      for t in ("1", "2", "general", "noise"))
    return "".join(out) + f'<p class="mut">{legend}</p>'


def render_report(out_dir: str | Path, html_path: str | Path = "report/index.html",
                  title: str = "APITerm report", method: str = "dependency") -> Path:
    d = Path(out_dir)
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    ms = summary["methods"]
    if method not in ms:
        method = next(iter(ms))
    rows = _csv(d / f"candidates_{method}.csv")
    dd, m = summary["dedup"], ms[method]
    ref = summary.get("reference")
    parts = [f"<h1>{e(title)}</h1>",
             f'<p class="mut">Primary method: <b>{e(method)}</b>. Reference corpus: '
             f'{e(ref["source"]) if ref else "none (cohesion only)"}.</p>']

    cards = [(summary["items_total"], "text items extracted"), (dd["items_after"], "unique texts"),
             (m["distinct_candidates"], "distinct candidates"), (m["main_list"], "after frequency filter"),
             (m["by_tier"].get("1", 0), "tier 1 (CLE candidates)")]
    parts.append('<div class="cards">' + "".join(f'<div class="card"><b>{n:,}</b><span>{e(t)}</span></div>' for n, t in cards) + "</div>")

    parts.append("<h2>1. Deduplication</h2>")
    pct = lambda a, b: f"{(1 - a / b) * 100:.1f}%" if b else "–"
    parts.append(_table([("", ""), ("Before", ""), ("After", ""), ("Reduction", "")], [
        ["Texts", f'{dd["items_before"]:,}', f'{dd["items_after"]:,}', pct(dd["items_after"], dd["items_before"])],
        ["Characters", f'{dd["chars_before"]:,}', f'{dd["chars_after"]:,}', pct(dd["chars_after"], dd["chars_before"])],
        ["Usable tokens", f'{m["tokens_raw"]:,}', f'{m["tokens_dedup"]:,}', pct(m["tokens_dedup"], m["tokens_raw"])],
    ], {1, 2, 3}))
    top_inflated = sorted((r for r in rows), key=lambda r: int(r["raw_freq"]) - int(r["freq"]), reverse=True)[:8]
    if top_inflated and int(top_inflated[0]["raw_freq"]) > int(top_inflated[0]["freq"]):
        parts.append("<p>Candidates most inflated by repeated descriptions:</p>" + _table(
            [("Candidate", ""), ("Raw", ""), ("Dedup", ""), ("Contexts", "")],
            [[e(r["candidate"]), r["raw_freq"], r["freq"], r["contexts"]] for r in top_inflated], {1, 2, 3}))

    parts.append("<h2>2. Candidates by pattern</h2>" + _pattern_chart(m["by_pattern"], m["by_pattern_tier1"]))
    parts.append("<h2>3. Cohesion × specificity</h2>" + _scatter(rows))
    tiers = m["by_tier"]
    parts.append(_table([("Tier", ""), ("Candidates", "")],
                        [[e(TIER_NAMES.get(t, t)), n] for t, n in sorted(tiers.items())], {1}))

    t1 = [r for r in rows if r["tier"] in ("1", "n/a")]
    parts.append("<h2>4. Top candidates per pattern</h2>")
    for p in PATTERNS:
        sel = [r for r in t1 if r["pattern"] == p][:10]
        if sel:
            parts.append(f"<h3>{e(p)}</h3>" + _table(
                [("Candidate", ""), ("Freq", ""), ("Contexts", ""), ("t", ""), ("LL", "")],
                [[e(r["candidate"]), r["freq"], r["contexts"], r["t_score"], r["log_likelihood"] or "–"] for r in sel],
                {1, 2, 3, 4}))

    var = _csv(d / f"variation_{method}.csv")
    parts.append("<h2>5. Verb variation per noun</h2>")
    if var:
        mx = max(int(v["total_freq"]) for v in var)
        parts.append(_table(
            [("Noun", ""), ("Verbs : frequency", ""), ("Class", ""), ("Suggested", ""), ("Total", "")],
            [[e(v["noun"]), e(v["verbs"]), e(v["equivalent_class"]) or "–", e(v["suggested_preferred"]) or "–",
              f'<span class="bar" style="width:{int(80 * int(v["total_freq"]) / mx)}px"></span>{v["total_freq"]}']
             for v in var[:25]], {4}))
        parts.append('<p class="note">"Class" marks verbs from the same small semantic class '
                     "(e.g. create/generate/issue). It is a heuristic flag for human review, not proof of equivalence.</p>")
    else:
        parts.append("<p>No noun is combined with two or more verbs above the frequency threshold.</p>")

    va = summary.get("verb_agreement", {})
    if va:
        tot = sum(va.values())
        parts.append("<h2>6. operationId verb vs. description verb</h2>" + _table(
            [("Status", ""), ("Operations", ""), ("Share", "")],
            [[e(k), n, f"{n / tot * 100:.1f}%"] for k, n in sorted(va.items(), key=lambda kv: -kv[1])], {1, 2}))

    ov = summary.get("method_overlap")
    if ov:
        parts.append("<h2>7. Surface patterns vs. dependencies</h2>" + _table(
            [("Set", ""), ("Surface only", ""), ("Both", ""), ("Dependency only", ""), ("Jaccard", "")],
            [[e(k), v["a_only"], v["both"], v["b_only"], v["jaccard"] if v["jaccard"] is not None else "–"]
             for k, v in (("Main list", ov["main_list"]), ("Tier 1", ov["tier1"]))], {1, 2, 3, 4}))

    parts.append("<h2>8. Limitations</h2><ul>"
                 "<li>The reference corpus is journalistic English: politics/economy vocabulary can make some "
                 "combinations look less specialised than they are against everyday speech.</li>"
                 "<li>No gold standard: see the annotation sample and rule in the repository.</li>"
                 "<li>POS tagging of technical prose is imperfect; known fixes (<code>token</code>, text-initial "
                 "verbs) are applied and documented in <code>annotate.py</code>.</li>"
                 "<li>t ≥ 2 requires frequency ≥ 4 because t ≤ √c.</li></ul>")
    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>'
            f"<style>{CSS}</style></head><body><main>{''.join(parts)}</main></body></html>")
    out = Path(html_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
