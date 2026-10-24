"""Scout-style execution contract: nothing pays out without one.

This is a bonus component. It is not one of the three engine guides the organisers handed out
(H-MEM, Markovian, World Model); its design follows the Scout Intent spec in the public Meterless
repository (engines/scout-intent): a signed object the downstream system verifies before it acts.

A contract is issued only when the mandate's decision is ALLOW. It binds the exact payment (a hash of
the action facts), the evidence it rests on, and the mandate version, expires quickly, and can be
used once. The executor refuses anything else, so a model that talks its way to a "pay" call still
cannot move money.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Any

from engine.audit import AuditLog
from engine.facts import ActionFacts
from engine.mandate import Effect, Mandate
from engine.pdp import Decision
from pydantic import AwareDatetime, BaseModel, ConfigDict


def facts_digest(facts: ActionFacts) -> str:
    body = json.dumps(facts.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


class ExecutionContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str
    action: str
    inv_id: str
    facts_hash: str
    decision: str
    matched_clauses: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    mandate_id: str
    mandate_version: int
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    signature: str = ""

    def signing_bytes(self) -> bytes:
        body = self.model_dump(mode="json", exclude={"signature"})
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def signing_key() -> bytes:
    """From CONTRACT_SIGNING_KEY; a fresh random key per process otherwise (sample mode)."""
    env = os.environ.get("CONTRACT_SIGNING_KEY")
    return env.encode() if env else _PROCESS_KEY


_PROCESS_KEY = secrets.token_bytes(32)


def _sign(c: ExecutionContract, key: bytes) -> str:
    return hmac.new(key, c.signing_bytes(), hashlib.sha256).hexdigest()


def issue_contract(decision: Decision, facts: ActionFacts, *, inv_id: str, evidence_ids: list[str],
                   mandate: Mandate, now: datetime, key: bytes, ttl: timedelta = timedelta(minutes=15)) -> ExecutionContract:
    if decision.effect is not Effect.ALLOW:
        raise ValueError(f"no contract for a {decision.effect} decision")
    unsigned = ExecutionContract(
        contract_id=f"EC-{secrets.token_hex(4)}", action=facts.action, inv_id=inv_id, facts_hash=facts_digest(facts),
        decision=str(decision.effect), matched_clauses=decision.matched, evidence_ids=tuple(evidence_ids),
        mandate_id=mandate.mandate_id, mandate_version=mandate.version, issued_at=now, expires_at=now + ttl,
    )
    return unsigned.model_copy(update={"signature": _sign(unsigned, key)})


class PaymentExecutor:
    """The only thing that can move money. It checks the contract, not the model's reasoning."""

    def __init__(self, key: bytes, audit: AuditLog) -> None:
        self._key = key
        self._audit = audit
        self._used: set[str] = set()

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
        if not c.signature.isascii() or not hmac.compare_digest(c.signature, _sign(c, self._key)):
            return "contract signature does not match"
        if not c.issued_at <= now < c.expires_at:
            return "contract expired"
        if c.inv_id != inv_id or c.facts_hash != facts_digest(facts):
            return "contract was issued for a different payment"
        if c.contract_id in self._used:
            return "contract already used"
        return None
