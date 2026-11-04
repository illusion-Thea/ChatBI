"""Generate a QueryX BI-style Excel report with a native line chart.

The public helpers support both common server-side export patterns:

* ``build_queryx_bi_report()`` returns XLSX bytes for an HTTP response.
* ``write_queryx_bi_report()`` writes the same workbook to a local file.

Requires: XlsxWriter >= 3.1
"""

from __future__ import annotations

import io
import math
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

import xlsxwriter


TECH_BLUE = "#1890FF"
DEEP_BLUE = "#17365D"
ANOMALY_RED = "#FF4D4F"
TEXT_DARK = "#262626"
TEXT_MUTED = "#595959"
LIGHT_GRAY = "#D9D9D9"
ROW_ALT = "#F7F9FC"
FONT_NAME = "Microsoft YaHei"

EXPECTED_MONTHS = tuple(f"2026-{month:02d}" for month in range(1, 11))


def _normalize_data(data: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate and sort the ten monthly points used by A9:B18."""
    if len(data) != 10:
        raise ValueError("图表固定引用 A9:A18/B9:B18，因此 data 必须恰好包含 10 条记录")

    normalized: list[dict[str, Any]] = []
    seen_months: set[str] = set()

    for index, item in enumerate(data, start=1):
        if "month" not in item or "amount" not in item:
            raise ValueError(f"第 {index} 条记录必须同时包含 month 和 amount")

        month = str(item["month"]).strip()
        if month in seen_months:
            raise ValueError(f"月份重复：{month}")

        raw_amount = item["amount"]
        if isinstance(raw_amount, bool):
            raise ValueError(f"{month} 的 amount 不能是布尔值")

        try:
            amount = float(raw_amount if not isinstance(raw_amount, Decimal) else raw_amount)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{month} 的 amount 不是有效数字：{raw_amount!r}") from exc

        if not math.isfinite(amount):
            raise ValueError(f"{month} 的 amount 必须是有限数字")

        seen_months.add(month)
        normalized.append({"month": month, "amount": amount})

    normalized.sort(key=lambda item: item["month"])
    actual_months = tuple(item["month"] for item in normalized)
    if actual_months != EXPECTED_MONTHS:
        raise ValueError(
            "为保证 A9:A18 与 2026 年 1-10 月一一对应，month 必须为 "
            + ", ".join(EXPECTED_MONTHS)
        )

    return normalized


def _add_formats(workbook: xlsxwriter.Workbook) -> dict[str, Any]:
    """Create formats once so merged cells cannot be overwritten accidentally."""
    horizontal_border = {"bottom": 1, "bottom_color": LIGHT_GRAY}
    card_fill = "#F7F9FC"

    return {
        "base": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "font_color": TEXT_DARK,
                "text_wrap": True,
                "valign": "vcenter",
            }
        ),
        "card_label_top": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "bold": True,
                "font_color": "#666666",
                "bg_color": card_fill,
                "align": "left",
                "valign": "vcenter",
                "text_wrap": True,
                "top": 1,
                "left": 1,
                "top_color": LIGHT_GRAY,
                "left_color": LIGHT_GRAY,
            }
        ),
        "card_label_middle": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "bold": True,
                "font_color": "#666666",
                "bg_color": card_fill,
                "align": "left",
                "valign": "vcenter",
                "text_wrap": True,
                "left": 1,
                "left_color": LIGHT_GRAY,
            }
        ),
        "card_value_top": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "font_color": "#000000",
                "bg_color": card_fill,
                "align": "left",
                "valign": "vcenter",
                "text_wrap": True,
                "top": 1,
                "right": 1,
                "top_color": LIGHT_GRAY,
                "right_color": LIGHT_GRAY,
            }
        ),
        "card_value_middle": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "font_color": "#000000",
                "bg_color": card_fill,
                "align": "left",
                "valign": "vcenter",
                "text_wrap": True,
                "right": 1,
                "right_color": LIGHT_GRAY,
            }
        ),
        "card_blank_left": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "bg_color": card_fill,
                "text_wrap": True,
                "valign": "vcenter",
                "left": 1,
                "bottom": 1,
                "left_color": LIGHT_GRAY,
                "bottom_color": LIGHT_GRAY,
            }
        ),
        "card_blank_right": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "bg_color": card_fill,
                "text_wrap": True,
                "valign": "vcenter",
                "right": 1,
                "bottom": 1,
                "right_color": LIGHT_GRAY,
                "bottom_color": LIGHT_GRAY,
            }
        ),
        "header": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": TECH_BLUE,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
                **horizontal_border,
            }
        ),
        "month_white": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "font_color": TEXT_DARK,
                "align": "left",
                "valign": "vcenter",
                "text_wrap": True,
                **horizontal_border,
            }
        ),
        "month_alt": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "font_color": TEXT_DARK,
                "bg_color": ROW_ALT,
                "align": "left",
                "valign": "vcenter",
                "text_wrap": True,
                **horizontal_border,
            }
        ),
        "amount_white": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "font_color": TEXT_DARK,
                "align": "right",
                "valign": "vcenter",
                "text_wrap": True,
                "num_format": "#,##0.00",
                **horizontal_border,
            }
        ),
        "amount_alt": workbook.add_format(
            {
                "font_name": FONT_NAME,
                "font_size": 10,
                "font_color": TEXT_DARK,
                "bg_color": ROW_ALT,
                "align": "right",
                "valign": "vcenter",
                "text_wrap": True,
                "num_format": "#,##0.00",
                **horizontal_border,
            }
        ),
    }


def _add_native_line_chart(
    workbook: xlsxwriter.Workbook,
    worksheet: xlsxwriter.worksheet.Worksheet,
    data: Sequence[Mapping[str, Any]],
) -> None:
    """Insert an editable Excel line chart bound exactly to A11:B20."""
    august_index = next(
        index for index, item in enumerate(data) if item["month"] == "2026-08"
    )

    # None keeps the default blue marker. Only the eighth point gets an override.
    point_formats: list[dict[str, Any] | None] = [None] * len(data)
    point_formats[august_index] = {
        "fill": {"color": ANOMALY_RED},
        "border": {"color": ANOMALY_RED, "width": 1.5},
    }

    # The point itself is red; its label is also red to make the anomaly unambiguous.
    custom_labels: list[dict[str, Any] | None] = [None] * len(data)
    custom_labels[august_index] = {
        "font": {
            "name": FONT_NAME,
            "size": 9,
            "bold": True,
            "color": ANOMALY_RED,
        },
        "position": "above",
    }

    chart = workbook.add_chart({"type": "line"})
    chart.add_series(
        {
            "name": "已支付销售额（元）",
            # List syntax avoids worksheet-name quoting mistakes and still exports
            # to the exact Excel formulas: $A$11:$A$20 and $B$11:$B$20.
            "categories": [worksheet.name, 10, 0, 19, 0],
            "values": [worksheet.name, 10, 1, 19, 1],
            "line": {"color": TECH_BLUE, "width": 2.5},
            "marker": {
                "type": "circle",
                "size": 7,
                "border": {"color": TECH_BLUE, "width": 1.25},
                "fill": {"color": "#FFFFFF"},
            },
            "points": point_formats,
            "smooth": True,
            "data_labels": {
                "value": True,
                "position": "above",
                "num_format": "#,##0.00",
                "font": {"name": FONT_NAME, "size": 8, "color": TEXT_MUTED},
                "custom": custom_labels,
            },
        }
    )

    chart.set_title(
        {
            "name": "2026年已支付销售额走势",
            "name_font": {
                "name": FONT_NAME,
                "size": 14,
                "bold": True,
                "color": DEEP_BLUE,
            },
        }
    )
    chart.set_legend({"none": True})
    chart.set_x_axis(
        {
            "name": "月份",
            "name_font": {"name": FONT_NAME, "size": 9, "color": TEXT_MUTED},
            "num_font": {"name": FONT_NAME, "size": 8, "color": TEXT_MUTED},
            "line": {"color": LIGHT_GRAY},
            "major_tick_mark": "none",
            "major_gridlines": {"visible": False},
        }
    )
    chart.set_y_axis(
        {
            "name": "销售额（元）",
            "name_font": {"name": FONT_NAME, "size": 9, "color": TEXT_MUTED},
            "num_font": {"name": FONT_NAME, "size": 8, "color": TEXT_MUTED},
            "num_format": "#,##0.00",
            "min": 0,
            "line": {"color": LIGHT_GRAY},
            "major_tick_mark": "none",
            "major_gridlines": {"visible": False},
        }
    )
    chart.set_chartarea(
        {"fill": {"color": "#FFFFFF"}, "border": {"none": True}}
    )
    chart.set_plotarea(
        {"fill": {"color": "#FFFFFF"}, "border": {"none": True}}
    )
    chart.set_size({"width": 650, "height": 390})

    # D9 keeps the A:B detail table readable while the chart spans rows 9-25.
    worksheet.insert_chart("D9", chart, {"x_offset": 4, "y_offset": 2})


def build_queryx_bi_report(
    data: Sequence[Mapping[str, Any]],
    *,
    export_time: str = "2026-11-04 19:37:23 CST",
    export_account: str = "admin",
) -> bytes:
    """Return a complete QueryX BI report as XLSX bytes for a web response."""
    normalized_data = _normalize_data(data)

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(
        output,
        {
            "in_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        },
    )
    workbook.set_properties(
        {
            "title": "2026年已支付销售额报表",
            "subject": "2026年已支付销售额走势",
            "author": "QueryX",
            "company": "QueryX",
        }
    )

    try:
        formats = _add_formats(workbook)
        worksheet = workbook.add_worksheet("BI报表")
        worksheet.hide_gridlines(2)
        worksheet.set_tab_color(TECH_BLUE)
        worksheet.set_zoom(90)

        # A is the 15-character label column. B:D total roughly 60 characters.
        # The base column format provides wrap + vertical centering globally;
        # explicit cell formats below preserve those properties.
        worksheet.set_column("A:A", 15, formats["base"])
        worksheet.set_column("B:D", 20, formats["base"])
        worksheet.set_column("E:H", 18, formats["base"])

        worksheet.set_row(0, 9)  # Keep row 1 as a small top margin.
        for row in range(1, 8):
            # xlsxwriter rows are zero-based: 1..7 correspond to Excel rows 2..8.
            worksheet.set_row(row, 25)

        metadata = (
            ("业务问题", "今年每个月的已支付销售额是多少？"),
            ("结果说明", "已获得 10 个时间点。按月汇总本年度已支付订单金额。"),
            ("统计口径", "销售额采用已支付订单的订单实付金额。"),
            ("导出时间", export_time),
            ("导出账号", export_account),
            ("数据范围", "共 10 行"),
        )
        for excel_row, (label, value) in enumerate(metadata, start=2):
            zero_based_row = excel_row - 1
            position = "top" if excel_row == 2 else "middle"
            worksheet.write(
                zero_based_row,
                0,
                label,
                formats[f"card_label_{position}"],
            )
            # Apply the final merged-cell style exactly once. Never write to
            # B:D again after merge_range(), which prevents style overwrites.
            worksheet.merge_range(
                zero_based_row,
                1,
                zero_based_row,
                3,
                value,
                formats[f"card_value_{position}"],
            )

        # Row 8 remains empty but retains the card fill and outer bottom border.
        worksheet.write_blank("A8", None, formats["card_blank_left"])
        worksheet.merge_range("B8:D8", "", formats["card_blank_right"])

        # Row 9 is the requested gap/chart start. Row 10 is the data header.
        worksheet.set_row(8, 9)
        worksheet.set_row(9, 26)
        worksheet.write("A10", "月份", formats["header"])
        worksheet.write("B10", "已支付销售额（元）", formats["header"])

        for offset, item in enumerate(normalized_data):
            zero_based_row = 10 + offset
            alternate = offset % 2 == 1
            worksheet.set_row(zero_based_row, 23)
            worksheet.write_string(
                zero_based_row,
                0,
                item["month"],
                formats["month_alt" if alternate else "month_white"],
            )
            # write_number guarantees that B9:B18 are numbers, not formatted strings.
            worksheet.write_number(
                zero_based_row,
                1,
                item["amount"],
                formats["amount_alt" if alternate else "amount_white"],
            )

        _add_native_line_chart(workbook, worksheet, normalized_data)

        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 1)
        worksheet.set_margins(0.35, 0.35, 0.45, 0.45)
        worksheet.print_area("A1:H25")
    finally:
        workbook.close()

    return output.getvalue()


def write_queryx_bi_report(
    data: Sequence[Mapping[str, Any]],
    output_path: str | Path,
    *,
    export_time: str = "2026-11-04 19:37:23 CST",
    export_account: str = "admin",
) -> Path:
    """Write the report to disk and return the resolved output path."""
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        build_queryx_bi_report(
            data,
            export_time=export_time,
            export_account=export_account,
        )
    )
    return path


if __name__ == "__main__":
    # Replace this list with the result returned by your query service.
    sample_data = [
        {"month": "2026-01", "amount": 45860.35},
        {"month": "2026-02", "amount": 48210.80},
        {"month": "2026-03", "amount": 50128.40},
        {"month": "2026-04", "amount": 52690.10},
        {"month": "2026-05", "amount": 54820.65},
        {"month": "2026-06", "amount": 56320.90},
        {"month": "2026-07", "amount": 57980.30},
        {"month": "2026-08", "amount": 9880.20},
        {"month": "2026-09", "amount": 51260.75},
        {"month": "2026-10", "amount": 53840.50},
    ]

    generated = write_queryx_bi_report(
        sample_data,
        Path(__file__).resolve().parents[1] / "outputs" / "queryx_bi_report.xlsx",
    )
    print(f"Excel 报表已生成：{generated}")
