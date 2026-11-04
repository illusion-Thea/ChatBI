"""Create polished, business-readable Excel exports for query results."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from numbers import Number
from typing import Any

import xlsxwriter

from backend.app.schemas import QuestionRecord


@dataclass(frozen=True)
class FieldMeaning:
    label: str
    description: str
    value_format: str = "常规"
    excel_format: str | None = None
    width: int = 18


FIELD_MEANINGS: dict[str, FieldMeaning] = {
    "month": FieldMeaning("月份", "查询统计月份，格式为 YYYY-MM。", "年月", "@", 14),
    "date": FieldMeaning("日期", "查询统计日期。", "日期", "yyyy-mm-dd", 14),
    "year": FieldMeaning("年份", "查询统计年份。", "年份", "0", 12),
    "region": FieldMeaning("区域", "客户所属经营区域。", "文本", None, 18),
    "category": FieldMeaning("商品品类", "商品所属品类名称。", "文本", None, 20),
    "product": FieldMeaning("商品名称", "参与统计的商品名称。", "文本", None, 28),
    "channel": FieldMeaning("下单渠道", "客户创建订单时使用的渠道。", "文本", None, 16),
    "segment": FieldMeaning("客户分层", "客户的业务分层或类型。", "文本", None, 16),
    "paid_gmv": FieldMeaning(
        "已支付销售额（元）", "已支付订单的实付金额合计。", "人民币金额", "#,##0.00", 22
    ),
    "revenue": FieldMeaning(
        "成交收入（元）", "已支付订单明细的折后成交收入。", "人民币金额", "#,##0.00", 20
    ),
    "cost": FieldMeaning(
        "商品成本（元）", "成交商品按标准成本计算的成本合计。", "人民币金额", "#,##0.00", 20
    ),
    "gross_profit": FieldMeaning(
        "销售毛利（元）",
        "成交收入减商品标准成本，不含物流和营销费用。",
        "人民币金额",
        "#,##0.00",
        20,
    ),
    "avg_order_value": FieldMeaning(
        "平均客单价（元）", "已支付订单金额的平均值。", "人民币金额", "#,##0.00", 20
    ),
    "refund_rate_pct": FieldMeaning(
        "退款订单率（%）", "退款订单数占统计范围内全部订单数的百分比。", "百分比数值", '0.00"%"', 20
    ),
    "order_count": FieldMeaning("订单数（笔）", "去重后的订单数量。", "整数", "#,##0", 16),
    "paid_order_count": FieldMeaning(
        "已支付订单数（笔）", "状态为 PAID 的订单数量。", "整数", "#,##0", 20
    ),
    "units_sold": FieldMeaning("销售数量（件）", "成交商品件数合计。", "整数", "#,##0", 18),
    "customers": FieldMeaning(
        "成交客户数（位）", "产生已支付订单的去重客户数。", "整数", "#,##0", 20
    ),
    "new_customers": FieldMeaning(
        "新增客户数（位）", "统计期间新注册的客户数量。", "整数", "#,##0", 20
    ),
}


def field_meaning(column: str, sample: Any = None) -> FieldMeaning:
    """Return a Chinese business label and a conservative fallback for unknown aliases."""
    normalized = column.strip().lower()
    if normalized in FIELD_MEANINGS:
        return FIELD_MEANINGS[normalized]
    label = re.sub(r"[_\-]+", " ", column).strip() or "未命名字段"
    value_format = "数值" if isinstance(sample, Number) and not isinstance(sample, bool) else "文本"
    excel_format = "#,##0.00" if value_format == "数值" else None
    return FieldMeaning(label, f"查询结果字段 {column}。", value_format, excel_format, 20)


def _safe_sheet_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Number):
        return value
    if isinstance(value, (date, datetime)):
        return value
    return str(value)


def build_query_workbook(record: QuestionRecord, exported_by: str) -> bytes:
    """Build a two-sheet XLSX report without exposing SQL or private credentials."""
    if not record.result:
        raise ValueError("当前查询没有可导出的结果")

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(
        output,
        {
            "in_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
            "constant_memory": False,
        },
    )
    workbook.set_properties(
        {
            "title": f"QueryX 查询结果 - {record.question}",
            "subject": "零售经营智能问数查询结果",
            "author": "QueryX",
            "company": "QueryX",
            "comments": "由 QueryX 安全查询平台生成",
        }
    )

    brand = "#4F46E5"
    blue = "#3B82F6"
    dark = "#0F172A"
    muted = "#64748B"
    font_name = "Microsoft YaHei"

    title_fmt = workbook.add_format(
        {"font_name": font_name, "font_size": 16, "bold": True, "font_color": dark}
    )
    meta_label_fmt = workbook.add_format(
        {"font_name": font_name, "font_size": 10, "bold": True, "font_color": muted}
    )
    meta_value_fmt = workbook.add_format(
        {
            "font_name": font_name,
            "font_size": 10,
            "font_color": dark,
            "text_wrap": True,
            "valign": "top",
        }
    )
    header_fmt = workbook.add_format(
        {
            "font_name": font_name,
            "font_size": 10,
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": brand,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#FFFFFF",
        }
    )
    text_fmt = workbook.add_format(
        {"font_name": font_name, "font_size": 10, "font_color": dark, "valign": "vcenter"}
    )
    alt_text_fmt = workbook.add_format(
        {
            "font_name": font_name,
            "font_size": 10,
            "font_color": dark,
            "bg_color": "#F8FAFC",
            "valign": "vcenter",
        }
    )
    note_fmt = workbook.add_format(
        {"font_name": font_name, "font_size": 9, "font_color": muted, "italic": True}
    )

    columns = record.result.columns
    samples = {
        column: next(
            (row.get(column) for row in record.result.rows if row.get(column) is not None), None
        )
        for column in columns
    }
    meanings = {column: field_meaning(column, samples[column]) for column in columns}
    last_col = max(len(columns) - 1, 3)

    sheet = workbook.add_worksheet("查询结果")
    sheet.hide_gridlines(2)
    sheet.set_tab_color(brand)
    sheet.set_zoom(95)
    sheet.set_row(0, 10)
    sheet.merge_range(1, 0, 1, last_col, "QueryX 查询结果", title_fmt)
    sheet.set_row(1, 26)
    sheet.write(2, 0, "业务问题", meta_label_fmt)
    sheet.merge_range(2, 1, 2, last_col, record.question, meta_value_fmt)
    sheet.set_row(2, 24)
    sheet.write(3, 0, "结果说明", meta_label_fmt)
    sheet.merge_range(3, 1, 3, last_col, record.answer or "查询已完成。", meta_value_fmt)
    sheet.set_row(3, 42)
    assumptions = (
        "；".join(record.generated.assumptions)
        if record.generated
        else "以查询结果记录的业务口径为准"
    )
    sheet.write(4, 0, "统计口径", meta_label_fmt)
    sheet.merge_range(4, 1, 4, last_col, assumptions, meta_value_fmt)
    sheet.set_row(4, 36)
    sheet.write(5, 0, "导出时间", meta_label_fmt)
    sheet.merge_range(
        5,
        1,
        5,
        last_col,
        datetime.now(timezone(timedelta(hours=8), name="CST")).strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        ),
        meta_value_fmt,
    )
    sheet.set_row(5, 24)
    sheet.write(6, 0, "导出账号", meta_label_fmt)
    sheet.merge_range(6, 1, 6, last_col, exported_by, meta_value_fmt)
    sheet.set_row(6, 24)
    sheet.write(7, 0, "数据范围", meta_label_fmt)
    range_note = f"共 {record.result.row_count:,} 行"
    if record.result.truncated:
        range_note += "；结果达到系统返回上限，导出内容为当前截断结果"
    sheet.merge_range(7, 1, 7, last_col, range_note, meta_value_fmt)
    sheet.set_row(7, 24)

    header_row = 9
    for col_index, column in enumerate(columns):
        meaning = meanings[column]
        sheet.write(header_row, col_index, meaning.label, header_fmt)
        sheet.set_column(col_index, col_index, min(max(meaning.width, 12), 36))
    for col_index in range(len(columns), last_col + 1):
        sheet.set_column(col_index, col_index, 3)
    sheet.set_row(header_row, 28)

    format_cache: dict[tuple[str | None, bool], Any] = {}
    for row_index, row in enumerate(record.result.rows, start=header_row + 1):
        alternate = (row_index - header_row) % 2 == 0
        for col_index, column in enumerate(columns):
            value = _safe_sheet_value(row.get(column))
            meaning = meanings[column]
            if isinstance(value, str):
                sheet.write_string(
                    row_index, col_index, value, alt_text_fmt if alternate else text_fmt
                )
                continue
            cache_key = (meaning.excel_format, alternate)
            cell_fmt = format_cache.get(cache_key)
            if cell_fmt is None:
                cell_fmt = workbook.add_format(
                    {
                        "font_name": font_name,
                        "font_size": 10,
                        "font_color": dark,
                        "bg_color": "#F8FAFC" if alternate else "#FFFFFF",
                        "valign": "vcenter",
                        "align": "right",
                        "num_format": meaning.excel_format or "General",
                    }
                )
                format_cache[cache_key] = cell_fmt
            sheet.write(row_index, col_index, value, cell_fmt)
        sheet.set_row(row_index, 22)

    if columns:
        last_data_row = max(header_row + len(record.result.rows), header_row + 1)
        sheet.autofilter(header_row, 0, last_data_row, len(columns) - 1)
        sheet.freeze_panes(header_row + 1, 0)
    sheet.write(
        header_row + len(record.result.rows) + 2, 0, "字段定义详见“字段说明”工作表。", note_fmt
    )
    sheet.set_landscape()
    sheet.fit_to_pages(1, 0)
    sheet.set_margins(0.4, 0.4, 0.55, 0.55)
    sheet.set_header("&LQueryX&C查询结果&R&P / &N")
    sheet.set_footer("&L仅供内部经营分析使用&R导出编号：" + record.id)

    dictionary = workbook.add_worksheet("字段说明")
    dictionary.hide_gridlines(2)
    dictionary.set_tab_color(blue)
    dictionary.set_zoom(100)
    dictionary.set_row(0, 10)
    dictionary.merge_range("A2:D2", "字段说明", title_fmt)
    dictionary.write_row("A4", ["中文名称", "技术字段名", "业务含义", "数据格式"], header_fmt)
    for row_index, column in enumerate(columns, start=4):
        meaning = meanings[column]
        row_fmt = alt_text_fmt if row_index % 2 else text_fmt
        dictionary.write_string(row_index, 0, meaning.label, row_fmt)
        dictionary.write_string(row_index, 1, column, row_fmt)
        dictionary.write_string(row_index, 2, meaning.description, row_fmt)
        dictionary.write_string(row_index, 3, meaning.value_format, row_fmt)
        dictionary.set_row(row_index, 30)
    dictionary.set_column("A:A", 24)
    dictionary.set_column("B:B", 24)
    dictionary.set_column("C:C", 54)
    dictionary.set_column("D:D", 18)
    dictionary.freeze_panes(4, 0)
    if columns:
        dictionary.autofilter(3, 0, 3 + len(columns), 3)
    dictionary.write(5 + len(columns), 0, "说明", meta_label_fmt)
    dictionary.merge_range(
        5 + len(columns),
        1,
        5 + len(columns),
        3,
        "中文名称用于业务阅读，技术字段名用于接口对接与数据追溯。",
        meta_value_fmt,
    )

    workbook.close()
    return output.getvalue()
