"""Put the five sample systems where Zetaris can federate them, register them, and check the result.

    python scripts/zetaris_sources.py up        generate local passwords, start PostgreSQL and an S3 store
    python scripts/zetaris_sources.py load      ERP and vendor master into PostgreSQL, documents into S3
    python scripts/zetaris_sources.py sql       print the Zetaris registration statements (passwords masked)
    python scripts/zetaris_sources.py register  run them on Zetaris through the REST API
    python scripts/zetaris_sources.py check     SELECT 1, SHOW LIGHTNING DATABASES, row counts against local

On this path timestamps are stored as ISO-8601 text, so every engine compares and returns them alike.
Loading goes through DuckDB's postgres and httpfs extensions; nothing new to pip install.
"""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gouji.harness import TABLES, LocalHarness, ZetarisHarness, zetaris_post  # noqa: E402
from gouji.llm import load_dotenv  # noqa: E402

HERE = ROOT / "deploy" / "zetaris-sources"
ENV = HERE / ".env"
BUCKET = "gouji"
DATABASES = {"erp": ("erp.duckdb", ["purchase_orders", "goods_receipts", "invoices", "payments"]),
             "vendor_master": ("vendor_master.duckdb", ["vendors", "vendor_changes"])}
# Zetaris runs in Docker; this is how its containers reach ports published on the host.
HOST_FROM_ZETARIS = "host.docker.internal"


def creds() -> dict[str, str]:
    if not ENV.exists():
        sys.exit("no deploy/zetaris-sources/.env yet: run `python scripts/zetaris_sources.py up` first")
    return dict(line.split("=", 1) for line in ENV.read_text(encoding="utf-8").splitlines() if "=" in line)


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=HERE, check=True)


def up() -> None:
    if not ENV.exists():
        ENV.write_text(f"GOUJI_PG_PASSWORD={secrets.token_urlsafe(18)}\nGOUJI_S3_PASSWORD={secrets.token_urlsafe(18)}\n",
                       encoding="utf-8")
    compose("up", "-d")
    print("PostgreSQL on localhost:5433, S3 on localhost:9000; passwords in deploy/zetaris-sources/.env")


def _iso_select(con: duckdb.DuckDBPyConnection, relation: str) -> str:
    """SELECT list that turns timestamps and dates into ISO-8601 text."""
    cols = []
    for name, typ, *_ in con.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall():
        if typ.startswith("TIMESTAMP"):
            cols.append(f"strftime({name}, '%Y-%m-%dT%H:%M:%S.%f') || '+00:00' AS {name}")
        elif typ == "DATE":
            cols.append(f"strftime({name}, '%Y-%m-%d') AS {name}")
        else:
            cols.append(name)
    return ", ".join(cols)


def load(data: Path) -> None:
    c = creds()
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    for ext in ("postgres", "httpfs"):
        con.execute(f"INSTALL {ext}; LOAD {ext}")
    pg = f"host=localhost port=5433 user=gouji password={c['GOUJI_PG_PASSWORD']}"
    for db, (file, tables) in DATABASES.items():
        # CREATE DATABASE cannot run inside a transaction, so it goes through psql in the container
        exists = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "gouji", "-d", "postgres",
                                 "-tAc", f"SELECT 1 FROM pg_database WHERE datname = '{db}'"],
                                cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()
        if not exists:
            subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "gouji", "-d", "postgres",
                            "-c", f"CREATE DATABASE {db}"], cwd=HERE, check=True, capture_output=True)
        con.execute(f"ATTACH '{(data / file).as_posix()}' AS src_{db} (READ_ONLY)")
        con.execute(f"ATTACH '{pg} dbname={db}' AS pg_{db} (TYPE postgres)")
        for t in tables:
            con.execute(f"DROP TABLE IF EXISTS pg_{db}.public.{t}")
            con.execute(f"CREATE TABLE pg_{db}.public.{t} AS SELECT {_iso_select(con, f'src_{db}.{t}')} FROM src_{db}.{t}")
            print(f"postgres {db}.{t}: {con.execute(f'SELECT count(*) FROM pg_{db}.public.{t}').fetchone()[0]} rows")

    # the S3 store creates the bucket at startup (docker-compose.yml)
    con.execute(f"CREATE SECRET s3 (TYPE s3, KEY_ID 'gouji', SECRET '{c['GOUJI_S3_PASSWORD']}', "
                "ENDPOINT 'localhost:9000', URL_STYLE 'path', USE_SSL false, REGION 'us-east-1')")
    d = data.resolve().as_posix()
    files = {
        "contracts.parquet": (f"read_parquet('{d}/contracts.parquet')", "(FORMAT PARQUET)"),
        "registry.csv": (f"read_csv('{d}/registry.csv', header=true, all_varchar=true)", "(FORMAT CSV, HEADER)"),
        # one JSON array: Zetaris reads JSON files as a single document, so line-delimited JSON gives one row
        "mailbox.json": (f"read_json_auto('{d}/mailbox.jsonl', format='newline_delimited')", "(FORMAT JSON, ARRAY true)"),
    }
    for name, (rel, fmt) in files.items():
        con.execute(f"COPY (SELECT {_iso_select(con, rel)} FROM {rel}) TO 's3://{BUCKET}/{name}' {fmt}")
        print(f"s3://{BUCKET}/{name}: {con.execute(f'SELECT count(*) FROM {rel}').fetchone()[0]} rows")


