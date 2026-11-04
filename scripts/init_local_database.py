"""Safely initialize the local MySQL business database and read-only account."""

from __future__ import annotations

import argparse
import json
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pymysql

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
TABLES = ("regions", "categories", "products", "customers", "orders", "order_items")


def _identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise SystemExit(f"{label} must match {IDENTIFIER.pattern}")
    return value


def _statements(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("--")]
    return [part.strip() for part in "\n".join(lines).split(";") if part.strip()]


def _validate(connection: pymysql.Connection[Any], database: str) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(f"USE `{database}`")
        counts: dict[str, int] = {}
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            counts[table] = int(cursor.fetchone()[0])
        expected = {
            "regions": 50,
            "categories": 50,
            "products": 150,
            "customers": 250,
            "orders": 360,
            "order_items": 500,
        }
        if counts != expected:
            raise RuntimeError(f"row counts differ: expected={expected}, actual={counts}")
        checks = {
            "orphan_customers": (
                "SELECT COUNT(*) FROM customers c "
                "LEFT JOIN regions r ON r.id=c.region_id WHERE r.id IS NULL"
            ),
            "orphan_products": (
                "SELECT COUNT(*) FROM products p "
                "LEFT JOIN categories c ON c.id=p.category_id WHERE c.id IS NULL"
            ),
            "orphan_orders": (
                "SELECT COUNT(*) FROM orders o "
                "LEFT JOIN customers c ON c.id=o.customer_id WHERE c.id IS NULL"
            ),
            "orphan_items": (
                "SELECT COUNT(*) FROM order_items i "
                "LEFT JOIN orders o ON o.id=i.order_id "
                "LEFT JOIN products p ON p.id=i.product_id "
                "WHERE o.id IS NULL OR p.id IS NULL"
            ),
            "orders_before_registration": (
                "SELECT COUNT(*) FROM orders o "
                "JOIN customers c ON c.id=o.customer_id "
                "WHERE DATE(o.created_at)<c.registered_at"
            ),
            "payment_before_order": "SELECT COUNT(*) FROM orders WHERE paid_at<created_at",
            "order_amount_mismatch": (
                "SELECT COUNT(*) FROM orders o JOIN "
                "(SELECT order_id,SUM(ROUND(quantity*unit_price*(1-discount),2)) total "
                "FROM order_items GROUP BY order_id) i ON i.order_id=o.id "
                "WHERE o.amount<>i.total"
            ),
        }
        results: dict[str, int] = {}
        for name, sql in checks.items():
            cursor.execute(sql)
            results[name] = int(cursor.fetchone()[0])
        if any(results.values()):
            raise RuntimeError(f"data integrity checks failed: {results}")
        cursor.execute("SELECT VERSION()")
        version = str(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*), ROUND(SUM(amount),2) FROM orders WHERE status='PAID'")
        paid_orders, paid_revenue = cursor.fetchone()
    return {
        "database": database,
        "mysql_version": version,
        "counts": counts,
        "checks": results,
        "paid_orders": int(paid_orders),
        "paid_revenue": str(Decimal(paid_revenue)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the Data Agent local MySQL database")
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--admin-user", default=os.getenv("MYSQL_ADMIN_USER", "root"))
    parser.add_argument("--database", default=os.getenv("BUSINESS_DB_NAME", "data_agent_local"))
    parser.add_argument("--readonly-user", default=os.getenv("BUSINESS_DB_USER", "data_agent_ro"))
    parser.add_argument(
        "--recreate", action="store_true", help="drop and recreate only the named target database"
    )
    args = parser.parse_args()

    database = _identifier(args.database, "database")
    readonly_user = _identifier(args.readonly_user, "readonly user")
    admin_password = os.getenv("MYSQL_ADMIN_PASSWORD", "")
    readonly_password = os.getenv("BUSINESS_DB_PASSWORD", "")
    if len(readonly_password) < 12:
        raise SystemExit("BUSINESS_DB_PASSWORD must be provided and contain at least 12 characters")

    connection = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.admin_user,
        password=admin_password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW DATABASES LIKE %s", (database,))
            exists = cursor.fetchone() is not None
            if exists and not args.recreate:
                raise SystemExit(
                    f"database {database!r} already exists; refusing to overwrite "
                    "(use --recreate explicitly)"
                )
            if exists:
                cursor.execute(f"DROP DATABASE `{database}`")
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(f"USE `{database}`")
            for path in (ROOT / "database" / "schema.sql", ROOT / "database" / "seed.sql"):
                for statement in _statements(path):
                    cursor.execute(statement)
            cursor.execute(
                f"CREATE USER IF NOT EXISTS '{readonly_user}'@'127.0.0.1' IDENTIFIED BY %s",
                (readonly_password,),
            )
            cursor.execute(
                f"ALTER USER '{readonly_user}'@'127.0.0.1' IDENTIFIED BY %s",
                (readonly_password,),
            )
            cursor.execute(
                f"GRANT SELECT, SHOW VIEW ON `{database}`.* TO '{readonly_user}'@'127.0.0.1'"
            )
        report = _validate(connection, database)
    finally:
        connection.close()

    output = ROOT / ".runtime" / "local-database.validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    print(f"validation_report={output}")


if __name__ == "__main__":
    main()
