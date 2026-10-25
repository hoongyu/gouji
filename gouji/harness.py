"""One interface to the five systems, so every check is a SQL query that runs where the data lives.

`LocalHarness` attaches the sample systems to an in-memory DuckDB (sample mode: no network, no
keys). `ZetarisHarness` sends the same ANSI SQL to a Zetaris instance, which federates the same
sources in place. Checks only ever see `query()` and `fetch()`, never a connection.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import duckdb

# logical table -> (system it belongs to, primary key)
TABLES: dict[str, tuple[str, str]] = {
    "purchase_orders": ("erp", "po_id"),
    "goods_receipts": ("erp", "gr_id"),
    "invoices": ("erp", "inv_id"),
    "payments": ("erp", "pay_id"),
    "vendors": ("vendor_master", "vendor_id"),
    "vendor_changes": ("vendor_master", "change_id"),
    "contracts": ("contracts", "contract_id"),
    "mailbox": ("mailbox", "email_id"),
    "registry": ("registry", "reg_no"),
}
TRUSTED_SYSTEMS = frozenset({"erp", "vendor_master", "contracts", "registry"})  # the mailbox is not


@dataclass
class QueryLog:
    sql: str
    params: tuple[Any, ...]
    rows: int
    ms: float
    systems: tuple[str, ...]


class Harness(Protocol):
    name: str
    log: list[QueryLog]

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]: ...
    def fetch(self, table: str, pk_value: Any) -> dict[str, Any] | None: ...


@dataclass
class _SqlHarness:
    name: str
    table_names: dict[str, str]
    run: Callable[[str, Sequence[Any]], list[dict[str, Any]]]
    log: list[QueryLog] = field(default_factory=list)

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        """`sql` names tables as {invoices}, {vendors}, ...; they are resolved per backend."""
        systems = tuple(sorted({TABLES[t][0] for t in TABLES if f"{{{t}}}" in sql}))
        resolved = sql.format(**self.table_names)
        t0 = time.perf_counter()
        rows = self.run(resolved, tuple(params))
        self.log.append(QueryLog(resolved, tuple(params), len(rows), (time.perf_counter() - t0) * 1000, systems))
        return rows

    def fetch(self, table: str, pk_value: Any) -> dict[str, Any] | None:
        _, pk = TABLES[table]
        rows = self.query(f"SELECT * FROM {{{table}}} WHERE {pk} = ?", [pk_value])
        return rows[0] if rows else None


class LocalHarness(_SqlHarness):
    """The five sample systems, attached read-only to an in-memory DuckDB."""

    def __init__(self, data_dir: Path) -> None:
        con = duckdb.connect()
        con.execute("SET TimeZone = 'UTC'")  # every case is judged in UTC; show times the same way
        d = data_dir.resolve().as_posix()
        con.execute(f"ATTACH '{d}/erp.duckdb' AS erp (READ_ONLY)")
        con.execute(f"ATTACH '{d}/vendor_master.duckdb' AS vm (READ_ONLY)")
        con.execute(f"CREATE VIEW contracts AS SELECT * FROM read_parquet('{d}/contracts.parquet')")
        con.execute(f"CREATE VIEW registry AS SELECT * FROM read_csv('{d}/registry.csv', header=true, all_varchar=true)")
        con.execute(f"CREATE VIEW mailbox AS SELECT * FROM read_json_auto('{d}/mailbox.jsonl', format='newline_delimited')")
        self._con = con

        def run(sql: str, params: Sequence[Any]) -> list[dict[str, Any]]:
            cur = self._con.execute(sql, list(params))
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

        names = {
            "purchase_orders": "erp.purchase_orders", "goods_receipts": "erp.goods_receipts",
            "invoices": "erp.invoices", "payments": "erp.payments", "vendors": "vm.vendors",
            "vendor_changes": "vm.vendor_changes", "contracts": "contracts", "mailbox": "mailbox",
            "registry": "registry",
        }
        super().__init__(name="local-duckdb", table_names=names, run=run)


# Where the nine tables live once registered in Zetaris: two databases (ERP, vendor master) and one store of
# documents (contracts, mailbox, registry). Override any of them with ZETARIS_TABLES=logical=qualified,...
ZETARIS_TABLES = {
    "purchase_orders": "erp.purchase_orders", "goods_receipts": "erp.goods_receipts", "invoices": "erp.invoices",
    "payments": "erp.payments", "vendors": "vendor_master.vendors", "vendor_changes": "vendor_master.vendor_changes",
    "contracts": "documents.contracts", "mailbox": "documents.mailbox", "registry": "documents.registry",
}


class ZetarisHarness(_SqlHarness):
    """The same queries against a Zetaris instance that federates the five systems in place.

    Talks to the Zetaris REST API (POST {ZETARIS_REST_URL}/sql-editor/sqls/run with a bearer API key
    and X-Org-ID), so no Java or JDBC driver is needed. Configured from the environment:
    ZETARIS_REST_URL, ZETARIS_ORG_ID, ZETARIS_API_KEY, and optionally ZETARIS_TABLES. The API takes no bound parameters, so values are inlined as
    escaped literals, and it returns every value as a string, so values are typed back here.
    """

    def __init__(self) -> None:
        zetaris_config()  # fail early, with a clear message, when the instance is not configured
        names = dict(ZETARIS_TABLES)
        names.update(pair.split("=", 1) for pair in os.environ.get("ZETARIS_TABLES", "").split(",") if "=" in pair)

        def run(sql: str, params: Sequence[Any]) -> list[dict[str, Any]]:
            text = inline_params(sql, params)
            return rows_from_response(zetaris_post(text), text)

        super().__init__(name="zetaris", table_names=names, run=run)


def zetaris_config() -> tuple[str, str, str, float]:
    base, key = os.environ.get("ZETARIS_REST_URL", "").rstrip("/"), os.environ.get("ZETARIS_API_KEY", "")
    if not base or not key:
        raise RuntimeError("Zetaris is not configured: set ZETARIS_REST_URL and ZETARIS_API_KEY, or use sample mode")
    return base, key, os.environ.get("ZETARIS_ORG_ID", "1"), float(os.environ.get("ZETARIS_TIMEOUT", "60"))


def zetaris_post(sql: str, limit: int = 10000) -> Any:
    """Run one Lightning SQL statement through the Zetaris REST API and return the decoded response."""
    base, key, org, timeout = zetaris_config()
    body = json.dumps({"queryId": str(uuid.uuid4()), "sql": sql, "source": "SqlEditor", "limit": limit})
    req = Request(f"{base}/sql-editor/sqls/run", data=body.encode(), method="POST", headers={
        "Authorization": f"Bearer {key}", "X-Org-ID": org, "X-Request-ID": str(uuid.uuid4()),
        "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode() or "null")
    except HTTPError as exc:
        raise RuntimeError(f"Zetaris HTTP {exc.code}: {exc.read().decode(errors='replace')[:300]}") from exc
    except (URLError, OSError) as exc:
        raise RuntimeError(f"cannot reach Zetaris at {base}: {getattr(exc, 'reason', exc)}") from exc


def _literal(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def inline_params(sql: str, params: Sequence[Any]) -> str:
    """Replace each ? outside quotes with an escaped literal, in order."""
    out, it, quote = [], iter(params), None
    for ch in sql:
        if quote:
            quote = None if ch == quote else quote
            out.append(ch)
        elif ch in "'\"":
            quote = ch
            out.append(ch)
        elif ch == "?":
            out.append(_literal(next(it)))
        else:
            out.append(ch)
    return "".join(out)


_NUMBER = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?")


def _typed(v: Any) -> Any:
    """REST returns strings: give numbers and booleans back their type, leave ids (even 0123) alone."""
    if not isinstance(v, str):
        return v
    if v in ("true", "false"):
        return v == "true"
    if not _NUMBER.fullmatch(v):
        return v
    if "." not in v and "e" not in v.lower():
        return int(v)
    f = float(v)
    return int(f) if f.is_integer() and "e" in v.lower() else f


def _select_names(sql: str) -> list[str]:
    """Column names from an explicit SELECT list (alias, or the part after the last dot)."""
    head = sql.split(" FROM ", 1)[0].split("SELECT", 1)[-1]
    parts, depth, cur = [], 0, ""
    for ch in head:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    names = []
    for part in parts:
        part = part.strip()
        alias = part.rsplit(" AS ", 1)[-1] if " AS " in part else part.split(".")[-1]
        names.append(alias.strip().strip('"`'))
    return names


def rows_from_response(out: Any, sql: str) -> list[dict[str, Any]]:
    data = out.get("data") if isinstance(out, dict) else out
    if not data:
        return []
    if isinstance(data[0], dict):
        return [{k: _typed(v) for k, v in row.items()} for row in data]
    cols = None
    for k in ("columns", "columnNames", "header", "headers", "schema", "fields"):
        meta = out.get(k) if isinstance(out, dict) else None
        if meta:
            cols = [c.get("name") if isinstance(c, dict) else str(c) for c in meta]
            break
    if cols is None:
        cols = _select_names(sql)
        if "*" in cols:
            raise RuntimeError("Zetaris returned no column names for a SELECT * query")
    return [dict(zip(cols, (_typed(v) for v in row))) for row in data]


def open_harness(data_dir: Path) -> _SqlHarness:
    """GOUJI_BACKEND=local or zetaris picks one; auto (the default) uses Zetaris when it is configured and
    sample mode is off, and the local sample systems otherwise."""
    backend = os.environ.get("GOUJI_BACKEND", "auto").lower()
    configured = bool(os.environ.get("ZETARIS_REST_URL") and os.environ.get("ZETARIS_API_KEY"))
    sample = os.environ.get("SAMPLE_MODE", "").lower() in {"1", "true", "yes"}
    if backend == "zetaris" or (backend == "auto" and configured and not sample):
        return ZetarisHarness()
    return LocalHarness(data_dir)
