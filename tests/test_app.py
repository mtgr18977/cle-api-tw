import logging

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client(monkeypatch, reference_db, nlp):
    monkeypatch.setenv("APITERM_REFERENCE", str(reference_db))
    import app.main as m
    m.get_reference.cache_clear()
    m.get_nlp.cache_clear()
    monkeypatch.setattr(m, "get_nlp", lambda: nlp)
    return TestClient(m.app)


def test_index_and_status(client):
    assert "Your file is processed in memory" in client.get("/").text
    assert client.get("/api/status").json()["reference"]["source"] == "synthetic test news"


def test_analyze_upload(client, sample_spec):
    r = client.post("/api/analyze", files={"file": ("spec.yaml", sample_spec)}, data={"method": "dependency"})
    assert r.status_code == 200
    j = r.json()
    assert j["candidates"][0]["tier"] == "1" and j["candidates"][0]["rank"] == 1
    assert any(v["noun"] == "token" for v in j["variation"])


def test_bad_input_is_rejected_without_echoing_content(client, caplog):
    secret = "SUPER-SECRET-INTERNAL-HOST"
    with caplog.at_level(logging.DEBUG):
        r = client.post("/api/analyze", files={"file": ("x.yaml", f"hello: {secret}")})
    assert r.status_code == 400 and secret not in r.text
    assert secret not in caplog.text
    r = client.post("/api/analyze", files={"file": ("x.yaml", b"{}")}, data={"method": "nope"})
    assert r.status_code == 422


def test_size_limit(client, monkeypatch):
    import app.main as m
    monkeypatch.setattr(m, "MAX_BYTES", 100)
    r = client.post("/api/analyze", files={"file": ("x.yaml", b"a" * 500)})
    assert r.status_code == 413


def test_nothing_written_to_disk(client, sample_spec, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client.post("/api/analyze", files={"file": ("spec.yaml", sample_spec)})
    assert list(tmp_path.iterdir()) == []
