"""Run the ten rules-mode questions through the authenticated HTTP API."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = [
    "今年每个月的已支付销售额是多少？",
    "本季度各区域销售额对比",
    "销售额最高的前 10 个商品",
    "各商品品类的销售额和订单量",
    "不同下单渠道的销售额占比",
    "各客户分层的客单价是多少？",
    "今年每月新增客户数",
    "各品类的销售毛利是多少？",
    "已支付订单总数是多少？",
    "退款订单率是多少？",
]


def _summary(record: dict[str, Any], question: str) -> dict[str, Any]:
    result = record.get("result") or {}
    rows = result.get("rows") or []
    generated = record.get("generated") or {}
    risk = record.get("risk") or {}
    return {
        "id": record["id"],
        "question": question,
        "status": record["status"],
        "risk": risk.get("level"),
        "estimated_rows": risk.get("estimated_rows"),
        "generated_sql": generated.get("sql"),
        "normalized_sql": record.get("normalized_sql"),
        "assumptions": generated.get("assumptions", []),
        "answer": record.get("answer"),
        "columns": result.get("columns", []),
        "row_count": result.get("row_count", 0),
        "first_row": rows[0] if rows else None,
        "chart_type": (record.get("chart") or {}).get("type"),
        "timeline": [item["status"] for item in record.get("timeline", [])],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local Data Agent HTTP end-to-end questions")
    parser.add_argument("--base-url", default="http://127.0.0.1:8013")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime" / "e2e-questions.json")
    args = parser.parse_args()
    password = os.getenv("PLATFORM_ADMIN_PASSWORD", "")
    if not password:
        raise SystemExit("PLATFORM_ADMIN_PASSWORD is required")

    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        root = client.get("/")
        live = client.get("/live")
        unauthorized = httpx.get(f"{args.base_url}/api/v1/health", timeout=10)
        login = client.post(
            "/api/v1/auth/login",
            json={"username": args.username, "password": password},
        )
        login.raise_for_status()
        csrf = login.json()["csrf_token"]
        client.headers["X-CSRF-Token"] = csrf
        health = client.get("/api/v1/health")
        health.raise_for_status()
        examples = client.get("/api/v1/examples")
        examples.raise_for_status()
        metadata = client.get("/api/v1/metadata/tables")
        metadata.raise_for_status()

        records: list[dict[str, Any]] = []
        for question in QUESTIONS:
            response = client.post(
                "/api/v1/questions",
                json={"question": question, "preferred_chart": "auto"},
            )
            response.raise_for_status()
            record = response.json()
            initial_status = record["status"]
            if initial_status == "approval_required":
                approval = client.post(
                    f"/api/v1/questions/{record['id']}/approve",
                    json={"sql_hash": record["sql_hash"]},
                )
                approval.raise_for_status()
                record = approval.json()
            if record["status"] != "completed":
                raise RuntimeError(f"question failed: {question}: {record}")
            summary = _summary(record, question)
            summary["initial_status"] = initial_status
            records.append(summary)

        overview = client.get("/api/v1/overview")
        overview.raise_for_status()
        history = client.get("/api/v1/history?page=1&page_size=100")
        history.raise_for_status()

    report = {
        "base_url": args.base_url,
        "root_status": root.status_code,
        "live": live.json(),
        "unauthorized_health_status": unauthorized.status_code,
        "login_user": login.json()["user"],
        "health": health.json(),
        "examples": examples.json()["questions"],
        "metadata_tables": [table["name"] for table in metadata.json()["tables"]],
        "overview": overview.json(),
        "history_total": history.json()["total"],
        "questions": records,
    }
    assert root.status_code == 200
    assert live.json() == {"status": "ok"}
    assert unauthorized.status_code == 401
    assert report["health"]["database"]["connected"] is True
    assert report["health"]["database"]["name"] == "data_agent_local"
    assert len(records) == 10
    assert all(record["status"] == "completed" for record in records)
    assert all(record["row_count"] > 0 for record in records)
    assert any(record["initial_status"] == "approval_required" for record in records)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    compact = {
        "root_status": report["root_status"],
        "live": report["live"],
        "unauthorized_health_status": report["unauthorized_health_status"],
        "health": report["health"],
        "metadata_tables": report["metadata_tables"],
        "history_total": report["history_total"],
        "questions": [
            {
                "question": item["question"],
                "initial_status": item["initial_status"],
                "status": item["status"],
                "risk": item["risk"],
                "rows": item["row_count"],
                "first_row": item["first_row"],
            }
            for item in records
        ],
    }
    print(json.dumps(compact, ensure_ascii=True, default=str, indent=2))
    print(f"e2e_report={args.output}")


if __name__ == "__main__":
    main()
