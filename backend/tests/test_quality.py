"""Tests qualité Vague 1 n°4 — complexité C901 native Ruff + grade maintenabilité."""

from fastapi.testclient import TestClient

from backend.agents.graph import run_pipeline
from backend.agents.tools import complexity_summary
from backend.main import app

client = TestClient(app)

COMPLEXE = """def monstre(a, b, c, d, e, f, g, h, i, j, k, l):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        if f:
                            if g:
                                if h:
                                    if i:
                                        if j:
                                            if k:
                                                if l:
                                                    return 1
    return 0
"""


def test_code_simple_grade_a():
    r = run_pipeline(code="x = 1\n")
    assert r["complexity"]["c901_count"] == 0
    assert r["maintainability"] == "A"


def test_code_complexe_c901_detecte():
    r = run_pipeline(code=COMPLEXE)
    assert r["complexity"]["c901_count"] >= 1
    assert r["complexity"]["max_complexity"] > 10
    assert r["maintainability"] in ("B", "C", "D")
    assert any("C901" in f for f in r["findings"])


def test_grade_regle_deterministe():
    assert complexity_summary([])["grade"] == "A"
    assert complexity_summary(
        [{"code": "C901", "message": "`f` is too complex (13 > 10)"}])["grade"] == "B"
    assert complexity_summary(
        [{"code": "C901", "message": "`f` is too complex (25 > 10)"}])["grade"] == "D"


def test_review_expose_complexite_et_audit():
    r = client.post("/review", json={"code": COMPLEXE})
    assert r.status_code == 200
    body = r.json()
    assert body["maintainability"] in ("B", "C", "D")
    assert body["complexity"]["c901_count"] >= 1
    g = client.get(f"/runs/{body['run_id']}")
    assert g.status_code == 200
    summary = g.json()["result_summary"]
    assert summary["maintainability"] in ("B", "C", "D")
    assert "grade=" in body["devops_notes"]
