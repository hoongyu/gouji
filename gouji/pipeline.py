"""One investigation, end to end, with every step written to a JSONL trace.

Guard -> plan -> investigate (Zetaris / DuckDB) -> verify -> World Model -> follow-ups -> decide
(mandate engine) -> execution contract -> executor -> brief.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.mandate import Effect, Mandate

from gouji.agents import INITIAL_PLAN, MAX_ROUNDS, guard, plan_followups, verify, write_brief
from gouji.checks import Finding, run_check
from gouji.contract import PaymentExecutor, issue_contract
from gouji.harness import Harness
from gouji.llm import Generator
from gouji.policy import decide_payment, grade_evidence
from gouji.world_model import ContextBuilderService, IngestPipelineService, WorldStoreService

FRAUD_ASPECTS = {"identity", "account", "channel", "duplicate", "injection"}


@dataclass
class Trace:
    path: Path
    run_id: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, agent: str, action: str, summary: str, **details: Any) -> None:
        ev = {"timestamp": datetime.now(UTC).isoformat(timespec="seconds"), "run_id": self.run_id,
              "agent": agent, "action": action, "summary": summary, **details}
        self.events.append(ev)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, default=str, ensure_ascii=False) + "\n")


@dataclass
class Context:
    harness: Harness
    store: WorldStoreService
    mandate: Mandate
    executor: PaymentExecutor
    key: bytes
    now: datetime
    planner: Generator | None = None
    reporter: Generator | None = None
    guard: Generator | None = None


def _number(findings: list[Finding], start: int) -> int:
    for f in findings:
        if not f.fid:
            start += 1
            f.fid = f"F{start}"
    return start


def investigate(ctx: Context, inv_id: str, trace: Trace, *, bypass_probe: bool = True) -> dict[str, Any]:
    t0 = time.perf_counter()
    h, now = ctx.harness, ctx.now
    q0 = len(h.log)
    inv = h.query("SELECT inv_id, issuer_name, account_on_invoice, amount_minor, po_ref FROM {invoices} WHERE inv_id = ?",
                  [inv_id])[0]
    trace.emit("Intake", "receive", f"payment request for {inv_id} from '{inv['issuer_name']}' "
               f"(EUR {inv['amount_minor'] / 100:,.2f})", inv_id=inv_id)

    findings, intent = guard(h, inv_id, now, ctx.guard)
    n = _number(findings, 0)
    trace.emit("Guard", "scan", f"intent={intent}; "
               + ("instructions aimed at the AI found and quarantined" if any(f.polarity == "red_flag" for f in findings)
                  else "no instructions aimed at the AI"), findings=[f.fid for f in findings])

    ran = {"C7"}
    plan, why, who = list(INITIAL_PLAN), "standard pre-payment checks for this intent", "scripted"
    ingest, builder = IngestPipelineService(ctx.store), ContextBuilderService(ctx.store)
    alerts = []
    for rnd in range(MAX_ROUNDS + 1):
        trace.emit("Planner", "plan", f"round {rnd}: run {', '.join(plan) or 'nothing'} ({who}): {why}", checks=plan)
        if not plan:
            break
        for check in plan:
            new = run_check(h, check, inv_id, now)
            n = _number(new, n)
            findings += new
            ran.add(check)
            trace.emit("Investigator", "query", f"{check}: {len(new)} findings "
                       f"({sum(f.polarity == 'red_flag' for f in new)} red flags)",
                       findings=[f.to_dict() for f in new])
        stats = verify(h, findings)
        trace.emit("Verifier", "re-read", f"{stats['citations']} cited cells re-read from source, "
                   f"{stats['mismatched']} mismatched, {stats['findings_dropped']} findings dropped", **stats)
        alerts = ingest.ingest(h, inv_id, now)
        context = builder.build(inv_id, alerts)
        trace.emit("WorldModel", "ingest", f"{len(context['items'])} entities in context, {len(alerts)} alerts"
                   + (": " + "; ".join(a.kind for a in alerts) if alerts else ""), alerts=context["alerts"])
        if rnd == MAX_ROUNDS:
            break
        plan, why, who = plan_followups(findings, context["alerts"], ran, ctx.planner)

    grades, grade_why = grade_evidence(findings, alerts)
    decision, facts, labels = decide_payment(ctx.mandate, inv_id=inv_id, account=inv["account_on_invoice"],
                                             amount_minor=inv["amount_minor"], now=now, grades=grades)
    trace.emit("Decider", "decide", f"mandate engine: {decision.effect} ({', '.join(decision.matched) or 'default'})",
               grades={k: str(v) for k, v in grades.items()}, reasons=list(decision.reasons))

    contract = None
    payment = None
    probe = None
    evidence_ids = [f.fid for f in findings if f.verified and f.polarity == "support"]
    if decision.effect is Effect.ALLOW:
        contract = issue_contract(decision, facts, inv_id=inv_id, evidence_ids=evidence_ids, mandate=ctx.mandate,
                                  now=now, key=ctx.key)
        payment = ctx.executor.pay(inv_id=inv_id, facts=facts, contract=contract, now=now)
        trace.emit("Executor", "pay", f"contract {contract.contract_id} verified; payment {payment['status']}",
                   contract_id=contract.contract_id)
    elif bypass_probe:
        probe = ctx.executor.pay(inv_id=inv_id, facts=facts, contract=None, now=now)
        trace.emit("Executor", "bypass-probe", f"direct pay call without a contract: {probe['status']} "
                   f"({probe['reason']})")

    reds = [f for f in findings if f.verified and f.polarity == "red_flag"]
    red_aspects = {f.aspect for f in reds} | {a.aspect for a in alerts}
    if decision.effect is Effect.ALLOW:
        recommendation = "release"
    elif red_aspects & FRAUD_ASPECTS:
        recommendation = "hold: likely fraud, do not pay; call the supplier on the number on file"
    elif red_aspects:
        recommendation = "hold: ask the supplier to correct the invoice"
    else:
        recommendation = "hold: evidence incomplete, review by hand"
    brief = write_brief(findings, str(decision.effect), recommendation, ctx.reporter)
    trace.emit("Reporter", "brief", f"brief by {brief['author']}; {brief['dropped_sentences']} uncited sentences removed")

    return {
        "inv_id": inv_id,
        "issuer": inv["issuer_name"],
        "amount_minor": inv["amount_minor"],
        "decision": str(decision.effect),
        "recommendation": recommendation,
        "matched_clauses": list(decision.matched),
        "decision_reasons": list(decision.reasons),
        "grades": {k: str(v) for k, v in grades.items()},
        "grade_reasons": grade_why,
        "findings": [f.to_dict() for f in findings],
        "alerts": [{"kind": a.kind, "aspect": a.aspect, "message": a.message} for a in alerts],
        "contract": contract.model_dump(mode="json") if contract else None,
        "payment": payment,
        "bypass_probe": probe,
        "brief": brief,
        "queries": len(h.log) - q0,
        "seconds": round(time.perf_counter() - t0, 3),
    }
