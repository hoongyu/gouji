import os

os.environ["SAMPLE_MODE"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from gouji.api import app  # noqa: E402

client = TestClient(app)


def test_run_returns_a_structured_result_and_a_hold_for_the_doppelganger():
    cases = client.get("/health").json()
    assert cases["status"] == "ok"
    r = client.post("/run", json={"run_id": "t1", "input": {"inv_id": "INV-5567"}, "options": {"sample_mode": True}}).json()
    assert r["status"] == "success"
    assert r["output"]["decision"] == "ask"
    assert r["output"]["contract"] is None
    assert r["log_file"] == "logs/trace-t1.jsonl"


def test_unknown_invoice_is_a_structured_error():
    r = client.post("/run", json={"input": {"inv_id": "INV-NOPE"}}).json()
    assert r["status"] == "error" and r["error"]["type"] == "NotFound"


def test_brief_and_cited_rows_render():
    page = client.get("/brief/INV-5567").text
    assert "Hold" in page and "legal entities" in page  # the World Model's doppelganger alert
    row = client.get("/row/invoices/INV-5567")
    assert row.status_code == 200 and "account_on_invoice" in row.text