def statements(mask: bool) -> list[str]:
    c = {} if mask else creds()
    pg_pw = "<GOUJI_PG_PASSWORD>" if mask else c["GOUJI_PG_PASSWORD"]
    s3_pw = "<GOUJI_S3_PASSWORD>" if mask else c["GOUJI_S3_PASSWORD"]
    out = []
    # Zetaris accepts only letters, digits and _ . - , in a description
    for db, label in (("erp", "Veltrona-ERP-PostgreSQL"), ("vendor_master", "Veltrona-vendor-master-PostgreSQL")):
        out += [f'CREATE DATASOURCE {db} DESCRIBE BY "{label}" OPTIONS ('
                f'jdbcdriver "org.postgresql.Driver", jdbcurl "jdbc:postgresql://{HOST_FROM_ZETARIS}:5433/{db}", '
                f'username "gouji", password "{pg_pw}", fetchsize "1000")',
                f"REGISTER DATASOURCE TABLES FROM {db}"]
    out.append('CREATE LIGHTNING DATABASE documents DESCRIBE BY "Contracts-AP-mailbox-and-company-registry-files-on-S3"')
    s3 = (f'awsAccessKeyId "gouji", awsSecretAccessKey "{s3_pw}", s3Endpoint "http://{HOST_FROM_ZETARIS}:9000", '
          'useS3PathStyleAccess "true"')
    out += [f'CREATE LIGHTNING FILESTORE TABLE contracts FROM documents FORMAT PARQUET OPTIONS ('
            f'path "s3a://{BUCKET}/contracts.parquet", {s3})',
            f'CREATE LIGHTNING FILESTORE TABLE registry FROM documents FORMAT CSV OPTIONS ('
            f'path "s3a://{BUCKET}/registry.csv", header "true", inferSchema "false", {s3})',
            f'CREATE LIGHTNING FILESTORE TABLE mailbox FROM documents FORMAT JSON OPTIONS ('
            f'path "s3a://{BUCKET}/mailbox.json", {s3})']
    return out


def register() -> None:
    for stmt in statements(mask=False):
        shown = next(m for m in statements(mask=True) if m.split(" OPTIONS")[0] == stmt.split(" OPTIONS")[0])
        print(f"> {shown[:110]}")
        print(f"  {json.dumps(zetaris_post(stmt), default=str)[:300]}")


def check(data: Path) -> None:
    print("SELECT 1:", json.dumps(zetaris_post("SELECT 1 AS one"))[:200])
    print("SHOW LIGHTNING DATABASES:", json.dumps(zetaris_post("SHOW LIGHTNING DATABASES"))[:400])
    z, local = ZetarisHarness(), LocalHarness(data)
    for t in TABLES:
        try:
            n = z.query(f"SELECT COUNT(*) AS n FROM {{{t}}}")[0]["n"]
        except RuntimeError as exc:
            n = f"error: {exc}"
        print(f"{t:<16} zetaris {n!s:<8} local {local.query(f'SELECT COUNT(*) AS n FROM {{{t}}}')[0]['n']}")


def _masked(exc: BaseException) -> str:
    text = str(exc)
    for secret in creds().values() if ENV.exists() else ():
        text = text.replace(secret, "********")
    return text


def main() -> None:
    load_dotenv(ROOT / ".env")
    try:
        _main()
    except (duckdb.Error, RuntimeError, subprocess.CalledProcessError) as exc:
        sys.exit(f"{type(exc).__name__}: {_masked(exc)}")


def _main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    data = ROOT / (sys.argv[2] if len(sys.argv) > 2 else "data/sample")
    if cmd == "up":
        up()
    elif cmd == "load":
        load(data)
    elif cmd == "sql":
        print(";\n\n".join(statements(mask=True)) + ";")
    elif cmd == "register":
        register()
    elif cmd == "check":
        check(data)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
