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
import re
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
                  planner=openai_generator("deepseek"), reporter=openai_generator("deepseek"),
                  guard=openai_generator("deepseek"))
    return ctx, meta


_cache: dict[str, dict[str, Any]] = {}


def _investigate(inv_id: str, run_id: str) -> dict[str, Any]:
    ctx, _ = _state()
    if not ctx.harness.query("SELECT inv_id FROM {invoices} WHERE inv_id = ?", [inv_id]):
        raise HTTPException(404, f"no invoice {inv_id}")
    trace = Trace(LOGS / f"trace-{run_id}.jsonl", run_id, echo=True)
    result = investigate(ctx, inv_id, trace)
    result["trace"] = trace.events
    result["run_id"] = run_id
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
:root{--ink:#16181d;--muted:#5f6670;--line:#e3e5e8;--soft:#f5f6f7;--red:#b42318;--red-bg:#fef3f2;--green:#067647;
--green-bg:#ecfdf3;--amber:#9a6700;--amber-bg:#fff8e6;--link:#1849a9}
*{box-sizing:border-box} body{font:15px/1.55 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif;color:var(--ink);
background:#fff;max-width:980px;margin:0 auto;padding:24px 16px 64px}
a{color:var(--link);text-decoration:none} a:hover{text-decoration:underline}
h1{font-size:24px;margin:6px 0 2px} h2{font-size:17px;margin:32px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.muted{color:var(--muted)} .small{font-size:13px} code,.mono{font-family:ui-monospace,Consolas,monospace;font-size:13px}
table{border-collapse:collapse;width:100%} td,th{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:var(--soft);font-weight:600;font-size:13px}
.verdict{border-radius:10px;padding:18px 20px;margin:18px 0 8px;border:1px solid}
.verdict.hold{background:var(--red-bg);border-color:#fecdca} .verdict.release{background:var(--green-bg);border-color:#abefc6}
.verdict .big{font-size:22px;font-weight:700} .hold .big{color:var(--red)} .release .big{color:var(--green)}
.verdict .rec{font-size:16px;margin:2px 0 10px}
.pill{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:600;white-space:nowrap}
.p-ok{background:var(--green-bg);color:var(--green)} .p-red{background:var(--red-bg);color:var(--red)}
.p-amber{background:var(--amber-bg);color:var(--amber)} .p-grey{background:var(--soft);color:var(--muted)}
.why p{margin:0 0 8px} .cite{font-size:12px;font-weight:600;vertical-align:1px}
.quarantine{border:1px dashed var(--red);background:#fff;padding:10px 12px;border-radius:8px;margin:8px 0}
.quarantine .label{font-size:12px;font-weight:600;color:var(--red);text-transform:uppercase;letter-spacing:.04em}
.timeline{list-style:none;padding:0;margin:0} .timeline li{display:grid;grid-template-columns:120px 1fr;gap:10px;
padding:6px 0;border-bottom:1px solid var(--line)} .agent{font-weight:600;font-size:13px}
.kv{display:grid;grid-template-columns:170px 1fr;gap:4px 12px;margin:8px 0} .kv div:nth-child(odd){color:var(--muted)}
tr.hl td,tr.hl th{background:var(--amber-bg)}
@media (max-width:640px){.timeline li{grid-template-columns:1fr}.kv{grid-template-columns:1fr}}
"""


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                        f"<title>{html.escape(title)}</title><style>{CSS}</style>{body}")


def _eur(minor: int) -> str:
    return f"EUR {minor / 100:,.2f}"


def _verdict(r: dict[str, Any]) -> tuple[str, str, str]:
    """(css class, headline, one sentence) for a result."""
    if r["decision"] == "allow":
        return "release", "Release", "Every required aspect is verified by independent trusted systems."
    _, _, rest = r["recommendation"].partition(": ")
    return "hold", "Hold", (rest[:1].upper() + rest[1:] + ".") if rest else "A person must decide."


GRADE_PILL = {"verified": ("p-ok", "verified"), "sourced": ("p-amber", "one source"),
              "user": ("p-amber", "unchecked"), "estimated": ("p-red", "not verified")}
POLARITY_PILL = {"red_flag": "<span class='pill p-red'>red flag</span>",
                 "support": "<span class='pill p-ok'>support</span>"}


def _link_ids(text: str) -> str:
    """Escape text and turn [F3] or [F2, F5] into links to the findings."""
    def links(m: re.Match) -> str:
        ids = [i.strip() for i in m.group(1).split(",")]
        return "<span class=cite>[" + ", ".join(f"<a href='#{i}'>{i}</a>" for i in ids) + "]</span>"
    escaped = html.escape(text)
    escaped = re.sub(r"\[(F\d+(?:\s*,\s*F\d+)*)\]", links, escaped)
    return re.sub(r"(?<![\[#\w])(F\d+)\b(?![^<]*</a>)", r"<a href='#\1'>\1</a>", escaped)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    ctx, _ = _state()
    rows = ctx.harness.query("SELECT inv_id, issuer_name, amount_minor, received_at FROM {invoices} "
                             "WHERE status = 'pending' ORDER BY inv_id")
    body = ("<h1>Payment requests awaiting release</h1><p class=muted>Veltrona Drives GmbH (fictional buyer). "
            f"The five systems are queried in place through <b>{html.escape(ctx.harness.name)}</b>. Open a request to "
            "investigate it; the mandate, not the model, decides whether it is paid.</p><table>"
            "<tr><th>Invoice</th><th>Issuer</th><th>Amount</th><th>Received</th><th>Status</th></tr>")
    for r in rows:
        done = _cache.get(r["inv_id"])
        status = ("<span class='pill p-grey'>not investigated</span>" if not done else
                  "<span class='pill p-ok'>release</span>" if done["decision"] == "allow" else
                  "<span class='pill p-red'>hold</span>")
        body += (f"<tr><td><a href='/brief/{r['inv_id']}'>{r['inv_id']}</a></td><td>{html.escape(r['issuer_name'])}</td>"
                 f"<td>{_eur(r['amount_minor'])}</td><td class=small>{str(r['received_at'])[:10]}</td><td>{status}</td></tr>")
    return _page("gouji: payment requests", body + "</table>")


@app.get("/brief/{inv_id}", response_class=HTMLResponse)
def brief(inv_id: str) -> HTMLResponse:
    r = _cache.get(inv_id) or _investigate(inv_id, datetime.now(UTC).strftime("ui-%Y%m%dT%H%M%S"))
    cls, headline, sentence = _verdict(r)
    c = r["contract"]
    if c:
        decided = (f"Decision <b>ALLOW</b> under clause {html.escape(', '.join(c['matched_clauses']))} of mandate "
                   f"<code>{html.escape(c['mandate_id'])}</code> v{c['mandate_version']}, not by the model. "
                   f"Execution contract <code>{html.escape(c['contract_id'])}</code> issued.")
    else:
        decided = ("Decision <b>ASK</b>, taken by the signed mandate, not by the model: no clause allows automatic "
                   "payment, so a person decides. No execution contract was issued.")
    body = (f"<p class=small><a href='/'>&larr; All requests</a></p><h1>{html.escape(r['issuer'])}</h1>"
            f"<div class=muted>Invoice {inv_id} &middot; {_eur(r['amount_minor'])}</div>"
            f"<div class='verdict {cls}'><div class=big>{headline}</div><div class=rec>{html.escape(sentence)}</div>"
            f"<div class=small>{decided}</div></div>")

    body += f"<h2>Why</h2><div class=why><p>{_link_ids(r['brief']['text'])}</p></div>"
    author = r["brief"]["author"]
    author = {"model": "the model", "scripted": "the scripted reporter (sample mode, no model)"}.get(author, author)
    body += (f"<p class='small muted'>Written by {html.escape(author)}. Every sentence cites findings "
             f"the Verifier re-read from source; {r['brief']['dropped_sentences']} sentence(s) without such citations "
             "were removed.</p>")

    for f in r["findings"]:
        if f["aspect"] == "injection" and f["polarity"] == "red_flag" and f["verified"]:
            for cit in f["citations"]:
                body += (f"<div class=quarantine><div class=label>Quarantined: text addressed to the AI "
                         f"({html.escape(cit['system'])}.{html.escape(cit['table'])}.{html.escape(cit['column'])})</div>"
                         f"<div class=mono>{html.escape(str(cit['value'])[:600])}</div>"
                         "<div class='small muted'>Treated as data. It is never evidence and never an instruction."
                         "</div></div>")

    if r["alerts"]:
        body += "<h2>World Model alerts</h2><ul>" + "".join(
            f"<li>{html.escape(a['message'])} <span class='pill p-grey'>{html.escape(a['kind'])}</span></li>"
            for a in r["alerts"]) + "</ul>"

    body += "<h2>Evidence by aspect</h2><table><tr><th>Aspect</th><th>Grade</th><th>Why</th></tr>"
    for aspect, g in r["grades"].items():
        pill, label = GRADE_PILL.get(g, ("p-grey", g))
        body += (f"<tr><td>{aspect}</td><td><span class='pill {pill}'>{label}</span></td>"
                 f"<td>{_link_ids(r['grade_reasons'].get(aspect, ''))}</td></tr>")
    body += "</table>"

    body += "<h2>Payment system</h2><div class=kv>"
    if c:
        pay = r["payment"] or {}
        evidence = ", ".join(f"<a href='#{i}'>{i}</a>" for i in c["evidence_ids"]) or "-"
        body += (f"<div>Execution contract</div><div><code>{html.escape(c['contract_id'])}</code>, HMAC-signed</div>"
                 f"<div>Bound to payment</div><div class=mono>{html.escape(c['facts_hash'][:16])}&hellip;</div>"
                 f"<div>Valid</div><div>{html.escape(c['issued_at'])} to {html.escape(c['expires_at'])}, single use</div>"
                 f"<div>Rests on</div><div>{evidence}</div>"
                 f"<div>Executor</div><div><span class='pill p-ok'>{html.escape(str(pay.get('status', '')))}</span></div>")
    else:
        probe = r["bypass_probe"] or {}
        body += ("<div>Execution contract</div><div>none</div>"
                 f"<div>Direct pay call</div><div><span class='pill p-red'>{html.escape(str(probe.get('status', 'not tried')))}"
                 f"</span> {html.escape(str(probe.get('reason', '')))}</div>")
    body += "</div>"

    body += ("<h2>Findings</h2><p class='small muted'>Every cited cell was re-read from its source system by primary "
             "key. Open a cell to see the row it came from.</p><table><tr><th>Id</th><th>Finding</th><th>Cited cells</th></tr>")
    for f in r["findings"]:
        if f["polarity"] == "info" and not f["verified"]:
            continue
        cites = "<br>".join(
            f"<a class=small href='/row/{cit['table']}/{html.escape(str(cit['pk']))}?col={cit['column']}'>"
            f"{cit['system']}.{cit['table']}[{html.escape(str(cit['pk']))}].{cit['column']}</a>" for cit in f["citations"])
        body += (f"<tr id='{f['fid']}'><td><b>{f['fid']}</b><br><span class='small muted'>{f['check']}</span></td>"
                 f"<td>{POLARITY_PILL.get(f['polarity'], '<span class=\"pill p-grey\">context</span>')} "
                 f"{html.escape(f['claim'])}{'' if f['verified'] else ' <b>(not verified, ignored)</b>'}</td>"
                 f"<td>{cites}</td></tr>")
    body += "</table>"

    if r.get("trace"):
        body += ("<h2>How gouji got here</h2><p class='small muted'>Each agent's step for this request, from "
                 f"<code>logs/trace-{html.escape(r['run_id'])}.jsonl</code>: {r['queries']} queries in {r['seconds']} s."
                 "</p><ol class=timeline>")
        body += "".join(f"<li><span class=agent>{html.escape(e['agent'])}</span><span>{_link_ids(e['summary'])}</span></li>"
                        for e in r["trace"])
        body += "</ol>"
    return _page(f"{inv_id}: {headline}", body)


@app.get("/row/{table}/{pk}", response_class=HTMLResponse)
def row(table: str, pk: str, col: str = "") -> HTMLResponse:
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
                f"<tr{' class=hl' if k == col else ''}><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>"
                for k, v in data.items()) + "</table>")
    return _page(f"{table} {pk}", body)
