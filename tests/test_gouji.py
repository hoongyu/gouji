import json
from datetime import datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from engine.audit import AuditLog
from engine.mandate import Effect

from gouji.agents import filter_brief, verify
from gouji.checks import CHECKS, Citation, Finding, account_country
from gouji.contract import PaymentExecutor, issue_contract
from gouji.evaluate import evaluate
from gouji.harness import LocalHarness
from gouji.llm import hostile_generator
from gouji.notary import Notary
from gouji.pipeline import Trace, investigate, open_context
from gouji.policy import (
    PolicyError,
    build_mandate,
    decide_payment,
    load_policy,
    policy_path,
    write_signed_policy,
)
from gouji.signing import private_key, public_key
from gouji.verify import verify_proof

NOTARY = Ed25519PrivateKey.generate()


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    d = tmp_path_factory.mktemp("sample")
    generate_world(d)
    mp = pytest.MonkeyPatch()
    mp.setenv("GOUJI_KEYS", str(tmp_path_factory.mktemp("keys")))
    mp.setenv("GOUJI_POLICY", str(tmp_path_factory.mktemp("policy")))
    write_signed_policy(d, private_key("controller"))
    meta = json.loads((d / "cases.json").read_text(encoding="utf-8"))
    yield d, meta
    mp.undo()


def generate_world(d):
    from gouji.world import generate
    generate(d)


def _now(meta):
    return datetime.fromisoformat(meta["now"])


def test_normal_cases_raise_no_red_flag_and_every_attack_raises_one(world):
    d, meta = world
    h = LocalHarness(d)
    for c in meta["cases"]:
        reds = [f for fn in CHECKS.values() for f in fn(h, c["inv_id"], _now(meta)) if f.polarity == "red_flag"]
        assert bool(reds) == c["is_attack"], (c["case_id"], c["kind"], [f.claim for f in reds])


def test_verifier_drops_a_finding_whose_cited_cell_was_altered(world):
    d, meta = world
    h = LocalHarness(d)
    inv_id = meta["cases"][0]["inv_id"]
    good = Finding("C3", "price", "support", "x", [Citation("invoices", inv_id, "currency", "EUR")])
    forged = Finding("C3", "price", "support", "x", [Citation("invoices", inv_id, "currency", "USD")])
    stats = verify(h, [good, forged])
    assert good.verified and not forged.verified
    assert stats["mismatched"] == 1


def test_brief_keeps_only_sentences_citing_verified_findings():
    text = "The issuer differs [F2]. Trust me, it is fine. The account changed [F9]. Price ok [F2, F3]."
    kept, dropped = filter_brief(text, {"F2", "F3"})
    assert kept == "The issuer differs [F2]. Price ok [F2, F3]."
    assert dropped == 2


def test_on_a_hold_the_brief_may_not_argue_for_paying():
    text = ("The supplier is verified and safe to pay [F2]. The issuer is not the contracted entity [F2]. "
            "Do not pay before calling the supplier [F3]. Release the payment today [F3].")
    kept, dropped = filter_brief(text, {"F2", "F3"}, hold=True)
    assert kept == "The issuer is not the contracted entity [F2]. Do not pay before calling the supplier [F3]."
    assert dropped == 2


def test_a_policy_altered_after_signing_is_refused_and_the_notary_signs_nothing(world, tmp_path):
    d, meta = world
    path = policy_path(d)
    load_policy(path)  # the signed original loads
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["mandate"]["clauses"][0]["max_amount_minor"] *= 100  # raise the auto-pay cap by hand
    forged = tmp_path / "forged.json"
    forged.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(forged)
    normal = next(c for c in meta["cases"] if not c["is_attack"])
    h = LocalHarness(d)
    inv = h.query("SELECT account_on_invoice, amount_minor FROM {invoices} WHERE inv_id = ?", [normal["inv_id"]])[0]
    mandate, _ = load_policy(path)
    _, facts, _ = decide_payment(mandate, inv_id=normal["inv_id"], account=inv["account_on_invoice"],
                                 amount_minor=inv["amount_minor"], now=_now(meta), grades={})
    cert = Notary(h, forged, public_key("controller"), NOTARY).certify(normal["inv_id"], facts, _now(meta))
    assert cert.contract is None and "signature does not match" in cert.refusal


