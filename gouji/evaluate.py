"""B1 (mandate only) against B3 (investigated) on the same cases, with every denominator printed.

The case mix and volumes are design choices for the fictional buyer, not measurements; they are
written into every report so nobody mistakes them for field data.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.audit import AuditLog
from engine.mandate import Effect

from gouji.contract import PaymentExecutor, signing_key
from gouji.harness import open_harness
from gouji.llm import Generator
from gouji.pipeline import Context, Trace, investigate
from gouji.policy import build_mandate, decide_payment
from gouji.world_model import WorldStoreService


def _eur(minor: int) -> str:
    return f"EUR {minor / 100:,.2f}"


def evaluate(data_dir: Path, logs_dir: Path, run_id: str, *, planner: Generator | None = None,
             reporter: Generator | None = None, guard: Generator | None = None,
             only: list[str] | None = None) -> dict[str, Any]:
    meta = json.loads((data_dir / "cases.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(meta["now"])
    cases = [c for c in meta["cases"] if not only or c["case_id"] in only or c["inv_id"] in only]
    h = open_harness(data_dir)
    b1_mandate = build_mandate(meta["registry_accounts"], now, investigated=False)
    b3_mandate = build_mandate(meta["registry_accounts"], now, investigated=True)
    key = signing_key()
    ctx = Context(harness=h, store=WorldStoreService(logs_dir / f"world-{run_id}.jsonl"), mandate=b3_mandate,
                  executor=PaymentExecutor(key, AuditLog(logs_dir / f"audit-{run_id}.jsonl")), key=key, now=now,
                  planner=planner, reporter=reporter, guard=guard)
    trace = Trace(logs_dir / f"trace-{run_id}.jsonl", run_id)
    rows = []
    results = {}
    for c in cases:
        inv = h.query("SELECT account_on_invoice, amount_minor FROM {invoices} WHERE inv_id = ?", [c["inv_id"]])[0]
        b1, _, _ = decide_payment(b1_mandate, inv_id=c["inv_id"], account=inv["account_on_invoice"],
                                  amount_minor=inv["amount_minor"], now=now, grades=None)
        r = investigate(ctx, c["inv_id"], trace)
        results[c["case_id"]] = r
        rows.append({"case_id": c["case_id"], "kind": c["kind"], "is_attack": c["is_attack"], "inv_id": c["inv_id"],
                     "amount_minor": c["amount_minor"], "b1": str(b1.effect), "b3": r["decision"],
                     "b3_recommendation": r["recommendation"], "red_flags": sum(
                         1 for f in r["findings"] if f["verified"] and f["polarity"] == "red_flag"),
                     "queries": r["queries"], "seconds": r["seconds"],
                     "brief_dropped": r["brief"]["dropped_sentences"]})
    summary = _summarise(rows)
    return {"run_id": run_id, "backend": h.name, "now": meta["now"], "seed": meta["seed"],
            "planner": "model" if planner else "scripted", "reporter": "model" if reporter else "scripted",
            "guard": "patterns + model screen" if guard else "patterns",
            "summary": summary, "cases": rows, "results": results}


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    attacks = [r for r in rows if r["is_attack"]]
    normal = [r for r in rows if not r["is_attack"]]
    out: dict[str, Any] = {"cases": len(rows), "attacks": len(attacks), "normal": len(normal),
                           "attack_money_minor": sum(r["amount_minor"] for r in attacks)}
    for b in ("b1", "b3"):
        missed = [r for r in attacks if r[b] == str(Effect.ALLOW)]
        blocked = [r for r in normal if r[b] != str(Effect.ALLOW)]
        out[b] = {
            "attacks_auto_released": len(missed),
            "attack_money_auto_released_minor": sum(r["amount_minor"] for r in missed),
            "attack_money_share": (sum(r["amount_minor"] for r in missed) / out["attack_money_minor"]) if attacks else 0.0,
            "normal_interrupted": len(blocked),
            "normal_interrupted_share": len(blocked) / len(normal) if normal else 0.0,
            "missed_kinds": sorted({r["kind"] for r in missed}),
            "interrupted_kinds": sorted({r["kind"] for r in blocked}),
        }
    by_kind: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "b1_allow": 0, "b3_allow": 0})
    for r in rows:
        k = by_kind[r["kind"]]
        k["n"] += 1
        k["b1_allow"] += r["b1"] == str(Effect.ALLOW)
        k["b3_allow"] += r["b3"] == str(Effect.ALLOW)
    out["by_kind"] = dict(sorted(by_kind.items()))
    held_attacks = [r for r in attacks if r["b3"] != str(Effect.ALLOW)]
    out["b3_hold_recommended_on_attacks"] = sum(r["b3_recommendation"].startswith("hold") for r in held_attacks)
    out["b3_brief_sentences_dropped"] = sum(r["brief_dropped"] for r in rows)
    return out


def to_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"# Evaluation {report['run_id']}",
        "",
        f"Backend: {report['backend']}. Planner: {report['planner']}. Reporter: {report['reporter']}. "
        f"Guard: {report['guard']}. "
        f"Seed {report['seed']}, judged as of {report['now']}.",
        "",
        f"Cases: {s['cases']} ({s['normal']} normal, {s['attacks']} attacks; attack money {_eur(s['attack_money_minor'])}). "
        "The mix and volumes are design choices for a fictional buyer, not field data.",
        "",
        "| | B1: mandate only | B3: investigated |",
        "|---|---|---|",
        f"| Attacks paid without a human | {s['b1']['attacks_auto_released']} / {s['attacks']} | "
        f"{s['b3']['attacks_auto_released']} / {s['attacks']} |",
        f"| Attack money paid without a human | {_eur(s['b1']['attack_money_auto_released_minor'])} "
        f"({s['b1']['attack_money_share']:.1%}) | {_eur(s['b3']['attack_money_auto_released_minor'])} "
        f"({s['b3']['attack_money_share']:.1%}) |",
        f"| Normal payments interrupted | {s['b1']['normal_interrupted']} / {s['normal']} "
        f"({s['b1']['normal_interrupted_share']:.1%}) | {s['b3']['normal_interrupted']} / {s['normal']} "
        f"({s['b3']['normal_interrupted_share']:.1%}) |",
        "",
        "| Kind | n | B1 paid | B3 paid |",
        "|---|---|---|---|",
    ]
    lines += [f"| {k} | {v['n']} | {v['b1_allow']} | {v['b3_allow']} |" for k, v in s["by_kind"].items()]
    lines += ["", f"B3 recommended holding {s['b3_hold_recommended_on_attacks']} of the attacks it escalated; "
              f"{s['b3_brief_sentences_dropped']} uncited brief sentences were removed by the Verifier."]
    return "\n".join(lines) + "\n"
