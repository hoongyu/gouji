"""The decision, made outside the model, by the mandate engine (mandate-engine, a declared
pre-existing component).

Verified findings become evidence grades; the mandate decides. Two mandates are built from the same
signed payee registry so the comparison is fair:

- B1 ("mandate only"): pay a registered payee, up to a cap, to an account traced to the mandate.
- B3 ("investigated"): the same clause plus a minimum evidence grade, and one more clause that lets
  a payee outside the registry through only when every required aspect is VERIFIED, i.e. two
  independent trusted systems agree and no red flag stands.

PayProof runs on B3, and only from a policy file the controller has signed with an Ed25519 key
(policy/ap-payments.<set>.json). The controller's public key is all PayProof holds; a policy that is
missing, unsigned or altered by one character is refused, and nothing is released under it.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from engine.facts import ActionFacts
from engine.grade import Grade
from engine.history import ActionHistory
from engine.mandate import Clause, Effect, Mandate, Payee
from engine.pdp import Decision, decide
from engine.provenance import ProvenanceLabel, ProvenanceTracker, Trust

from gouji.checks import ASPECTS, Finding
from gouji.harness import TRUSTED_SYSTEMS
from gouji.signing import canonical, fingerprint, public_key, sha256, sign, verify
from gouji.world_model import Alert

ACTION = "pay_invoice"
MAX_AUTO_MINOR = 25_000_000  # EUR 250,000.00 per payment without a human
REQUIRED = ("identity", "account", "price", "receipt", "duplicate", "injection")


def build_mandate(registry_accounts: dict[str, str], now: datetime, *, investigated: bool) -> Mandate:
    payees = tuple(Payee(payee_id=pid, name=pid, account=acct, category="supplier", verified_via="onboarding")
                   for pid, acct in sorted(registry_accounts.items()))
    base = dict(actions=frozenset({ACTION}), currencies=frozenset({"EUR"}), max_amount_minor=MAX_AUTO_MINOR,
                trusted_args=frozenset({"account"}))
    if investigated:
        clauses = (
            Clause(clause_id="P1", effect=Effect.ALLOW, payee_in_registry=True, min_grade=Grade.VERIFIED, **base),
            Clause(clause_id="P2", effect=Effect.ALLOW, min_grade=Grade.VERIFIED, **base),
        )
    else:
        clauses = (Clause(clause_id="P1", effect=Effect.ALLOW, payee_in_registry=True, **base),)
    return Mandate(
        mandate_id="ap-payments", version=2 if investigated else 1, principal="Veltrona accounts payable",
        agent_id="gouji", valid_from=now - timedelta(days=30), valid_until=now + timedelta(days=365),
        payees=payees, clauses=clauses, default_effect=Effect.ASK, approver="the AP specialist on duty",
    )


class PolicyError(Exception):
    """The policy is missing, unsigned or altered. Nothing may be released under it."""


def policy_path(data_dir: Path) -> Path:
    return Path(os.environ.get("GOUJI_POLICY", "policy")) / f"ap-payments.{Path(data_dir).name}.json"


def policy_document(mandate: Mandate) -> dict:
    """The mandate as JSON, with its sets sorted so the signed bytes never depend on hash order."""
    body = mandate.model_dump(mode="json")
    for clause in body["clauses"]:
        for k, v in clause.items():
            if isinstance(v, list):
                clause[k] = sorted(v)
    return body


def sign_policy(mandate: Mandate, key: Ed25519PrivateKey) -> dict:
    body = policy_document(mandate)
    data = canonical(body)
    return {"mandate": body, "sha256": sha256(data), "signed_by": "controller",
            "key": fingerprint(key.public_key()), "signature": sign(key, data)}


def write_signed_policy(data_dir: Path, key: Ed25519PrivateKey) -> Path:
    """The controller's act: sign the B3 mandate for a data set and write it to its policy file."""
    meta = json.loads((Path(data_dir) / "cases.json").read_text(encoding="utf-8"))
    mandate = build_mandate(meta["registry_accounts"], datetime.fromisoformat(meta["now"]), investigated=True)
    path = policy_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sign_policy(mandate, key), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_policy(path: Path, controller: Ed25519PublicKey | None = None) -> tuple[Mandate, str]:
    """The mandate in a signed policy file and its hash, if the controller's signature holds."""
    if not path.exists():
        raise PolicyError(f"no signed policy at {path}; the controller signs one with: python run.py policy")
    doc = json.loads(path.read_text(encoding="utf-8"))
    body = doc.get("mandate")
    pub = controller or public_key("controller")
    if not isinstance(body, dict) or not verify(pub, canonical(body), str(doc.get("signature", ""))):
        raise PolicyError(f"{path}: the controller's signature does not match this policy")
    return Mandate.model_validate(body), sha256(canonical(body))


