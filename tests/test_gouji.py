import json
from datetime import timedelta
from pathlib import Path

import pytest
from engine.audit import AuditLog
from engine.mandate import Effect

from gouji.agents import filter_brief, verify
from gouji.checks import CHECKS, Citation, Finding, account_country
from gouji.contract import PaymentExecutor, issue_contract
from gouji.evaluate import evaluate
from gouji.harness import LocalHarness
from gouji.policy import build_mandate, decide_payment
from gouji.world import generate

KEY = b"test-key-0123456789abcdef"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    d = tmp_path_factory.mktemp("sample")
    generate(d)
    meta = json.loads((d / "cases.json").read_text(encoding="utf-8"))
    return d, meta


def test_normal_cases_raise_no_red_flag_and_every_attack_raises_one(world):
    d, meta = world
    from datetime import datetime
    now = datetime.fromisoformat(meta["now"])
    h = LocalHarness(d)
    for c in meta["cases"]:
        reds = [f for fn in CHECKS.values() for f in fn(h, c["inv_id"], now) if f.polarity == "red_flag"]
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


def test_executor_pays_only_with_a_valid_unused_contract_for_the_same_payment(world, tmp_path):
    d, meta = world
    from datetime import datetime
    now = datetime.fromisoformat(meta["now"])
    mandate = build_mandate(meta["registry_accounts"], now, investigated=False)
    pid, acct = next(iter(meta["registry_accounts"].items()))
    decision, facts, _ = decide_payment(mandate, inv_id="INV-X", account=acct, amount_minor=10_000, now=now, grades=None)
    assert decision.effect is Effect.ALLOW
    ex = PaymentExecutor(KEY, AuditLog(tmp_path / "audit.jsonl"))
    assert ex.pay(inv_id="INV-X", facts=facts, contract=None, now=now)["reason"] == "no execution contract"
    c = issue_contract(decision, facts, inv_id="INV-X", evidence_ids=[], mandate=mandate, now=now, key=KEY)
    bigger = facts.model_copy(update={"amount_minor": 99_999_00})
    assert ex.pay(inv_id="INV-X", facts=bigger, contract=c, now=now)["reason"] == "contract was issued for a different payment"
    assert ex.pay(inv_id="INV-X", facts=facts, contract=c, now=now + timedelta(hours=1))["reason"] == "contract expired"
    assert ex.pay(inv_id="INV-X", facts=facts, contract=c, now=now)["status"] == "paid"
    assert ex.pay(inv_id="INV-X", facts=facts, contract=c, now=now)["reason"] == "contract already used"
    forged = c.model_copy(update={"evidence_ids": ("F1",)})
    assert ex.pay(inv_id="INV-X", facts=facts, contract=forged, now=now)["reason"] == "contract signature does not match"


def test_no_contract_is_issued_for_a_decision_that_is_not_allow(world):
    d, meta = world
    from datetime import datetime
    now = datetime.fromisoformat(meta["now"])
    mandate = build_mandate(meta["registry_accounts"], now, investigated=False)
    decision, facts, _ = decide_payment(mandate, inv_id="INV-Y", account="LV00SYN00000000000099", amount_minor=10_000,
                                        now=now, grades=None)
    assert decision.effect is Effect.ASK
    with pytest.raises(ValueError):
        issue_contract(decision, facts, inv_id="INV-Y", evidence_ids=[], mandate=mandate, now=now, key=KEY)


def test_account_country():
    assert account_country("LV00SYN00000000000001") == "LV"
    assert account_country("SYNTTWTP/000-SYN-7781") == "TW"


def test_investigated_mandate_holds_every_sample_attack_and_releases_every_normal_payment(world, tmp_path):
    d, _ = world
    report = evaluate(d, tmp_path, "test")
    s = report["summary"]
    assert s["b3"]["attacks_auto_released"] == 0
    assert s["b3"]["normal_interrupted"] == 0
    assert s["b1"]["attacks_auto_released"] > 0  # the baseline really misses some
    assert all(r["b3"] == "ask" for r in report["cases"] if r["is_attack"])
