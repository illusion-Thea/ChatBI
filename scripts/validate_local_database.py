"""Validate the local business database through the application's read-only account."""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import pymysql
from sqlglot import parse

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COUNTS = {
    "regions": 50,
    "categories": 50,
    "products": 150,
    "customers": 250,
    "orders": 360,
    "order_items": 500,
}


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the Data Agent local business database")
    parser.add_argument("--host", default=os.getenv("BUSINESS_DB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BUSINESS_DB_PORT", "3307")))
    parser.add_argument("--database", default=os.getenv("BUSINESS_DB_NAME", "data_agent_local"))
    parser.add_argument("--user", default=os.getenv("BUSINESS_DB_USER", "data_agent_ro"))
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime" / "local-database.queries.json",
    )
    args = parser.parse_args()
    password = os.getenv("BUSINESS_DB_PASSWORD", "")
    if not password:
        raise SystemExit("BUSINESS_DB_PASSWORD is required")

    connection = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        database=args.database,
        charset="utf8mb4",
    )
    try:
        with connection.cursor() as cursor:
            counts: dict[str, int] = {}
            for table in EXPECTED_COUNTS:
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                counts[table] = int(cursor.fetchone()[0])
            if counts != EXPECTED_COUNTS:
                raise RuntimeError(f"unexpected row counts: {counts}")

            cursor.execute("SELECT name FROM regions WHERE id=1")
            first_region = str(cursor.fetchone()[0])
            if first_region != "北京城区":
                raise RuntimeError(f"UTF-8 round-trip failed: {first_region!r}")

            sql_text = (ROOT / "database" / "expected_queries.sql").read_text(encoding="utf-8")
            queries = [
                expression.sql(dialect="mysql", comments=False)
                for expression in parse(sql_text, read="mysql")
                if expression is not None
            ]
            results: list[dict[str, Any]] = []
            for index, sql in enumerate(queries, 1):
                cursor.execute(sql)
                rows = cursor.fetchall()
                if not rows:
                    raise RuntimeError(f"acceptance query Q{index:02d} returned no rows")
                results.append(
                    {
                        "id": f"Q{index:02d}",
                        "row_count": len(rows),
                        "first_row": [_json_value(value) for value in rows[0]],
                    }
                )

            cursor.execute("SHOW GRANTS FOR CURRENT_USER")
            grants = [str(row[0]) for row in cursor.fetchall()]
            write_denied = False
            write_error = ""
            try:
                cursor.execute("INSERT INTO regions(id,name) VALUES (999,'不应写入')")
            except Exception as exc:
                write_denied = True
                write_error = str(exc)
            if not write_denied:
                connection.rollback()
                raise RuntimeError("read-only account unexpectedly accepted INSERT")
    finally:
        connection.close()

    report = {
        "database": args.database,
        "counts": counts,
        "utf8_round_trip": first_region,
        "acceptance_queries": results,
        "grants": grants,
        "write_denied": write_denied,
        "write_error": write_error,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True))
    print(f"validation_report={args.output}")


if __name__ == "__main__":
    main()
