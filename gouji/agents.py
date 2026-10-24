"""The agents around the checks: Guard, Planner, Verifier, Reporter.

The model plans and explains; it never decides. Every claim it makes has to cite a finding the
Verifier re-read from source, and the decision is taken by the mandate engine on graded evidence.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from gouji.checks import CHECK_NAMES, Finding, run_check
from gouji.harness import Harness
from gouji.llm import Generator

INITIAL_PLAN = ["C1", "C2", "C3", "C4", "C5"]  # C7 runs first, in the Guard
MAX_ROUNDS = 2


# Guard -----------------------------------------------------------------------------------------
def guard(h: Harness, inv_id: str, now: datetime) -> tuple[list[Finding], str]:
    """Scan untrusted text for instructions aimed at the AI before anything else reads it."""
    findings = run_check(h, "C7", inv_id, now)
    mail = h.query("SELECT m.body FROM {invoices} i LEFT JOIN {mailbox} m ON m.email_id = i.email_id "
                   "WHERE i.inv_id = ?", [inv_id])
    body = (mail[0]["body"] or "") if mail else ""
    intent = "pay_invoice+account_change" if re.search(r"\b(account|remit|bank details)\b", body, re.I) else "pay_invoice"
    return findings, intent


# Planner -----------------------------------------------------------------------------------------
PLANNER_SYSTEM = (
    "You plan the next checks of a pre-payment investigation. You only choose which checks to run; "
    "you never decide whether to pay. Reply with JSON only: {\"run\": [check ids], \"why\": \"one sentence\"}. "
    "Choose from the available checks that have not run yet; return an empty list when the evidence is enough."
)


def plan_followups(findings: list[Finding], alerts: list[dict[str, Any]], ran: set[str],
                   gen: Generator | None) -> tuple[list[str], str, str]:
    """Return (checks to run, reason, who planned it: 'model' or 'scripted')."""
    available = [c for c in CHECK_NAMES if c not in ran]
    if not available:
        return [], "every check has run", "scripted"
    if gen is not None:
        summary = [{"id": f.fid, "check": f.check, "polarity": f.polarity, "claim": f.claim} for f in findings]
        prompt = json.dumps({"findings": summary, "world_model_alerts": alerts,
                             "available_checks": {c: CHECK_NAMES[c] for c in available}}, ensure_ascii=False)
        try:
            raw = gen(PLANNER_SYSTEM, prompt)
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            run = [c for c in data.get("run", []) if c in available][:3]
            return run, str(data.get("why", ""))[:300], "model"
        except Exception as exc:  # a bad plan falls back to the scripted one, and says so
            scripted, why, _ = plan_followups(findings, alerts, ran, None)
            return scripted, f"model plan unusable ({type(exc).__name__}); {why}", "scripted"
    suspicious = any(f.check in ("C1", "C2") and f.polarity in ("red_flag", "info") for f in findings) or alerts
    if suspicious and "C6" in available:
        return ["C6"], "identity or account looks unusual: trace where the request came from", "scripted"
    return [], "no anomaly that needs a follow-up", "scripted"


# Verifier ------------------------------------------------------------------------------------------
def _same(a: Any, b: Any) -> bool:
    if isinstance(a, datetime) or isinstance(b, datetime):
        return str(a)[:19].replace("T", " ") == str(b)[:19].replace("T", " ")
    return str(a) == str(b)


def verify(h: Harness, findings: list[Finding]) -> dict[str, int]:
    """Re-read every cited cell from its source system. A finding stands only if all its cells match."""
    stats = {"citations": 0, "mismatched": 0, "findings_dropped": 0}
    for f in findings:
        if f.verified is not None:
            continue
        ok = bool(f.citations)
        for c in f.citations:
            stats["citations"] += 1
            row = h.fetch(c.table, c.pk)
            if row is None or not _same(row.get(c.column), c.value):
                stats["mismatched"] += 1
                ok = False
        f.verified = ok
        stats["findings_dropped"] += 0 if ok else 1
    return stats


# Reporter ------------------------------------------------------------------------------------------
REPORTER_SYSTEM = (
    "You write the explanation an accounts-payable specialist reads before releasing or holding a payment. "
    "Use only the findings given. Every sentence must end with the ids of the findings it rests on, like [F3] or "
    "[F2, F5]. Do not decide; the decision is given. 4 to 7 sentences, plain English, no headings."
)
_CITE = re.compile(r"\[(F\d+(?:\s*,\s*F\d+)*)\]")


def filter_brief(text: str, valid: set[str]) -> tuple[str, int]:
    """Keep only sentences whose every cited id is a verified finding; count what was dropped."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    kept, dropped = [], 0
    for s in sentences:
        ids = [i.strip() for m in _CITE.findall(s) for i in m.split(",")]
        if ids and all(i in valid for i in ids):
            kept.append(s)
        else:
            dropped += 1
    return " ".join(kept), dropped


def write_brief(findings: list[Finding], decision: str, recommendation: str, gen: Generator | None) -> dict[str, Any]:
    verified = [f for f in findings if f.verified]
    valid = {f.fid for f in verified}
    lead = [f for f in verified if f.polarity == "red_flag"] or [f for f in verified if f.polarity == "support"]
    if gen is not None:
        payload = {"decision": decision, "recommendation": recommendation,
                   "findings": [{"id": f.fid, "polarity": f.polarity, "claim": f.claim} for f in verified]}
        try:
            text, dropped = filter_brief(gen(REPORTER_SYSTEM, json.dumps(payload, ensure_ascii=False)), valid)
        except Exception as exc:
            return {**_template(lead), "author": f"scripted (model failed: {type(exc).__name__}: {exc})"[:160]}
        if text:
            return {"text": text, "dropped_sentences": dropped, "author": "model"}
        return {**_template(lead), "dropped_sentences": dropped,
                "author": "scripted (no sentence of the model's brief survived citation checks)"}
    return {**_template(lead), "author": "scripted"}


def _template(lead: list[Finding]) -> dict[str, Any]:
    text = " ".join(f"{f.claim} [{f.fid}]" for f in lead[:6])
    return {"text": text, "dropped_sentences": 0}