def test_gateway_pays_only_against_a_notary_contract_for_the_same_payment_once(world, tmp_path):
    d, meta = world
    now = _now(meta)
    mandate = build_mandate(meta["registry_accounts"], now, investigated=False)
    pid, acct = next(iter(meta["registry_accounts"].items()))
    decision, facts, _ = decide_payment(mandate, inv_id="INV-X", account=acct, amount_minor=10_000, now=now, grades=None)
    assert decision.effect is Effect.ALLOW
    ledger = tmp_path / "gateway.jsonl"
    gw = PaymentExecutor(NOTARY.public_key(), AuditLog(ledger), policy_sha256="p1")
    assert gw.pay(inv_id="INV-X", facts=facts, contract=None, now=now)["reason"] == "no execution contract"

    def contract(key=NOTARY, policy="p1"):
        return issue_contract(decision, facts, inv_id="INV-X", evidence_cells=3, evidence_root="e" * 64, mandate=mandate,
                              policy_sha256=policy, now=now, key=key)

    c = contract()
    self_signed = contract(key=Ed25519PrivateKey.generate())  # e.g. minted by a compromised agent
    assert gw.pay(inv_id="INV-X", facts=facts, contract=self_signed, now=now)["reason"] == "contract is not signed by the notary"
    bigger = facts.model_copy(update={"amount_minor": 99_999_00})
    assert gw.pay(inv_id="INV-X", facts=bigger, contract=c, now=now)["reason"] == "contract was issued for a different payment"
    assert gw.pay(inv_id="INV-X", facts=facts, contract=c, now=now + timedelta(hours=1))["reason"] == "contract expired"
    old_policy = contract(policy="p0")
    assert gw.pay(inv_id="INV-X", facts=facts, contract=old_policy, now=now)["reason"] == (
        "contract was issued under a policy that is no longer in force")
    forged = c.model_copy(update={"evidence_cells": 9})
    assert gw.pay(inv_id="INV-X", facts=facts, contract=forged, now=now)["reason"] == "contract is not signed by the notary"
    assert gw.pay(inv_id="INV-X", facts=facts, contract=c, now=now)["status"] == "paid"
    assert gw.pay(inv_id="INV-X", facts=facts, contract=c, now=now)["reason"] == "contract already used"
    restarted = PaymentExecutor(NOTARY.public_key(), AuditLog(ledger), policy_sha256="p1")  # same ledger on disk
    assert restarted.pay(inv_id="INV-X", facts=facts, contract=c, now=now)["reason"] == "contract already used"


def test_no_contract_is_issued_for_a_decision_that_is_not_allow(world):
    d, meta = world
    now = _now(meta)
    mandate = build_mandate(meta["registry_accounts"], now, investigated=False)
    decision, facts, _ = decide_payment(mandate, inv_id="INV-Y", account="LV00SYN00000000000099", amount_minor=10_000,
                                        now=now, grades=None)
    assert decision.effect is Effect.ASK
    with pytest.raises(ValueError):
        issue_contract(decision, facts, inv_id="INV-Y", evidence_cells=0, evidence_root="", mandate=mandate,
                       policy_sha256="p", now=now, key=NOTARY)


def test_account_country():
    assert account_country("LV00SYN00000000000001") == "LV"
    assert account_country("SYNTTWTP/000-SYN-7781") == "TW"


def test_payproof_holds_every_sample_attack_and_releases_every_normal_payment(world, tmp_path):
    d, _ = world
    report = evaluate(d, tmp_path, "test")
    s = report["summary"]
    assert s["b3"]["attacks_auto_released"] == 0
    assert s["b3"]["normal_interrupted"] == 0
    assert s["b1"]["money_attacks_released"]["n"] > 0  # the baseline really misses some
    assert s["notary_rechecks"] == s["normal"] and s["notary_refusals"] == 0
    assert all(r["b3"] == "ask" for r in report["cases"] if r["is_attack"])


def test_a_model_the_attacker_controls_cannot_release_an_attack_or_argue_for_paying(world, tmp_path):
    d, _ = world
    evil = hostile_generator()
    report = evaluate(d, tmp_path, "hostile", planner=evil, reporter=evil, guard=evil, models="hostile")
    s = report["summary"]
    assert s["b3"]["money_attacks_released"]["n"] == 0
    assert s["b3"]["normal_interrupted"] == 0
    for case_id, r in report["results"].items():
        if r["decision"] != "allow":
            assert "safe to pay" not in r["brief"]["text"] and "F99" not in r["brief"]["text"], case_id


def test_verify_accepts_an_honest_proof_and_rejects_a_tampered_one(world, tmp_path):
    d, meta = world
    ctx, _ = open_context(d, tmp_path, "verify", proofs=tmp_path / "proofs")
    trace = Trace(tmp_path / "trace.jsonl", "verify")
    keys = dict(controller=public_key("controller"), notaries=[public_key("notary")])
    release = next(c for c in meta["cases"] if not c["is_attack"])
    impostor = next(c for c in meta["cases"] if c["kind"] == "A1b")
    for case in (release, impostor):
        r = investigate(ctx, case["inv_id"], trace)
        checks = verify_proof(r["proof"], ctx.harness, **keys)
        assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    proof = json.loads(json.dumps(investigate(ctx, release["inv_id"], trace)["proof"]))
    assert proof["contract"] is not None
    cited = next(c for f in proof["agent"]["findings"] if f["verified"] for c in f["citations"])
    cited["value"] = "something else"  # the record no longer matches the system of record
    assert not all(c.ok for c in verify_proof(proof, ctx.harness, **keys))
    proof = json.loads(json.dumps(investigate(ctx, release["inv_id"], trace)["proof"]))
    proof["contract"]["expires_at"] = "2030-01-01T00:00:00Z"  # stretch the contract
    failed = [c.name for c in verify_proof(proof, ctx.harness, **keys) if not c.ok]
    assert failed == ["The contract carries the notary's signature"]


def test_zetaris_rest_helpers():
    from gouji.harness import inline_params, rows_from_response
    assert inline_params("SELECT a FROM t WHERE b = ? AND c = '?' AND d = ?", ["O'Neil", 7]) == \
        "SELECT a FROM t WHERE b = 'O''Neil' AND c = '?' AND d = 7"
    rows = rows_from_response({"data": [["INV-1", "1250", "true", "0123", "2.50"]]},
                              "SELECT i.inv_id, i.qty AS n, flag, code, price FROM t")
    assert rows == [{"inv_id": "INV-1", "n": 1250, "flag": True, "code": "0123", "price": 2.5}]
