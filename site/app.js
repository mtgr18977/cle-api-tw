"use strict";
(function () {
  const A = window.APITERM, D = A.data, APIS = A.apis.filter(a => D[a]);
  const IDX = {rank: 0, tier: 1, pattern: 2, candidate: 3, freq: 4, raw: 5, contexts: 6, t: 7, ll: 8, ref: 9, example: 10};
  const TIERS = ["1", "2", "general", "noise"];
  const TIER_NAME = {"1": "1 CLE candidate", "2": "2 human review", "general": "general", "noise": "noise", "n/a": "cohesion only"};
  const TIER_COLOR = {"1": "#56b4e9", "2": "#e69f00", "general": "#8b949e", "noise": "#6b7280", "n/a": "#56b4e9"};
  const API_COLOR = ["#009e73", "#cc79a7", "#f0e442", "#d55e00"];   // distinct from the tier colours
  const PATTERNS = ["V+N", "V+Prep+N", "N+N", "Adj+N", "N+of+N"];
  const S = {method: "dependency", reveal: false};
  const $ = id => document.getElementById(id);

  function el(tag, props, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (k === "class") e.className = v; else if (k.startsWith("on")) e[k] = v; else e.setAttribute(k, v);
    }
    for (const kid of kids.flat()) if (kid != null) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return e;
  }
  const NS = "http://www.w3.org/2000/svg";
  function sv(tag, props, ...kids) {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(props || {})) e.setAttribute(k, v);
    for (const kid of kids.flat()) if (kid != null) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return e;
  }
  const fmt = n => n == null ? "–" : (typeof n === "number" ? n.toLocaleString("en-US", {maximumFractionDigits: 3}) : n);
  const pct = x => x == null ? "–" : (x * 100).toFixed(1) + "%";
  const rows = (api, m = S.method) => D[api][m];
  const fill = (sel, opts) => { sel.replaceChildren(...opts.map(o => el("option", {value: o}, o))); };
  const th = (label, cls, onclick) => el("th", {class: cls || "", onclick}, label);
  const legend = items => el("div", {class: "legend"}, items.map(([c, t]) => el("span", {}, el("span", {class: "sw", style: "background:" + c}), t)));

  // ------------------------------------------------------------------ overview
  function drawOverview() {
    $("cards").replaceChildren(...APIS.map(api => {
      const d = D[api], s = d.summary, m = s.methods[S.method], dd = s.dedup, meta = d.meta;
      const kv = [["operationIds", fmt(s.items_by_kind.operationId)], ["Texts (raw → unique)", `${fmt(dd.items_before)} → ${fmt(dd.items_after)}`],
        ["Removed by dedup", pct(dd.removed / dd.items_before)], ["Main list", fmt(m.main_list)], ["Tier 1", fmt(m.by_tier["1"] || 0)],
        ["Below min. frequency", fmt(m.negative_set)]];
      return el("div", {class: "card"}, el("h3", {}, api[0].toUpperCase() + api.slice(1)),
        el("div", {class: "mut"}, `${meta.domain} · ${meta.license} · ${meta.commit}`),
        el("div", {class: "kv"}, kv.flat().map(x => el("span", {}, x))));
    }));
    const head = ["API", "Texts before", "Texts after", "Removed", "Tokens before", "Tokens after"];
    $("dedup").replaceChildren(el("table", {}, el("tr", {}, head.map((h, i) => th(h, i ? "n" : ""))),
      APIS.map(api => { const s = D[api].summary, dd = s.dedup, m = s.methods[S.method];
        return el("tr", {}, el("td", {}, api), [dd.items_before, dd.items_after].map(v => el("td", {class: "n"}, fmt(v))),
          el("td", {class: "n"}, pct(dd.removed / dd.items_before)),
          [m.tokens_raw, m.tokens_dedup].map(v => el("td", {class: "n"}, fmt(v)))); })));
    // stacked tier bars
    const W = 900, L = 110, bh = 26, H = 30 + APIS.length * 44;
    const svg = sv("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Candidates by tier"});
    const max = Math.max(...APIS.map(a => rows(a).length));
    const sc = (W - L - 80) / max;
    APIS.forEach((api, i) => {
      const y = 16 + i * 44; let x = L; const r = rows(api);
      svg.append(sv("text", {x: 8, y: y + 17}, api));
      const present = [...new Set(r.map(x => x[IDX.tier]))];
      (S.method && present.includes("n/a") ? ["n/a"] : TIERS).forEach(t => {
        const n = r.filter(x => x[IDX.tier] === t).length, w = n * sc;
        if (!n) return;
        svg.append(sv("rect", {x, y, width: Math.max(w, 1), height: bh, fill: TIER_COLOR[t], rx: 2}, sv("title", {}, `${TIER_NAME[t]}: ${n}`)));
        if (w > 38) svg.append(sv("text", {x: x + 5, y: y + 17, fill: "#04141f", style: "fill:#04141f"}, n));
        x += w;
      });
      svg.append(sv("text", {x: x + 6, y: y + 17, class: "m"}, fmt(r.length)));
    });
    $("tierchart").replaceChildren(svg, legend(TIERS.map(t => [TIER_COLOR[t], TIER_NAME[t]])));
  }

  // ------------------------------------------------------------------ findings
  function groupedBars(el0, cats, series, valueFmt, maxV, W = 900) {
    const H = 300, L = 46, B = 40, T = 14, gw = (W - L - 10) / cats.length;
    const svg = sv("svg", {viewBox: `0 0 ${W} ${H}`});
    for (let i = 0; i <= 4; i++) { const v = maxV * i / 4, y = T + (1 - i / 4) * (H - T - B);
      svg.append(sv("line", {x1: L, x2: W - 6, y1: y, y2: y, stroke: "#30363d"}), sv("text", {x: L - 6, y: y + 4, "text-anchor": "end", class: "m"}, valueFmt(v))); }
    cats.forEach((c, ci) => {
      const bw = Math.min(46, gw / (series.length + 1));
      series.forEach((s, si) => {
        const v = s.values[ci], h = (v / maxV) * (H - T - B), x = L + ci * gw + gw / 2 - (series.length * bw) / 2 + si * bw, y = H - B - h;
        svg.append(sv("rect", {x, y, width: bw - 3, height: Math.max(h, 0), fill: s.color, rx: 2}, sv("title", {}, `${s.name} · ${c}: ${valueFmt(v)} (n=${s.n[ci]})`)));
        svg.append(sv("text", {x: x + (bw - 3) / 2, y: y - 4, "text-anchor": "middle", class: "m"}, valueFmt(v)));
      });
      svg.append(sv("text", {x: L + ci * gw + gw / 2, y: H - 16, "text-anchor": "middle"}, c));
    });
    el0.replaceChildren(svg, legend(series.map(s => [s.color, s.name])));
  }
  function drawFindings() {
    const buckets = [["2–3", f => f <= 3], ["4–9", f => f >= 4 && f <= 9], ["10+", f => f >= 10]];
    groupedBars($("freqchart"), buckets.map(b => b[0]), APIS.map((api, i) => {
      const sub = buckets.map(([, fn]) => rows(api).filter(r => fn(r[IDX.freq])));
      return {name: api, color: API_COLOR[i], values: sub.map(s => s.length ? s.filter(r => r[IDX.tier] === "1").length / s.length : 0), n: sub.map(s => s.length)};
    }), v => Math.round(v * 100) + "%", 1, 460);
    groupedBars($("refzero"), ["count 0 in reference"], APIS.map((api, i) => {
      const r = rows(api); return {name: api, color: API_COLOR[i], values: [r.filter(x => x[IDX.ref] === 0).length / r.length], n: [r.length]};
    }), v => Math.round(v * 100) + "%", 1, 460);
    const counts = PATTERNS.map(p => APIS.map(api => rows(api).filter(r => r[IDX.pattern] === p).length));
    const mx = Math.max(...counts.flat(), 1);
    groupedBars($("patternchart"), PATTERNS, APIS.map((api, i) => ({name: api, color: API_COLOR[i], values: counts.map(c => c[i]), n: counts.map(c => c[i])})), v => fmt(Math.round(v)), Math.ceil(mx / 500) * 500);
  }

  // ------------------------------------------------------------------ annotation lookup
  const LABELS = new Map();
  if (A.annotation) A.annotation.rows.forEach(r => LABELS.set(`${r.api}|${r.pattern}|${r.candidate}`, r));

  // ------------------------------------------------------------------ explorer
  const E = {sort: "rank", dir: 1, shown: 200};
  function filteredRows() {
    const api = $("e-api").value, pat = $("e-pat").value, tier = $("e-tier").value, min = +$("e-min").value || 1, q = $("e-q").value.toLowerCase();
    let r = rows(api).filter(x => (!pat || x[IDX.pattern] === pat) && (!tier || x[IDX.tier] === tier) && x[IDX.freq] >= min &&
      (!q || x[IDX.candidate].toLowerCase().includes(q) || x[IDX.example].toLowerCase().includes(q)));
    const k = IDX[E.sort];
    r.sort((a, b) => { const x = a[k], y = b[k]; return (x === y ? 0 : x == null ? 1 : y == null ? -1 : x < y ? -1 : 1) * E.dir; });
    return r;
  }
  function drawExplorer() {
    const api = $("e-api").value, r = filteredRows();
    $("e-count").textContent = `${fmt(r.length)} candidates`;
    const cols = [["rank", "#", "n"], ["tier", "Tier", ""], ["pattern", "Pattern", ""], ["candidate", "Candidate", ""], ["freq", "Freq", "n"], ["raw", "Raw", "n"],
      ["contexts", "Ctx", "n"], ["t", "t", "n"], ["ll", "LL", "n"], ["ref", "Ref", "n"]];
    const head = el("tr", {}, cols.map(([k, l, c]) => th(l + (E.sort === k ? (E.dir > 0 ? " ▲" : " ▼") : ""), "s " + c,
      () => { E.dir = E.sort === k ? -E.dir : 1; E.sort = k; drawExplorer(); })), S.reveal ? th("LLM label") : null, th("Example"));
    const body = r.slice(0, E.shown).map(x => {
      const lab = S.reveal ? LABELS.get(`${api}|${x[IDX.pattern]}|${x[IDX.candidate]}`) : null;
      return el("tr", {}, el("td", {class: "n"}, x[0]), el("td", {}, el("span", {class: "tag t" + x[1]}, x[1])), el("td", {}, x[2]), el("td", {}, x[3]),
        [4, 5, 6, 7, 8, 9].map(i => el("td", {class: "n"}, fmt(x[i]))),
        S.reveal ? el("td", {title: lab ? lab.note : ""}, lab ? el("span", {class: "lab-" + lab.label}, lab.label) : "") : null,
        el("td", {class: "ex"}, x[10]));
    });
    $("e-table").replaceChildren(head, ...body);
    $("e-more").hidden = r.length <= E.shown;
  }

  // ------------------------------------------------------------------ scatter
  const symlog = v => (v >= 0 ? 1 : -1) * Math.log10(1 + Math.abs(v));
  let PTS = [], GEO = null;
  function drawScatter() {
    const api = $("s-api").value, c = $("s-canvas"), g = c.getContext("2d"), W = c.width, H = c.height, L = 78, R = 14, T = 14, B = 44;
    PTS = rows(api).filter(r => r[IDX.ll] != null).map(r => ({x: r[IDX.t], y: symlog(r[IDX.ll]), r}));
    g.clearRect(0, 0, W, H);
    if (!PTS.length) { g.fillStyle = "#8b949e"; g.font = "14px system-ui"; g.fillText("No reference table: no specificity axis.", L, H / 2); return; }
    const xs = PTS.map(p => p.x), ys = PTS.map(p => p.y);
    const x0 = Math.min(...xs, 0) - .2, x1 = Math.max(...xs, 3) + .2, y0 = Math.min(...ys, -.5) - .1, y1 = Math.max(...ys, 1) + .1;
    const X = v => L + (v - x0) / (x1 - x0) * (W - L - R), Y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
    GEO = {X, Y, L, R, T, B, W, H};
    g.font = "12px system-ui"; g.strokeStyle = "#30363d"; g.fillStyle = "#8b949e";
    for (let v = Math.ceil(x0); v <= x1; v++) { g.beginPath(); g.moveTo(X(v), T); g.lineTo(X(v), H - B); g.stroke(); g.fillText(v, X(v) - 3, H - B + 16); }
    [-100, -10, 0, 10, 100, 1000, 10000].forEach(v => { const y = Y(symlog(v)); if (y < T || y > H - B) return; g.beginPath(); g.moveTo(L, y); g.lineTo(W - R, y); g.stroke(); g.textAlign = "right"; g.fillText(v, L - 8, y + 4); g.textAlign = "left"; });
    g.setLineDash([5, 5]); g.strokeStyle = "#8b949e";
    g.beginPath(); g.moveTo(X(2), T); g.lineTo(X(2), H - B); g.stroke();
    g.beginPath(); g.moveTo(L, Y(symlog(3.84))); g.lineTo(W - R, Y(symlog(3.84))); g.stroke(); g.setLineDash([]);
    g.fillText("t-score (cohesion) →", W / 2 - 50, H - 8);
    g.save(); g.translate(14, H / 2 + 70); g.rotate(-Math.PI / 2); g.fillText("signed log-likelihood →", 0, 0); g.restore();
    ["noise", "general", "2", "1"].forEach(t => { g.fillStyle = TIER_COLOR[t]; g.globalAlpha = .7;
      PTS.filter(p => p.r[IDX.tier] === t).forEach(p => { g.beginPath(); g.arc(X(p.x), Y(p.y), 3, 0, 7); g.fill(); }); });
    g.globalAlpha = 1;
  }
  function scatterHover(ev) {
    if (!GEO) return; const c = $("s-canvas"), b = c.getBoundingClientRect(), k = c.width / b.width;
    const mx = (ev.clientX - b.left) * k, my = (ev.clientY - b.top) * k; let best = null, bd = 100;
    for (const p of PTS) { const d = (GEO.X(p.x) - mx) ** 2 + (GEO.Y(p.y) - my) ** 2; if (d < bd) { bd = d; best = p; } }
    const tip = $("s-tip"); if (!best) { tip.hidden = true; return; }
    const r = best.r; tip.hidden = false; tip.textContent = `${r[IDX.candidate]} · ${r[IDX.pattern]} · freq ${r[IDX.freq]} · t ${r[IDX.t]} · LL ${r[IDX.ll]}`;
    tip.style.left = Math.min(ev.clientX - b.left + 12, b.width - 240) + "px"; tip.style.top = (ev.clientY - b.top + 12) + "px";
  }

  // ------------------------------------------------------------------ variation / verbs
  function drawVariation() {
    const api = $("v-api").value, q = $("v-q").value.toLowerCase(), only = $("v-flag").checked;
    const r = D[api].variation[S.method].filter(v => (!only || v.equivalent_class) && (!q || v.noun.toLowerCase().includes(q) || v.verbs.toLowerCase().includes(q)));
    $("v-count").textContent = `${r.length} nouns`;
    $("v-table").replaceChildren(el("tr", {}, ["Noun", "Verbs : frequency", "Class", "Suggested", "Total"].map((h, i) => th(h, i === 4 ? "n" : ""))),
      ...r.slice(0, 300).map(v => el("tr", {}, el("td", {}, v.noun), el("td", {}, v.verbs), el("td", {}, v.equivalent_class || "–"),
        el("td", {}, v.suggested_preferred || "–"), el("td", {class: "n"}, v.total_freq))));
  }
  function drawVerbs() {
    const statuses = ["same", "same_class", "different", "no_verb", "no_id_verb"];
    $("verb-summary").replaceChildren(el("table", {}, el("tr", {}, ["API", ...statuses].map((h, i) => th(h, i ? "n" : ""))),
      APIS.map(api => { const c = D[api].agreement.counts, tot = Object.values(c).reduce((a, b) => a + b, 0);
        return el("tr", {}, el("td", {}, api), statuses.map(s => el("td", {class: "n"}, c[s] ? `${fmt(c[s])} (${pct(c[s] / tot)})` : "–"))); })));
    const api = $("d-api").value, m = new Map();
    D[api].agreement.rows.filter(r => r[3] === "different").forEach(r => { const k = r[1] + " → " + r[2]; m.set(k, (m.get(k) || 0) + 1); });
    const top = [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 15);
    $("d-table").replaceChildren(el("tr", {}, [th("operationId verb → description verb"), th("Operations", "n")]),
      ...(top.length ? top.map(([k, n]) => el("tr", {}, el("td", {}, k), el("td", {class: "n"}, n))) : [el("tr", {}, el("td", {colspan: 2, class: "mut"}, "No divergences to show (see the table above).")) ]));
  }

  // ------------------------------------------------------------------ annotation
  function drawAnnotation() {
    const box = $("a-body"); box.hidden = !S.reveal;
    if (!S.reveal || !A.annotation) return;
    const ev = A.annotation.evaluation, dv = A.annotation.derived, rows0 = A.annotation.rows;
    const tbl = (head, body) => el("div", {class: "scroll"}, el("table", {}, el("tr", {}, head.map((h, i) => th(h, i ? "n" : ""))), body));
    const counts = ["cle", "generic", "not", "doubtful"].map(l => [l, rows0.filter(r => r.label === l).length]);
    const tierRows = Object.entries(ev.per_tier_weighted).filter(([t]) => t !== "negative" || true).map(([t, v]) =>
      el("tr", {}, el("td", {}, el("span", {class: "tag t" + t}, TIER_NAME[t] || t)), [v.n_annotated, pct(v.weighted_precision_strict), pct(v.weighted_precision_with_generic)].map(x => el("td", {class: "n"}, x))));
    const pk = Object.entries(ev.precision_at_k).map(([api, v]) => el("tr", {}, el("td", {}, api), ["5", "10", "20"].map(k => el("td", {class: "n"}, v[k] == null ? "–" : pct(v[k])))));
    const strata = Object.entries(ev.per_stratum).map(([k, v]) => el("tr", {}, el("td", {}, k), [v.annotated, v.cle, v.generic, v.not, pct(v.precision_strict), pct(v.precision_with_generic)].map(x => el("td", {class: "n"}, x))));
    const pat = Object.entries(dv.by_pattern_unweighted).map(([p, v]) => el("tr", {}, el("td", {}, p), [v.annotated, v.cle, v.generic].map(x => el("td", {class: "n"}, x))));
    const dd = (name, v) => el("tr", {}, el("td", {}, name), [v.n, pct(v.strict), pct(v.with_generic)].map(x => el("td", {class: "n"}, x)));
    box.replaceChildren(
      el("p", {}, "Labels: ", counts.map(([l, n]) => el("span", {class: "lab-" + l, style: "margin-right:14px"}, `${l} ${n}`))),
      el("h3", {}, "Precision per tier (stratum-weighted)"), tbl(["Tier", "Annotated", "Strict (cle)", "With generic"], tierRows),
      el("h3", {}, "Precision@k of the top of the ranking"), tbl(["API", "@5", "@10", "@20"], pk),
      el("h3", {}, "What predicts a term?"), tbl(["Subset", "Annotated", "Strict", "With generic"], [
        dd("In both methods (main strata)", dv.main_strata_in_surface), dd("Dependency-only (main strata)", dv.main_strata_not_in_surface),
        dd("Freq 4-9, t ≥ 2", dv.freq_4_9_cohesive_t_ge_2), dd("Freq 4-9, t < 2", dv.freq_4_9_not_cohesive_t_lt_2)]),
      el("h3", {}, "By pattern (unweighted counts)"), tbl(["Pattern", "Annotated", "cle", "generic"], pat),
      el("h3", {}, "Per stratum"), tbl(["Stratum", "Annotated", "cle", "generic", "not", "Strict", "With generic"], strata));
  }

  // ------------------------------------------------------------------ about
  function drawSources() {
    $("sources").replaceChildren(el("table", {}, el("tr", {}, ["API", "Domain", "Source", "Commit", "Licence", "Copyright"].map(h => th(h))),
      APIS.map(api => { const m = D[api].meta; return el("tr", {}, [api, m.domain, m.repo, m.commit, m.license, m.copyright].map(x => el("td", {}, x))); })));
  }

  // ------------------------------------------------------------------ wiring
  function init() {
    ["e-api", "s-api", "v-api", "d-api"].forEach(id => fill($(id), APIS));
    fill($("e-pat"), ["", ...PATTERNS]); $("e-pat").firstChild.textContent = "all";
    $("method").onchange = () => { S.method = $("method").value; all(); };
    ["e-api", "e-pat", "e-tier", "e-min", "e-q"].forEach(id => $(id).addEventListener("input", () => { E.shown = 200; drawExplorer(); }));
    $("e-more").onclick = () => { E.shown += 300; drawExplorer(); };
    $("s-api").onchange = drawScatter; $("s-canvas").addEventListener("mousemove", scatterHover);
    $("s-canvas").addEventListener("mouseleave", () => { $("s-tip").hidden = true; });
    ["v-api", "v-flag", "v-q"].forEach(id => $(id).addEventListener("input", drawVariation));
    $("d-api").onchange = drawVerbs;
    $("a-reveal").onchange = () => { S.reveal = $("a-reveal").checked; drawAnnotation(); drawExplorer(); };
    $("s-legend").replaceChildren(legend(TIERS.map(t => [TIER_COLOR[t], TIER_NAME[t]])));
    drawSources(); all();
  }
  function all() { drawOverview(); drawFindings(); drawExplorer(); drawScatter(); drawVariation(); drawVerbs(); drawAnnotation(); }
  init();
})();
