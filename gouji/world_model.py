"""Meterless World Model, minimum set, implemented from the hackathon's agent-engine guide.

The three services keep the guide's names:

- WorldStoreService      canonical entities and relationships, each with provenance, content-hash
                         ids, and an append-only JSONL log the canonical view can be rebuilt from.
- IngestPipelineService  reconcile -> cluster -> persist -> infer(alerts) for one request, reading
                         the rows it needs through the harness (so in production, through Zetaris).
- ContextBuilderService  a structured context for the planner and the reporter, with a
                         selectionReason for every item.

Legal entities are keyed by registration number and jurisdiction, never by name. That is the point:
two companies with the same name are two entities, and the alert that says so is what catches a
doppelganger supplier.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from gouji.checks import CHANGE_WINDOW_DAYS, account_country
from gouji.harness import Harness


def stable_id(kind: str, key: str) -> str:
    return f"{kind[:3].lower()}_{hashlib.sha256(f'{kind}|{key}'.lower().encode()).hexdigest()[:12]}"


def norm_name(name: str) -> str:
    return " ".join(name.lower().replace(",", " ").replace(".", " ").split())


@dataclass
class Provenance:
    system: str
    table: str
    pk: str


@dataclass
class Entity:
    id: str
    kind: str  # LegalEntity | BankAccount | VendorRecord | Invoice | Contract | EmailDomain
    key: str
    attrs: dict[str, Any]
    provenance: list[Provenance] = field(default_factory=list)


@dataclass
class Relation:
    kind: str  # issued_by | pays_to | claims_to_be | contract_with | sent_from | changed_by_request
    src: str
    dst: str
    provenance: Provenance
    valid_from: str | None = None  # bitemporal: when it became true in the world ...
    recorded_at: str | None = None  # ... and when the source recorded it


@dataclass
class Alert:
    kind: str  # doppelganger | account_jurisdiction_mismatch | unverified_account_change
    aspect: str  # which evidence aspect it weakens
    message: str
    entities: list[str]
    provenance: list[Provenance]


class WorldStoreService:
    def __init__(self, log_path: Path | None = None) -> None:
        self.entities: dict[str, Entity] = {}
        self.relations: list[Relation] = []
        self._log_path = log_path
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, op: str, payload: dict[str, Any]) -> None:
        if self._log_path:
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"op": op, **payload}, default=str, ensure_ascii=False) + "\n")

    def upsert(self, kind: str, key: str, attrs: dict[str, Any], prov: Provenance) -> Entity:
        eid = stable_id(kind, key)
        ent = self.entities.get(eid)
        if ent is None:
            ent = Entity(eid, kind, key, dict(attrs), [prov])
            self.entities[eid] = ent
            self._append("entity", asdict(ent))
        else:
            ent.attrs.update({k: v for k, v in attrs.items() if v is not None})
            if prov not in ent.provenance:
                ent.provenance.append(prov)
                self._append("provenance", {"id": eid, **asdict(prov)})
        return ent

    def relate(self, rel: Relation) -> None:
        if rel not in self.relations:
            self.relations.append(rel)
            self._append("relation", asdict(rel))

    def of_kind(self, kind: str) -> list[Entity]:
        return [e for e in self.entities.values() if e.kind == kind]

    def related(self, src: str, kind: str) -> list[Entity]:
        return [self.entities[r.dst] for r in self.relations if r.src == src and r.kind == kind]


class IngestPipelineService:
    def __init__(self, store: WorldStoreService) -> None:
        self.store = store

    def ingest(self, h: Harness, inv_id: str, now: datetime) -> list[Alert]:
        s = self.store
        rows = h.query(
            "SELECT i.inv_id, i.issuer_name, i.issuer_reg_no, i.account_on_invoice, i.received_at, i.email_id, "
            "p.po_id, v.vendor_id, v.legal_name, v.reg_no, v.country, v.account AS master_account, "
            "c.contract_id, c.vendor_reg_no AS contract_reg_no, c.jurisdiction "
            "FROM {invoices} i JOIN {purchase_orders} p ON p.po_id = i.po_ref "
            "JOIN {vendors} v ON v.vendor_id = p.vendor_id "
            "LEFT JOIN {contracts} c ON c.vendor_reg_no = v.reg_no AND c.item = p.item AND c.amendment_of IS NULL "
            "WHERE i.inv_id = ?",
            [inv_id],
        )
        if not rows:
            return []
        r = rows[0]
        # reconcile: every row becomes an entity keyed by what identifies it in the world
        inv = s.upsert("Invoice", r["inv_id"], {"issuer_name": r["issuer_name"]}, Provenance("erp", "invoices", r["inv_id"]))
        issuer = s.upsert("LegalEntity", f"{r['issuer_reg_no']}", {"name": r["issuer_name"], "reg_no": r["issuer_reg_no"]},
                          Provenance("erp", "invoices", r["inv_id"]))
        s.relate(Relation("issued_by", inv.id, issuer.id, Provenance("erp", "invoices", r["inv_id"]),
                          recorded_at=str(r["received_at"])))
        acct = s.upsert("BankAccount", r["account_on_invoice"], {"country": account_country(r["account_on_invoice"])},
                        Provenance("erp", "invoices", r["inv_id"]))
        s.relate(Relation("pays_to", inv.id, acct.id, Provenance("erp", "invoices", r["inv_id"])))
        supplier = None
        if r["contract_id"]:
            supplier = s.upsert("LegalEntity", r["contract_reg_no"],
                                {"name": r["legal_name"], "reg_no": r["contract_reg_no"], "jurisdiction": r["jurisdiction"]},
                                Provenance("contracts", "contracts", r["contract_id"]))
            con = s.upsert("Contract", r["contract_id"], {"item_vendor": r["vendor_id"]},
                           Provenance("contracts", "contracts", r["contract_id"]))
            s.relate(Relation("contract_with", con.id, supplier.id, Provenance("contracts", "contracts", r["contract_id"])))
        rec = s.upsert("VendorRecord", r["vendor_id"], {"account": r["master_account"]},
                       Provenance("vendor_master", "vendors", r["vendor_id"]))
        on_file = s.upsert("LegalEntity", r["reg_no"], {"name": r["legal_name"], "reg_no": r["reg_no"], "jurisdiction": r["country"]},
                           Provenance("vendor_master", "vendors", r["vendor_id"]))
        s.relate(Relation("claims_to_be", rec.id, on_file.id, Provenance("vendor_master", "vendors", r["vendor_id"])))
        for reg in h.query("SELECT reg_no, legal_name, jurisdiction, incorporated_on FROM {registry} "
                           "WHERE lower(legal_name) = lower(?)", [r["issuer_name"]]):
            s.upsert("LegalEntity", reg["reg_no"],
                     {"name": reg["legal_name"], "reg_no": reg["reg_no"], "jurisdiction": reg["jurisdiction"],
                      "incorporated_on": reg["incorporated_on"]}, Provenance("registry", "registry", reg["reg_no"]))
        changes = h.query(
            "SELECT change_id, new_value, callback_verified, changed_at FROM {vendor_changes} "
            "WHERE vendor_id = ? AND field = 'account' ORDER BY changed_at DESC LIMIT 1", [r["vendor_id"]])
        for ch in changes:
            new_acct = s.upsert("BankAccount", ch["new_value"], {"country": account_country(ch["new_value"])},
                                Provenance("vendor_master", "vendor_changes", ch["change_id"]))
            s.relate(Relation("changed_by_request", rec.id, new_acct.id,
                              Provenance("vendor_master", "vendor_changes", ch["change_id"]),
                              valid_from=str(ch["changed_at"]), recorded_at=str(ch["changed_at"])))

        # cluster + infer: alerts are derived from the canonical view, not from any single source
        alerts: list[Alert] = []
        same_name = [e for e in s.of_kind("LegalEntity") if norm_name(e.attrs.get("name", "")) == norm_name(r["issuer_name"])]
        if supplier and issuer.id != supplier.id and len(same_name) > 1:
            alerts.append(Alert(
                "doppelganger", "identity",
                f"'{r['issuer_name']}' resolves to {len(same_name)} legal entities. The contract is with "
                f"{supplier.key} ({supplier.attrs.get('jurisdiction')}); this invoice is issued by {issuer.key} "
                f"({issuer.attrs.get('jurisdiction', '?')}).",
                [e.id for e in same_name], [p for e in same_name for p in e.provenance]))
        if supplier and acct.attrs.get("country") and acct.attrs["country"] != supplier.attrs.get("jurisdiction"):
            alerts.append(Alert(
                "account_jurisdiction_mismatch", "account",
                f"The paying account is in {acct.attrs['country']}; the contracted entity {supplier.key} is in "
                f"{supplier.attrs.get('jurisdiction')}.", [acct.id, supplier.id], acct.provenance + supplier.provenance))
        for ch in changes:
            fresh = now - datetime.fromisoformat(str(ch["changed_at"])) < timedelta(days=CHANGE_WINDOW_DAYS)
            if fresh and not ch["callback_verified"] and ch["new_value"] == r["account_on_invoice"]:
                alerts.append(Alert(
                    "unverified_account_change", "account",
                    f"{r['vendor_id']} switched to this account recently without a callback.",
                    [rec.id], [Provenance("vendor_master", "vendor_changes", ch["change_id"])]))
        for a in alerts:
            s._append("alert", {"inv_id": inv_id, **asdict(a)})
        return alerts


class ContextBuilderService:
    def __init__(self, store: WorldStoreService) -> None:
        self.store = store

    def build(self, inv_id: str, alerts: list[Alert]) -> dict[str, Any]:
        s = self.store
        inv = s.entities.get(stable_id("Invoice", inv_id))
        if inv is None:
            return {"inv_id": inv_id, "items": [], "alerts": []}
        items = []
        for rel in [r for r in s.relations if r.src == inv.id]:
            e = s.entities[rel.dst]
            items.append({"entity": e.key, "kind": e.kind, "attrs": e.attrs,
                          "selectionReason": f"directly linked to the invoice by '{rel.kind}'",
                          "provenance": [asdict(p) for p in e.provenance]})
        for a in alerts:
            for eid in a.entities:
                e = s.entities[eid]
                items.append({"entity": e.key, "kind": e.kind, "attrs": e.attrs,
                              "selectionReason": f"named in a '{a.kind}' alert",
                              "provenance": [asdict(p) for p in e.provenance]})
        return {"inv_id": inv_id, "items": items,
                "alerts": [{"kind": a.kind, "aspect": a.aspect, "message": a.message} for a in alerts]}
