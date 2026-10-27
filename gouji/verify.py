"""Check a PayProof decision after the fact, from its proof file alone.

    python run.py verify logs/proofs/<run>/INV-5559.json [--backend zetaris]

Nothing in the proof is taken on trust. The policy must carry the controller's signature; every cited
cell is read again from its system of record; the program grades the evidence and asks the signed
mandate again; a contract must carry the notary's signature and bind this payment, this evidence and
this policy; and for a release, the investigation runs once more without a model and must release it too.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from engine.mandate import Effect

from gouji.checks import Citation, Finding
from gouji.contract import ExecutionContract, evidence_root, facts_digest
from gouji.harness import Harness
from gouji.notary import rederive
from gouji.policy import PolicyError, decide_payment, grade_evidence, load_policy
from gouji.signing import canonical, cell_text, fingerprint, sha256, verify
from gouji.world_model import IngestPipelineService, WorldStoreService


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


class _Rows:
    """Cited rows, each read once from the source system."""

    def __init__(self, h: Harness) -> None:
        self.h, self.rows = h, {}

    def same(self, table: str, pk: str, column: str, value: Any) -> bool:
        if (table, pk) not in self.rows:
            self.rows[(table, pk)] = self.h.fetch(table, pk)
        row = self.rows[(table, pk)]
        return row is not None and cell_text(row.get(column)) == cell_text(value)


def _finding(d: dict[str, Any]) -> Finding:
    return Finding(d["check"], d["aspect"], d["polarity"], d["claim"],
                   [Citation(c["table"], c["pk"], c["column"], c["value"]) for c in d["citations"]], d["fid"], d["verified"])


def verify_proof(proof: dict[str, Any], h: Harness, *, controller: Ed25519PublicKey, notaries: list[Ed25519PublicKey],
                 policy_file: Path | None = None) -> list[Check]:
    """`notaries` are the notary public keys this verifier trusts; the proof itself never supplies one."""
    out: list[Check] = []
    now = datetime.fromisoformat(proof["judged_at"])
    inv_id, pay = proof["inv_id"], proof["payment"]
    try:
        mandate, sha = load_policy(policy_file or Path(proof["policy"]["file"]), controller)
    except PolicyError as exc:
        return [Check("The policy carries the controller's signature", False, str(exc))]
    out.append(Check("The policy carries the controller's signature", True,
                     f"{mandate.mandate_id} v{mandate.version}, controller key {fingerprint(controller)}"))
    out.append(Check("The decision was taken under this policy", proof["policy"]["sha256"] == sha, f"sha256 {sha[:16]}"))

    rows = _Rows(h)
    findings = [_finding(d) for d in proof["agent"]["findings"]]
    cited = [(f, c) for f in findings if f.verified for c in f.citations]
    stale = {id(f) for f, c in cited if not rows.same(c.table, c.pk, c.column, c.value)}
    out.append(Check(f"Every cited cell reads the same in {h.name} today", not stale,
                     f"{sum(1 for f, c in cited if id(f) not in stale)} of {len(cited)} cells match"))
    root = evidence_root(findings)
    out.append(Check("The evidence root matches the cited cells", root == proof["agent"]["evidence_root"], root[:16]))
    for f in findings:
        if id(f) in stale:
            f.verified = False  # a finding whose cells changed no longer counts

    alerts = IngestPipelineService(WorldStoreService()).ingest(h, inv_id, now)
    kinds = sorted(a.kind for a in alerts)
    out.append(Check("The World Model raises the same alerts", kinds == sorted(a["kind"] for a in proof["agent"]["alerts"]),
                     ", ".join(kinds) or "none"))
    grades, _ = grade_evidence(findings, alerts)
    decision, facts, _ = decide_payment(mandate, inv_id=inv_id, account=pay["account"], amount_minor=pay["amount_minor"],
                                        now=now, grades=grades)
    out.append(Check("The signed mandate decides the same on this evidence",
                     str(decision.effect) == proof["agent"]["decision"] and facts_digest(facts) == proof["agent"]["facts_hash"],
                     f"{decision.effect} ({', '.join(decision.matched) or 'no clause applies, default'})"))

    if proof.get("contract"):
        c = ExecutionContract.model_validate(proof["contract"])
        signer = next((k for k in notaries if verify(k, c.signing_bytes(), c.signature)), None)
        out.append(Check("The contract carries the notary's signature", signer is not None,
                         f"{c.contract_id}, notary key {fingerprint(signer) if signer else 'not one this verifier trusts'}"))
        cells = proof["notary"]["cells"]
        fresh = sum(rows.same(*cell) for cell in cells)
        out.append(Check(f"The notary's cells read the same in {h.name} today", fresh == len(cells),
                         f"{fresh} of {len(cells)} cells match"))
        binds = (c.inv_id == inv_id and c.evidence_root == sha256(canonical(cells)) and c.policy_sha256 == sha
                 and c.evidence_cells == len(cells))
        out.append(Check("The contract binds this payment, this evidence and this policy", binds,
                         f"facts {c.facts_hash[:12]}, evidence {c.evidence_root[:12]}, policy {c.policy_sha256[:12]}"))
        rd = rederive(h, inv_id, now, mandate)
        out.append(Check("Run again without a model, the investigation releases it too",
                         rd.decision.effect is Effect.ALLOW and facts_digest(rd.facts) == c.facts_hash,
                         f"{rd.decision.effect} after {rd.queries} queries"))
    else:
        gw = proof.get("gateway") or {}
        out.append(Check("No contract was issued, so nothing could be paid", gw.get("status") != "paid",
                         f"gateway: {gw.get('status', 'not called')} ({gw.get('reason') or 'no reason given'})"))
    return out
