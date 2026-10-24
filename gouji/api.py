"""HTTP entry point and the one-page brief for the accounts-payable specialist.

    POST /run                 {"run_id": "...", "input": {"inv_id": "INV-5567"}, "options": {"sample_mode": true}}
    GET  /                    the open payment requests
    GET  /brief/{inv_id}      the one-page brief: decision first, evidence chain below
    GET  /row/{table}/{pk}    a cited row, re-read from its source system
    GET  /health
"""

from __future__ import annotations

import html
import json
import os
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from engine.audit import AuditLog
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from gouji.contract import PaymentExecutor, signing_key
from gouji.harness import TABLES, open_harness
from gouji.llm import load_dotenv, openai_generator, sample_mode
from gouji.pipeline import Context, Trace, investigate
from gouji.policy import build_mandate
from gouji.world_model import WorldStoreService

DATA = Path(os.environ.get("GOUJI_DATA", "data/sample"))
LOGS = Path("logs")
AGENTS = [
    {"name": "Guard", "role": "Scans untrusted text for instructions aimed at the AI before anything reads it"},
    {"name": "Planner", "role": "Chooses the checks and follow-ups; never decides payment"},
    {"name": "Investigator", "role": "Runs each check as federated SQL where the data lives (Zetaris or DuckDB)"},
    {"name": "Verifier", "role": "Re-reads every cited cell from its source; drops what does not match"},
    {"name": "WorldModel", "role": "Meterless World Model: resolves legal entities, raises doppelganger alerts"},
    {"name": "Decider", "role": "mandate-engine decides on graded evidence; only ALLOW gets an execution contract"},
    {"name": "Reporter", "role": "Writes the brief; sentences without verified citations are removed"},
]

app = FastAPI(title="gouji", version="0.1.0")


