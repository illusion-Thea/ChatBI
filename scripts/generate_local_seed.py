"""Generate deterministic MySQL seed data for the local Data Agent database."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "database" / "seed.sql"
DEFAULT_MANIFEST = ROOT / "database" / "seed.manifest.json"
SEED = 20261104
TABLES = ("regions", "categories", "products", "customers", "orders", "order_items")

REGION_NAMES = [
    "北京城区",
    "天津城区",
    "石家庄",
    "唐山",
    "太原",
    "呼和浩特",
    "沈阳",
    "大连",
    "长春",
    "哈尔滨",
    "上海城区",
    "南京",
    "苏州",
    "无锡",
    "杭州",
    "宁波",
    "温州",
    "合肥",
    "福州",
    "厦门",
    "南昌",
    "济南",
    "青岛",
    "郑州",
    "武汉",
    "长沙",
    "广州",
    "深圳",
    "佛山",
    "东莞",
    "南宁",
    "海口",
    "重庆城区",
    "成都",
    "绵阳",
    "贵阳",
    "昆明",
    "拉萨",
    "西安",
    "兰州",
    "西宁",
    "银川",
    "乌鲁木齐",
    "珠海",
    "中山",
    "泉州",
    "烟台",
    "洛阳",
    "宜昌",
    "嘉兴",
]

CATEGORY_NAMES = [
    "笔记本电脑",
    "台式电脑",
    "显示器",
    "键盘鼠标",
    "存储设备",
    "网络设备",
    "耳机音箱",
    "摄影设备",
    "智能穿戴",
    "手机配件",
    "办公桌椅",
    "办公照明",
    "文件收纳",
    "书写用品",
    "打印耗材",
    "会议设备",
    "清洁用品",
    "饮水器具",
    "差旅用品",
    "劳保用品",
    "咖啡茶饮",
    "休闲零食",
    "谷物早餐",
    "方便食品",
    "健康饮品",
    "烘焙食品",
    "坚果果干",
    "乳制品",
    "调味食品",
    "节日礼盒",
    "瑜伽用品",
    "跑步装备",
    "骑行装备",
    "露营用品",
    "健身器械",
    "球类用品",
    "游泳用品",
    "户外服饰",
    "旅行箱包",
    "运动护具",
    "智能家居",
    "厨房电器",
    "生活电器",
    "床品家纺",
    "卫浴用品",
    "家居装饰",
    "宠物用品",
    "母婴用品",
    "园艺用品",
    "汽车用品",
]

PRODUCT_SUFFIXES = ("基础款", "专业款", "旗舰款")
SEGMENTS = ("个人", "小微企业", "中型企业", "大型企业")
CHANNELS = ("官网", "小程序", "线下门店", "企业采购")


def _months(
    start_year: int, start_month: int, end_year: int, end_month: int
) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        result.append((year, month))
        month += 1
        if month == 13:
            year += 1
            month = 1
    return result


def build_data() -> dict[str, list[tuple[Any, ...]]]:
    rng = random.Random(SEED)
    regions = [(index, name) for index, name in enumerate(REGION_NAMES, 1)]
    categories = [(index, name) for index, name in enumerate(CATEGORY_NAMES, 1)]

    products: list[tuple[Any, ...]] = []
    for category_id, category_name in categories:
        category_band = (category_id - 1) % 10
        base_price = Decimal(str(29 + category_band * 37 + (category_id // 10) * 18))
        if category_id <= 10:
            base_price *= Decimal("3.8")
        for variant, suffix in enumerate(PRODUCT_SUFFIXES, 1):
            product_id = len(products) + 1
            price = (base_price * Decimal(str(0.85 + variant * 0.42))).quantize(Decimal("0.01"))
            margin = Decimal(str(rng.uniform(0.24, 0.43)))
            cost = (price * (Decimal("1") - margin)).quantize(Decimal("0.01"))
            products.append((product_id, f"{category_name}{suffix}", category_id, price, cost, 1))

    customers: list[tuple[Any, ...]] = []
    for customer_id in range(1, 251):
        registered = date(2024, 1, 1) + timedelta(days=rng.randint(0, 820))
        region_id = rng.choices(range(1, 51), weights=[51 - index for index in range(50)], k=1)[0]
        segment = rng.choices(SEGMENTS, weights=(72, 19, 7, 2), k=1)[0]
        customers.append(
            (customer_id, f"演示客户{customer_id:04d}", region_id, segment, registered)
        )

    month_slots: list[tuple[int, int]] = []
    for year, month in _months(2025, 1, 2026, 10):
        month_slots.extend([(year, month)] * 16)
    month_slots.extend(
        [(2025, 6), (2025, 11), (2025, 12), (2025, 12), (2026, 6), (2026, 7), (2026, 9), (2026, 10)]
    )
    rng.shuffle(month_slots)

    drafts: list[tuple[Any, ...]] = []
    for slot_index, (year, month) in enumerate(month_slots):
        day = rng.randint(1, min(monthrange(year, month)[1], 28))
        created_at = datetime.combine(
            date(year, month, day),
            time(rng.randint(8, 22), rng.randint(0, 59), rng.randint(0, 59)),
        )
        eligible = [row for row in customers if row[4] <= created_at.date()]
        customer = rng.choice(eligible)
        status = rng.choices(("PAID", "REFUNDED", "CANCELLED", "PENDING"), (82, 6, 9, 3), k=1)[0]
        if (year, month) < (2026, 10) and status == "PENDING":
            status = "PAID"
        item_count = 2 if slot_index < 140 else 1
        product_ids = rng.sample(range(1, 151), item_count)
        lines: list[tuple[int, int, Decimal, Decimal]] = []
        amount = Decimal("0")
        for product_id in sorted(product_ids):
            product = products[product_id - 1]
            quantity = rng.choices((1, 2, 3, 4), (76, 16, 6, 2), k=1)[0]
            discount = rng.choices(
                (Decimal("0"), Decimal("0.0500"), Decimal("0.1000"), Decimal("0.1500")),
                (66, 19, 11, 4),
                k=1,
            )[0]
            unit_price = Decimal(product[3])
            line_total = (unit_price * quantity * (Decimal("1") - discount)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            amount += line_total
            lines.append((product_id, quantity, unit_price, discount))
        paid_at = (
            created_at + timedelta(minutes=rng.randint(1, 180))
            if status in {"PAID", "REFUNDED"}
            else None
        )
        channel = rng.choices(CHANNELS, weights=(24, 39, 29, 8), k=1)[0]
        drafts.append((created_at, customer[0], status, paid_at, amount, channel, lines))

    orders: list[tuple[Any, ...]] = []
    order_items: list[tuple[Any, ...]] = []
    for order_id, draft in enumerate(sorted(drafts, key=lambda row: row[0]), 1):
        created_at, customer_id, status, paid_at, amount, channel, lines = draft
        order_no = f"LOCAL{created_at:%Y%m%d}{order_id:06d}"
        orders.append(
            (order_id, order_no, customer_id, status, created_at, paid_at, amount, channel)
        )
        for product_id, quantity, unit_price, discount in lines:
            order_items.append(
                (len(order_items) + 1, order_id, product_id, quantity, unit_price, discount)
            )

    data = dict(
        zip(
            TABLES,
            (regions, categories, products, customers, orders, order_items),
            strict=True,
        )
    )
    expected = {
        "regions": 50,
        "categories": 50,
        "products": 150,
        "customers": 250,
        "orders": 360,
        "order_items": 500,
    }
    assert {table: len(rows) for table, rows in data.items()} == expected
    return data


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, datetime):
        return f"'{value:%Y-%m-%d %H:%M:%S}'"
    if isinstance(value, date):
        return f"'{value:%Y-%m-%d}'"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def render_seed(data: dict[str, list[tuple[Any, ...]]]) -> str:
    parts = [
        "-- Deterministic local Data Agent seed; MySQL 8.0+.",
        f"-- Seed: {SEED}. Generated by scripts/generate_local_seed.py.",
        "SET NAMES utf8mb4;",
        "START TRANSACTION;",
    ]
    for table in TABLES:
        values = ",\n".join(
            "(" + ",".join(_literal(value) for value in row) + ")" for row in data[table]
        )
        parts.append(f"INSERT INTO `{table}` VALUES\n{values};")
    parts.append("COMMIT;")
    return "\n\n".join(parts) + "\n"


def manifest(data: dict[str, list[tuple[Any, ...]]], payload: bytes) -> dict[str, Any]:
    paid_orders = [row for row in data["orders"] if row[3] == "PAID"]
    return {
        "seed": SEED,
        "counts": {table: len(rows) for table, rows in data.items()},
        "date_range": {
            "first_order": min(row[4] for row in data["orders"]).isoformat(),
            "last_order": max(row[4] for row in data["orders"]).isoformat(),
        },
        "paid_orders": len(paid_orders),
        "paid_revenue": str(sum((row[6] for row in paid_orders), Decimal("0"))),
        "seed_sql_bytes": len(payload),
        "seed_sql_sha256": hashlib.sha256(payload).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic local MySQL seed SQL")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    data = build_data()
    payload = render_seed(data).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    report = manifest(data, payload)
    args.manifest.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
