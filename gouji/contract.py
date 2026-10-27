"""Scout-style execution contract: nothing pays out without one.

This is a bonus component. It is not one of the three engine guides the organisers handed out
(H-MEM, Markovian, World Model); its design follows the Scout Intent spec in the public Meterless
repository (engines/scout-intent): a signed object the downstream system verifies before it acts.

Only the notary (gouji/notary.py) can sign a contract, with its own Ed25519 key, and only after it has
re-derived the ALLOW on its own. A contract binds the exact payment (a hash of the action facts), the
evidence it rests on (a hash of every cited cell and its value), and the signed policy in force; it
expires quickly and can be used once. The payment gateway holds the notary's public key and nothing
else, so neither the agent nor the gateway can mint a contract, and a model that talks its way to a
"pay" call still cannot move money.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from engine.audit import AuditLog
from engine.facts import ActionFacts
from engine.mandate import Effect, Mandate
from engine.pdp import Decision
from pydantic import AwareDatetime, BaseModel, ConfigDict

from gouji.checks import Finding
from gouji.signing import canonical, cell_text, fingerprint, sha256, sign, verify


def facts_digest(facts: ActionFacts) -> str:
    body = json.dumps(facts.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return sha256(body.encode())


def evidence_cells(findings: Iterable[Finding]) -> list[list[str]]:
    """Every cell the verified findings cite, as [table, pk, column, value], sorted and de-duplicated."""
    cells = {(c.table, str(c.pk), c.column, cell_text(c.value)) for f in findings if f.verified for c in f.citations}
    return [list(c) for c in sorted(cells)]


def evidence_root(findings: Iterable[Finding]) -> str:
    return sha256(canonical(evidence_cells(findings)))


class ExecutionContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str
    action: str
    inv_id: str
    facts_hash: str
    evidence_root: str
    policy_sha256: str
    decision: str
    matched_clauses: tuple[str, ...]
    evidence_cells: int
    mandate_id: str
    mandate_version: int
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    notary_key: str
    signature: str = ""

    def signing_bytes(self) -> bytes:
        return canonical(self.model_dump(mode="json", exclude={"signature"}))


def issue_contract(decision: Decision, facts: ActionFacts, *, inv_id: str, evidence_cells: int, evidence_root: str,
                   mandate: Mandate, policy_sha256: str, now: datetime, key: Ed25519PrivateKey,
                   ttl: timedelta = timedelta(minutes=15)) -> ExecutionContract:
    if decision.effect is not Effect.ALLOW:
        raise ValueError(f"no contract for a {decision.effect} decision")
    unsigned = ExecutionContract(
        contract_id=f"EC-{secrets.token_hex(4)}", action=facts.action, inv_id=inv_id, facts_hash=facts_digest(facts),
        evidence_root=evidence_root, policy_sha256=policy_sha256, decision=str(decision.effect),
        matched_clauses=decision.matched, evidence_cells=evidence_cells, mandate_id=mandate.mandate_id,
        mandate_version=mandate.version, issued_at=now, expires_at=now + ttl, notary_key=fingerprint(key.public_key()),
    )
    return unsigned.model_copy(update={"signature": sign(key, unsigned.signing_bytes())})


class PaymentExecutor:
    """The payment gateway: the only thing that can move money. It holds the notary's public key, never a
    private one, and checks the contract, not anyone's reasoning. Spent contracts are read back from its
    hash-chained ledger on start, so a restart does not make a contract usable again."""

    def __init__(self, notary: Ed25519PublicKey, audit: AuditLog, *, policy_sha256: str | None = None) -> None:
        self._notary = notary
        self._audit = audit
        self._policy = policy_sha256
        self._used = {r.payload.get("contract_id") for r in audit.records() if r.kind == "payment_paid"}

    def pay(self, *, inv_id: str, facts: ActionFacts, contract: ExecutionContract | None, now: datetime) -> dict[str, Any]:
        reason = self._refusal(inv_id, facts, contract, now)
        status = "refused" if reason else "paid"
        if not reason and contract:
            self._used.add(contract.contract_id)
        self._audit.append("payment_" + status, {
            "inv_id": inv_id, "contract_id": contract.contract_id if contract else None,
            "account": facts.counterparty_account, "amount_minor": facts.amount_minor, "reason": reason,
        }, now)
        return {"status": status, "reason": reason}

    def _refusal(self, inv_id: str, facts: ActionFacts, c: ExecutionContract | None, now: datetime) -> str | None:
        if c is None:
            return "no execution contract"
        if not verify(self._notary, c.signing_bytes(), c.signature):
            return "contract is not signed by the notary"
        if not c.issued_at <= now < c.expires_at:
            return "contract expired"
        if c.inv_id != inv_id or c.facts_hash != facts_digest(facts):
            return "contract was issued for a different payment"
        if self._policy and c.policy_sha256 != self._policy:
            return "contract was issued under a policy that is no longer in force"
        if c.contract_id in self._used:
            return "contract already used"
        return None
