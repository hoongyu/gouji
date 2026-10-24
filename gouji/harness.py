"""One interface to the five systems, so every check is a SQL query that runs where the data lives.

`LocalHarness` attaches the sample systems to an in-memory DuckDB (sample mode: no network, no
keys). `ZetarisHarness` sends the same ANSI SQL to a Zetaris instance, which federates the same
sources in place. Checks only ever see `query()` and `fetch()`, never a connection.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

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


class ZetarisHarness(_SqlHarness):
    """The same queries against a Zetaris instance that federates the five systems in place.

    Configured from the environment: ZETARIS_HOST, ZETARIS_PORT, ZETARIS_USER, ZETARIS_PASSWORD,
    ZETARIS_CATALOG, and ZETARIS_TABLES (comma-separated `logical=qualified.name` pairs).
    """

    def __init__(self) -> None:
        host = os.environ.get("ZETARIS_HOST")
        if not host:
            raise RuntimeError("Zetaris is not configured: set ZETARIS_HOST and friends, or use sample mode")
        try:
            import trino  # type: ignore[import-not-found]
        except ImportError as exc:  # optional dependency
            raise RuntimeError("install the 'zetaris' extra (trino client) to query Zetaris") from exc
        conn = trino.dbapi.connect(
            host=host, port=int(os.environ.get("ZETARIS_PORT", "443")),
            user=os.environ.get("ZETARIS_USER", "gouji"),
            catalog=os.environ.get("ZETARIS_CATALOG"), http_scheme="https",
            auth=trino.auth.BasicAuthentication(os.environ.get("ZETARIS_USER", ""),
                                                os.environ.get("ZETARIS_PASSWORD", "")),
        )
        names = dict(pair.split("=", 1) for pair in os.environ.get("ZETARIS_TABLES", "").split(",") if "=" in pair)
        missing = sorted(set(TABLES) - set(names))
        if missing:
            raise RuntimeError(f"ZETARIS_TABLES is missing: {', '.join(missing)}")

        def run(sql: str, params: Sequence[Any]) -> list[dict[str, Any]]:
            cur = conn.cursor()
            cur.execute(sql, list(params))
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

        super().__init__(name="zetaris", table_names=names, run=run)


def open_harness(data_dir: Path) -> _SqlHarness:
    """Zetaris when it is configured, the local sample systems otherwise."""
    if os.environ.get("ZETARIS_HOST") and os.environ.get("SAMPLE_MODE", "").lower() not in {"1", "true"}:
        return ZetarisHarness()
    return LocalHarness(data_dir)