def grade_evidence(findings: list[Finding], alerts: list[Alert]) -> tuple[dict[str, Grade], dict[str, str]]:
    """One grade per aspect from verified findings only. A single red flag or alert caps it."""
    grades: dict[str, Grade] = {}
    why: dict[str, str] = {}
    verified = [f for f in findings if f.verified]
    for aspect in ASPECTS:
        fs = [f for f in verified if f.aspect == aspect]
        if not fs and aspect not in REQUIRED:
            continue
        reds = [f.fid for f in fs if f.polarity == "red_flag"] + [a.kind for a in alerts if a.aspect == aspect]
        sup = [f for f in fs if f.polarity == "support"]
        systems = {s for f in sup for s in f.systems if s in TRUSTED_SYSTEMS}
        tables = {c.table for f in sup for c in f.citations}
        if reds:
            g, reason = Grade.ESTIMATED, "red flag: " + ", ".join(reds)
        elif not sup:
            g, reason = Grade.ESTIMATED, "not checked"
        elif aspect in ("identity", "account"):
            g = Grade.VERIFIED if len(systems) >= 2 else Grade.SOURCED
            reason = f"{len(systems)} independent trusted systems agree ({', '.join(sorted(systems))})"
        elif aspect == "price":
            g = Grade.VERIFIED if {"erp", "contracts"} <= systems else Grade.SOURCED
            reason = "invoice matches the contract in force" if g is Grade.VERIFIED else "contract not cited"
        elif aspect == "receipt":
            g = Grade.VERIFIED if {"purchase_orders", "goods_receipts"} <= tables else Grade.SOURCED
            reason = "order and goods receipt agree" if g is Grade.VERIFIED else "no goods receipt cited"
        else:
            g, reason = Grade.VERIFIED, "checked, nothing found"
        grades[aspect], why[aspect] = g, reason
    return grades, why


def decide_payment(mandate: Mandate, *, inv_id: str, account: str, amount_minor: int, now: datetime,
                   grades: dict[str, Grade] | None) -> tuple[Decision, ActionFacts, dict[str, ProvenanceLabel]]:
    """B1 when `grades` is None (no investigation), B3 otherwise."""
    tracker = ProvenanceTracker()
    for p in mandate.payees:
        tracker.observe(p.account, Trust.MANDATE, f"mandate payee {p.payee_id}")
    tracker.observe(f"invoice {inv_id}: pay {account}", Trust.UNTRUSTED, f"invoice {inv_id}")
    if grades is not None and grades.get("account") is Grade.VERIFIED:
        tracker.observe(account, Trust.SYSTEM, "vendor master, confirmed by investigation")
    payee = mandate.payee_by_account(account)
    facts = ActionFacts(
        action=ACTION, payee_id=payee.payee_id if payee else None, payee_category=payee.category if payee else None,
        counterparty_account=account, amount_minor=amount_minor, currency="EUR",
        evidence=dict(grades or {}), traced_args={"account": account},
    )
    labels = {"account": tracker.label(account)}
    return decide(mandate, facts, labels, ActionHistory(), now), facts, labels
