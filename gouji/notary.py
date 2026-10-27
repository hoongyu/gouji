"""The notary: the only component that can sign an execution contract, and it contains no model.

When the agent's investigation ends in ALLOW, the notary does not take the agent's word for it. It
checks the controller's signature on the policy, runs every check again on the systems of record
(the pattern screen, no planner, no model), re-reads every cited cell, grades the evidence and asks the
signed mandate. It signs only if its own decision is ALLOW for the same payment. A model can therefore
make PayProof stricter (flag an injection, add a check), never looser: money goes out only when the
investigation without a model would have released it too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from engine.facts import ActionFacts
from engine.mandate import Effect, Mandate
from engine.pdp import Decision

from gouji.agents import guard, verify
from gouji.checks import Finding, run_check
from gouji.contract import (
    ExecutionContract,
    evidence_cells,
    evidence_root,
    issue_contract,
)
from gouji.harness import Harness
from gouji.policy import PolicyError, decide_payment, grade_evidence, load_policy
from gouji.world_model import Alert, IngestPipelineService, WorldStoreService

CHECKS_WITHOUT_MODEL = ("C1", "C2", "C3", "C4", "C5", "C6")  # C7 runs inside the guard
PAYMENT_FIELDS = ("action", "payee_id", "counterparty_account", "amount_minor", "currency")


@dataclass
class Rederivation:
    decision: Decision
    facts: ActionFacts
    findings: list[Finding]
    alerts: list[Alert]
    queries: int


def rederive(h: Harness, inv_id: str, now: datetime, mandate: Mandate) -> Rederivation:
    """The whole investigation again, without a model: every check, the Verifier, the World Model, the mandate."""
    q0 = len(h.log)
    inv = h.query("SELECT account_on_invoice, amount_minor FROM {invoices} WHERE inv_id = ?", [inv_id])[0]
    findings, _ = guard(h, inv_id, now, None)
    for check in CHECKS_WITHOUT_MODEL:
        findings += run_check(h, check, inv_id, now)
    verify(h, findings)
    alerts = IngestPipelineService(WorldStoreService()).ingest(h, inv_id, now)
    grades, _ = grade_evidence(findings, alerts)
    decision, facts, _ = decide_payment(mandate, inv_id=inv_id, account=inv["account_on_invoice"],
                                        amount_minor=inv["amount_minor"], now=now, grades=grades)
    return Rederivation(decision, facts, findings, alerts, len(h.log) - q0)


@dataclass
class Certificate:
    contract: ExecutionContract | None
    refusal: str | None
    decision: str
    facts: ActionFacts | None = None
    cells: list[list[str]] = field(default_factory=list)
    evidence_root: str = ""
    queries: int = 0


class Notary:
    def __init__(self, h: Harness, policy: Path, controller: Ed25519PublicKey, key: Ed25519PrivateKey,
                 ttl: timedelta = timedelta(minutes=15)) -> None:
        self._h, self._policy, self._controller, self._key, self._ttl = h, policy, controller, key, ttl

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self._key.public_key()

    def certify(self, inv_id: str, requested: ActionFacts, now: datetime) -> Certificate:
        """Sign a contract if, and only if, the notary's own re-derivation allows the requested payment."""
        try:
            mandate, policy_sha = load_policy(self._policy, self._controller)  # checked before every signature
        except PolicyError as exc:
            return Certificate(None, str(exc), "not decided")
        rd = rederive(self._h, inv_id, now, mandate)
        cert = Certificate(None, None, str(rd.decision.effect), rd.facts, evidence_cells(rd.findings),
                           evidence_root(rd.findings), rd.queries)
        if rd.decision.effect is not Effect.ALLOW:
            cert.refusal = f"its own re-check without a model decides {rd.decision.effect}"
        elif any(getattr(rd.facts, k) != getattr(requested, k) for k in PAYMENT_FIELDS):
            cert.refusal = "the payment it re-derived differs from the one requested"
        else:
            cert.contract = issue_contract(rd.decision, rd.facts, inv_id=inv_id, evidence_cells=len(cert.cells),
                                           evidence_root=cert.evidence_root, mandate=mandate, policy_sha256=policy_sha,
                                           now=now, key=self._key, ttl=self._ttl)
        return cert
