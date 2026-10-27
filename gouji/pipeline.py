"""One investigation, end to end, with every step written to a JSONL trace and a proof file.

Guard -> plan -> investigate (Zetaris / DuckDB) -> verify -> World Model -> follow-ups -> decide
(mandate engine, signed policy) -> notary re-check without a model -> execution contract -> gateway -> brief.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.audit import AuditLog
from engine.mandate import Effect, Mandate

from gouji.agents import (
    INITIAL_PLAN,
    MAX_ROUNDS,
    guard,
    plan_followups,
    verify,
    write_brief,
)
from gouji.checks import Finding, run_check
from gouji.contract import PaymentExecutor, evidence_root, facts_digest
from gouji.harness import Harness, open_harness
from gouji.llm import Generator
from gouji.notary import Notary
from gouji.policy import decide_payment, grade_evidence, load_policy, policy_path
from gouji.signing import fingerprint, private_key, public_key
from gouji.world_model import (
    ContextBuilderService,
    IngestPipelineService,
    WorldStoreService,
)

FRAUD_ASPECTS = {"identity", "account", "channel", "duplicate", "injection"}


@dataclass
class Trace:
    path: Path
    run_id: str
    echo: bool = False  # also print each event to stdout (the API and single cases do; batch evaluation does not)
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, agent: str, action: str, summary: str, **details: Any) -> None:
        ev = {"timestamp": datetime.now(UTC).isoformat(timespec="seconds"), "run_id": self.run_id,
              "agent": agent, "action": action, "summary": summary, **details}
        self.events.append(ev)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, default=str, ensure_ascii=False) + "\n")
        if self.echo:
            print(f"[{self.run_id}] {agent:<12} {action:<12} {summary}", flush=True)


@dataclass
class Context:
    harness: Harness
    store: WorldStoreService
    mandate: Mandate  # from the policy file the controller signed
    policy_file: Path
    policy_sha256: str
    notary: Notary
    executor: PaymentExecutor
    now: datetime
    planner: Generator | None = None
    reporter: Generator | None = None
    guard: Generator | None = None
    proofs: Path | None = None  # where to write one proof file per investigation


def open_context(data_dir: Path, logs_dir: Path, run_id: str, *, planner: Generator | None = None,
                 reporter: Generator | None = None, guard: Generator | None = None,
                 proofs: Path | None = None) -> tuple[Context, dict[str, Any]]:
    """Everything one PayProof process needs, wired with the separation the guarantees rest on: the policy
    is loaded only if the controller's signature holds; the notary owns its private key; the gateway gets
    the notary's public key from keys/notary.pub and nothing else."""
    meta = json.loads((data_dir / "cases.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(meta["now"])
    h = open_harness(data_dir)
    policy_file = policy_path(data_dir)
    mandate, policy_sha = load_policy(policy_file)  # PolicyError: PayProof does not run on an unsigned policy
    notary = Notary(h, policy_file, public_key("controller"), private_key("notary"))
    gateway = PaymentExecutor(public_key("notary"), AuditLog(logs_dir / f"gateway-{run_id}.jsonl"),
                              policy_sha256=policy_sha)
    ctx = Context(harness=h, store=WorldStoreService(logs_dir / f"world-{run_id}.jsonl"), mandate=mandate,
                  policy_file=policy_file, policy_sha256=policy_sha, notary=notary, executor=gateway, now=now,
                  planner=planner, reporter=reporter, guard=guard, proofs=proofs)
    return ctx, meta


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
            red = sum(f.polarity == "red_flag" for f in new)
            trace.emit("Investigator", "query", f"{check}: {len(new)} finding{'' if len(new) == 1 else 's'} "
                       f"({red} red flag{'' if red == 1 else 's'})",
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
    trace.emit("Decider", "decide", f"signed mandate {ctx.mandate.mandate_id} v{ctx.mandate.version}: {decision.effect} "
               f"({', '.join(decision.matched) or 'default'})",
               grades={k: str(v) for k, v in grades.items()}, reasons=list(decision.reasons))

    contract = payment = probe = cert = None
    effect = decision.effect
    if decision.effect is Effect.ALLOW:
        cert = ctx.notary.certify(inv_id, facts, now)
        trace.emit("Notary", "re-check", f"re-checked without a model: {cert.queries} queries, {len(cert.cells)} cells, "
                   f"decision {cert.decision}; " + (f"contract {cert.contract.contract_id} signed (Ed25519)"
                                                    if cert.contract else f"no contract: {cert.refusal}"))
        if cert.contract:
            contract = cert.contract
            payment = ctx.executor.pay(inv_id=inv_id, facts=cert.facts, contract=contract, now=now)
            trace.emit("Executor", "pay", f"contract {contract.contract_id} verified with the notary's public key; "
                       f"payment {payment['status']}", contract_id=contract.contract_id)
        else:
            effect = Effect.ASK
    if effect is not Effect.ALLOW and bypass_probe:
        probe = ctx.executor.pay(inv_id=inv_id, facts=facts, contract=None, now=now)
        trace.emit("Executor", "bypass-probe", f"direct pay call without a contract: {probe['status']} "
                   f"({probe['reason']})")

    reds = [f for f in findings if f.verified and f.polarity == "red_flag"]
    red_aspects = {f.aspect for f in reds} | {a.aspect for a in alerts}
    if effect is Effect.ALLOW:
        recommendation = "release"
    elif red_aspects & FRAUD_ASPECTS:
        recommendation = "hold: likely fraud, do not pay; call the supplier on the number on file"
    elif red_aspects:
        recommendation = "hold: ask the supplier to correct the invoice"
    elif cert and not cert.contract:
        recommendation = "hold: the notary's re-check without a model did not confirm the release; review by hand"
    else:
        recommendation = "hold: evidence incomplete, review by hand"
    brief = write_brief(findings, str(effect), recommendation, ctx.reporter)
    trace.emit("Reporter", "brief", f"brief by {brief['author']}; {brief['dropped_sentences']} sentences removed "
               "(uncited, or arguing against the decision)")

    proof = {
        "proof_version": 1, "inv_id": inv_id, "run_id": trace.run_id, "judged_at": now.isoformat(),
        "backend": h.name, "decision": str(effect),
        "payment": {"account": inv["account_on_invoice"], "amount_minor": inv["amount_minor"], "currency": "EUR"},
        "policy": {"file": ctx.policy_file.as_posix(), "mandate_id": ctx.mandate.mandate_id,
                   "version": ctx.mandate.version, "sha256": ctx.policy_sha256},
        "agent": {"decision": str(decision.effect), "matched_clauses": list(decision.matched),
                  "facts_hash": facts_digest(facts), "grades": {k: str(v) for k, v in grades.items()},
                  "findings": [f.to_dict() for f in findings],
                  "alerts": [{"kind": a.kind, "aspect": a.aspect} for a in alerts],
                  "evidence_root": evidence_root(findings),
                  "models": {"guard": bool(ctx.guard), "planner": bool(ctx.planner), "reporter": bool(ctx.reporter)}},
        "notary": None if cert is None else {
            "decision": cert.decision, "refusal": cert.refusal, "queries": cert.queries, "cells": cert.cells,
            "evidence_root": cert.evidence_root, "key": fingerprint(ctx.notary.public_key)},
        "contract": contract.model_dump(mode="json") if contract else None,
        "gateway": payment or probe,
    }
    proof_file = None
    if ctx.proofs is not None:
        ctx.proofs.mkdir(parents=True, exist_ok=True)
        proof_file = ctx.proofs / f"{inv_id}.json"
        proof_file.write_text(json.dumps(proof, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    return {
        "inv_id": inv_id,
        "issuer": inv["issuer_name"],
        "amount_minor": inv["amount_minor"],
        "decision": str(effect),
        "recommendation": recommendation,
        "matched_clauses": list(decision.matched),
        "decision_reasons": list(decision.reasons),
        "grades": {k: str(v) for k, v in grades.items()},
        "grade_reasons": grade_why,
        "findings": [f.to_dict() for f in findings],
        "alerts": [{"kind": a.kind, "aspect": a.aspect, "message": a.message} for a in alerts],
        "notary": proof["notary"],
        "contract": proof["contract"],
        "payment": payment,
        "bypass_probe": probe,
        "brief": brief,
        "proof": proof,
        "proof_file": proof_file.as_posix() if proof_file else None,
        "queries": len(h.log) - q0,
        "seconds": round(time.perf_counter() - t0, 3),
    }