@lru_cache(maxsize=1)
def _state() -> tuple[Context, dict[str, Any]]:
    load_dotenv()
    meta = json.loads((DATA / "cases.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(meta["now"])
    key = signing_key()
    run = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    ctx = Context(harness=open_harness(DATA), store=WorldStoreService(LOGS / f"world-api-{run}.jsonl"),
                  mandate=build_mandate(meta["registry_accounts"], now, investigated=True),
                  executor=PaymentExecutor(key, AuditLog(LOGS / f"audit-api-{run}.jsonl")), key=key, now=now,
                  planner=openai_generator("deepseek"), reporter=openai_generator("deepseek"))
    return ctx, meta


_cache: dict[str, dict[str, Any]] = {}


def _investigate(inv_id: str, run_id: str) -> dict[str, Any]:
    ctx, _ = _state()
    if not ctx.harness.query("SELECT inv_id FROM {invoices} WHERE inv_id = ?", [inv_id]):
        raise HTTPException(404, f"no invoice {inv_id}")
    result = investigate(ctx, inv_id, Trace(LOGS / f"trace-{run_id}.jsonl", run_id))
    _cache[inv_id] = result
    return result


class RunRequest(BaseModel):
    run_id: str | None = None
    input: dict[str, Any]
    options: dict[str, Any] = {}


@app.get("/health")
def health() -> dict[str, Any]:
    ctx, meta = _state()
    return {"status": "ok", "backend": ctx.harness.name, "sample_mode": sample_mode() or ctx.planner is None,
            "cases": len(meta["cases"])}


@app.post("/run")
def run(req: RunRequest) -> dict[str, Any]:
    run_id = req.run_id or datetime.now(UTC).strftime("run-%Y%m%dT%H%M%S")
    t0 = time.perf_counter()
    inv_id = req.input.get("inv_id")
    if not inv_id:
        return {"run_id": run_id, "status": "error",
                "error": {"type": "BadInput", "message": "input.inv_id is required", "recoverable": True}}
    try:
        r = _investigate(inv_id, run_id)
    except HTTPException as exc:
        return {"run_id": run_id, "status": "error",
                "error": {"type": "NotFound", "message": exc.detail, "recoverable": True}}
    except Exception as exc:  # a structured error, never a silent crash
        return {"run_id": run_id, "status": "error",
                "error": {"type": type(exc).__name__, "message": str(exc)[:300], "recoverable": False}}
    return {
        "run_id": run_id, "status": "success",
        "output": {"summary": f"{r['decision']}: {r['recommendation']}", "decision": r["decision"],
                   "recommendations": [r["recommendation"]], "brief": r["brief"]["text"], "grades": r["grades"],
                   "alerts": r["alerts"], "contract": r["contract"], "artifacts": [f"/brief/{inv_id}"]},
        "agents": AGENTS, "trace_id": f"trace-{run_id}", "log_file": f"logs/trace-{run_id}.jsonl",
        "execution_time_seconds": round(time.perf_counter() - t0, 2),
    }


CSS = """
body{font:15px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:920px;margin:24px auto;padding:0 16px;color:#111}
h1{font-size:22px;margin:0 0 4px} .muted{color:#666} table{border-collapse:collapse;width:100%;margin:12px 0}
td,th{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top} th{background:#f3f3f3}
.verdict{border:2px solid #111;padding:14px 16px;margin:16px 0} .hold{border-color:#b00020} .release{border-color:#0a7d32}
.verdict b{font-size:20px} a{color:#0645ad} code{background:#f3f3f3;padding:0 3px} .red{color:#b00020} .ok{color:#0a7d32}
"""


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                        f"<title>{html.escape(title)}</title><style>{CSS}</style>{body}")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    ctx, meta = _state()
    rows = ctx.harness.query("SELECT inv_id, issuer_name, amount_minor, received_at FROM {invoices} "
                             "WHERE status = 'pending' ORDER BY inv_id")
    body = ("<h1>Payment requests awaiting release</h1><p class=muted>Veltrona Drives GmbH (fictional). "
            f"Data: {html.escape(ctx.harness.name)}. Click a request to investigate it.</p><table>"
            "<tr><th>Invoice</th><th>Issuer</th><th>Amount</th></tr>")
    body += "".join(f"<tr><td><a href='/brief/{r['inv_id']}'>{r['inv_id']}</a></td><td>{html.escape(r['issuer_name'])}"
                    f"</td><td>EUR {r['amount_minor'] / 100:,.2f}</td></tr>" for r in rows)
    return _page("gouji", body + "</table>")


@app.get("/brief/{inv_id}", response_class=HTMLResponse)
def brief(inv_id: str) -> HTMLResponse:
    r = _cache.get(inv_id) or _investigate(inv_id, datetime.now(UTC).strftime("ui-%Y%m%dT%H%M%S"))
    release = r["decision"] == "allow"
    cite = {f["fid"]: f for f in r["findings"]}

    def link_ids(text: str) -> str:
        import re
        return re.sub(r"\b(F\d+)\b", lambda m: f"<a href='#{m.group(1)}'>{m.group(1)}</a>", html.escape(text))

    body = (f"<p class=muted><a href='/'>All requests</a></p><h1>{html.escape(r['issuer'])}: {inv_id}</h1>"
            f"<p class=muted>EUR {r['amount_minor'] / 100:,.2f}</p>"
            f"<div class='verdict {'release' if release else 'hold'}'><b>{'Release' if release else 'Hold'}</b><br>"
            f"{html.escape(r['recommendation'])}<br><span class=muted>Decided by the mandate, not the model: "
            f"{html.escape(r['decision'])} "
            f"({html.escape(', '.join(r['matched_clauses']) or 'no clause allows it; a person must approve')})."
            + (f" Execution contract {html.escape(r['contract']['contract_id'])} issued." if r["contract"] else
               " No execution contract: the payment system will refuse to pay.") + "</span></div>"
            f"<h2>Why</h2><p>{link_ids(r['brief']['text'])}</p><p class=muted>Written by: {html.escape(r['brief']['author'])}; "
            f"{r['brief']['dropped_sentences']} sentence(s) without verified citations removed.</p>")
    if r["alerts"]:
        body += "<h2>World Model alerts</h2><ul>" + "".join(
            f"<li class=red>{html.escape(a['message'])}</li>" for a in r["alerts"]) + "</ul>"
    body += "<h2>Evidence by aspect</h2><table><tr><th>Aspect</th><th>Grade</th><th>Why</th></tr>"
    body += "".join(f"<tr><td>{a}</td><td class={'ok' if g == 'verified' else 'red'}>{g}</td>"
                    f"<td>{html.escape(r['grade_reasons'].get(a, ''))}</td></tr>" for a, g in r["grades"].items())
    body += "</table><h2>Findings (every cell re-read from its source)</h2><table><tr><th>Id</th><th>Finding</th><th>Sources</th></tr>"
    for f in r["findings"]:
        if f["polarity"] == "info" and not f["verified"]:
            continue
        cls = "red" if f["polarity"] == "red_flag" else ("ok" if f["polarity"] == "support" else "muted")
        srcs = "<br>".join(f"<a href='/row/{c['table']}/{html.escape(str(c['pk']))}'>{c['system']}.{c['table']}"
                           f"[{html.escape(str(c['pk']))}].{c['column']}</a>" for c in f["citations"])
        body += (f"<tr id='{f['fid']}'><td>{f['fid']}</td><td class={cls}>{html.escape(f['claim'])}"
                 f"{'' if f['verified'] else ' <b>(not verified)</b>'}</td><td>{srcs}</td></tr>")
    return _page(f"{inv_id} brief", body + "</table>")


@app.get("/row/{table}/{pk}", response_class=HTMLResponse)
def row(table: str, pk: str) -> HTMLResponse:
    if table not in TABLES:
        raise HTTPException(404, "unknown table")
    ctx, _ = _state()
    data = ctx.harness.fetch(table, pk)
    if data is None:
        raise HTTPException(404, "no such row")
    system, key = TABLES[table]
    body = (f"<p class=muted><a href='javascript:history.back()'>Back</a></p><h1>{system}.{table}</h1>"
            f"<p class=muted>Re-read just now from {html.escape(ctx.harness.name)} by primary key {key} = "
            f"{html.escape(pk)}.</p><table>" + "".join(
                f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>" for k, v in data.items()) + "</table>")
    return _page(f"{table} {pk}", body)
