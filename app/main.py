"""APITerm webapp (plan section 7): upload an OpenAPI file, review candidates, export a glossary.

Privacy: the upload is processed in memory only. It is never written to disk and its content
is never logged (error messages carry no document text).

Run:  APITERM_REFERENCE=reference/data/news.db uvicorn app.main:app
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from apiterm.pipeline import analyze
from apiterm.reference import Reference
from apiterm.triage import Thresholds

MAX_BYTES = int(os.environ.get("APITERM_MAX_BYTES", 15 * 1024 * 1024))
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="APITerm", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@lru_cache(maxsize=1)
def get_nlp():
    from apiterm.annotate import load_model
    return load_model(os.environ.get("APITERM_MODEL", "en_core_web_sm"))


@lru_cache(maxsize=1)
def get_reference() -> Reference | None:
    path = os.environ.get("APITERM_REFERENCE")
    return Reference(path) if path else None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status() -> dict:
    ref = get_reference()
    return {"reference": ref.describe() if ref else None, "max_bytes": MAX_BYTES}


@app.post("/api/analyze")
def analyze_upload(file: UploadFile = File(...), method: str = Form("dependency"),
                   min_freq: int = Form(2), limit: int = Form(2000)) -> JSONResponse:
    if method not in ("surface", "dependency"):
        raise HTTPException(422, "method must be 'surface' or 'dependency'")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"file larger than {MAX_BYTES // (1024 * 1024)} MB")
    try:
        res = analyze(data, get_reference(), get_nlp(), Thresholds(min_freq=max(min_freq, 1)),
                      methods=(method,))
    except ValueError as exc:                       # message never contains document text
        raise HTTPException(400, str(exc)) from None
    except RecursionError:
        raise HTTPException(400, "document is nested too deeply") from None
    cols = ("rank", "tier", "tier_label", "pattern", "candidate", "freq", "raw_freq", "contexts",
            "t_score", "log_likelihood", "ref_freq", "example")
    return JSONResponse({
        "summary": res.summary,
        "candidates": [{c: r[c] for c in cols} for r in res.rows[method][:max(limit, 1)]],
        "variation": res.variation[method],
        "verb_agreement": res.summary["verb_agreement"],
    })
