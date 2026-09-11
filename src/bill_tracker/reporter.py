"""Report generation from config-driven sections."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from bill_tracker.models import Bill, Receipt, ReportConfig, VendorStore


def _parse_this_month() -> tuple[str, str]:
    """Return (first_day, last_day) of the current month as YYYY-MM-DD."""
    today = date.today()
    first = today.replace(day=1)
    if today.month == 12:
        last = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return first.isoformat(), last.isoformat()


def _parse_this_year() -> str:
    """Return the current year as a string."""
    return str(date.today().year)


def apply_filter(items: list, filter_str: str) -> list:
    """Filter a list of items by simple key:value pairs.

    Supports multiple filters separated by spaces.
    Special values: "this-month", "this-year".

    Args:
        items: List of Bill or Receipt objects.
        filter_str: Space-separated key:value pairs.

    Returns:
        Filtered list.
    """
    if not filter_str:
        return items

    filters = _parse_filter_string(filter_str)
    result = items

    for key, value in filters.items():
        result = _apply_single_filter(result, key, value)

    return result


def _parse_filter_string(filter_str: str) -> dict[str, str]:
    """Parse "key1:val1 key2:val2" into a dict."""
    filters: dict[str, str] = {}
    for part in filter_str.split():
        if ":" in part:
            key, _, value = part.partition(":")
            filters[key.strip()] = value.strip()
    return filters


def _apply_single_filter(items: list, key: str, value: str) -> list:
    """Apply a single filter condition."""
    result = []
    first_day, last_day = _parse_this_month()
    this_year = _parse_this_year()

    for item in items:
        item_value = getattr(item, key, None)
        if item_value is None:
            continue

        # Handle special values
        if value == "true":
            if item_value is True:
                result.append(item)
        elif value == "false":
            if item_value is False:
                result.append(item)
        elif value == "this-month":
            if isinstance(item_value, str) and first_day <= item_value <= last_day:
                result.append(item)
        elif value == "this-year":
            if isinstance(item_value, str) and item_value.startswith(this_year):
                result.append(item)
        else:
            # Case-insensitive string match
            if str(item_value).lower() == value.lower():
                result.append(item)

    return result


def apply_sort(items: list, sort_str: str) -> list:
    """Sort items by field and direction.

    Args:
        items: List of Bill or Receipt objects.
        sort_str: Sort specification like "field:asc" or "field:desc".

    Returns:
        Sorted list.
    """
    if not sort_str or ":" not in sort_str:
        return items

    field, _, direction = sort_str.partition(":")
    reverse = direction.strip().lower() == "desc"

    def _sort_key(item):
        val = getattr(item, field.strip(), None)
        if val is None:
            return ""
        return val

    return sorted(items, key=_sort_key, reverse=reverse)


def format_bill_row(bill: Bill, columns: list[str]) -> str:
    """Format a bill as a markdown table row.

    Args:
        bill: Bill to format.
        columns: List of field names to include.

    Returns:
        Markdown table row string.
    """
    cells = []
    for col in columns:
        val = getattr(bill, col, None)
        if val is None:
            cells.append("")
        elif isinstance(val, bool):
            cells.append("Yes" if val else "No")
        elif isinstance(val, float):
            cells.append(f"{val:.2f}")
        else:
            cells.append(str(val))
    return "| " + " | ".join(cells) + " |"


def format_receipt_row(receipt: Receipt, columns: list[str]) -> str:
    """Format a receipt as a markdown table row.

    Args:
        receipt: Receipt to format.
        columns: List of field names to include.

    Returns:
        Markdown table row string.
    """
    cells = []
    for col in columns:
        val = getattr(receipt, col, None)
        if val is None:
            cells.append("")
        elif isinstance(val, bool):
            cells.append("Yes" if val else "No")
        elif isinstance(val, float):
            cells.append(f"{val:.2f}")
        else:
            cells.append(str(val))
    return "| " + " | ".join(cells) + " |"


def _make_table_header(columns: list[str]) -> str:
    """Create a markdown table header."""
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join(" --- " for _ in columns) + "|"
    return header + "\n" + separator


def _compute_days_late(bill: Bill) -> int:
    """Compute days a bill is overdue."""
    if bill.paid:
        return 0
    try:
        due = datetime.strptime(bill.dueDate, "%Y-%m-%d")
        today = datetime.now()
        delta = (today - due).days
        return max(0, delta)
    except (ValueError, TypeError):
        return 0


def generate_report(
    bills: list[Bill],
    receipts: list[Receipt],
    report_config: ReportConfig,
    vendors: VendorStore,
) -> str:
    """Generate a complete report in markdown format.

    Args:
        bills: All bills.
        receipts: All receipts.
        report_config: Report configuration.
        vendors: Vendor store.

    Returns:
        Markdown report string.
    """
    today = date.today().isoformat()
    lines = [
        f"# Bill Tracker Report — {today}",
        "",
        f"**Total bills:** {len(bills)} | **Unpaid:** {sum(1 for b in bills if not b.paid)} | **Receipts:** {len(receipts)}",
        "",
    ]

    for section in report_config.sections:
        lines.append(f"## {section.title}")
        lines.append("")

        # Determine what type of items this section deals with
        # Sections starting with "receipt" or "payment" use receipts, others use bills
        is_receipt_section = any(
            keyword in section.id.lower()
            for keyword in ("receipt", "payment", "matched")

        )

        if is_receipt_section:
            items = receipts
        else:
            items = bills

        filtered = apply_filter(list(items), section.filter)
        sorted_items = apply_sort(filtered, section.sort)

        if not sorted_items:
            lines.append("*No items to display.*")
            lines.append("")
            continue

        # Add daysLate as a virtual column for bills
        render_columns = list(section.columns)
        has_days_late = "daysLate" in render_columns

        # Build table
        display_columns = [c for c in render_columns if c != "daysLate"]
        if has_days_late:
            display_columns = render_columns

        lines.append(_make_table_header(display_columns))

        for item in sorted_items:
            if is_receipt_section and hasattr(item, "paymentDate"):
                row = format_receipt_row(item, display_columns)
            elif hasattr(item, "dueDate"):
                # Handle daysLate virtual column
                if has_days_late and "daysLate" in render_columns:
                    cells = []
                    for col in render_columns:
                        if col == "daysLate":
                            cells.append(str(_compute_days_late(item)))
                        else:
                            val = getattr(item, col, None)
                            if val is None:
                                cells.append("")
                            elif isinstance(val, bool):
                                cells.append("Yes" if val else "No")
                            elif isinstance(val, float):
                                cells.append(f"{val:.2f}")
                            else:
                                cells.append(str(val))
                    row = "| " + " | ".join(cells) + " |"
                else:
                    row = format_bill_row(item, display_columns)
            else:
                row = format_bill_row(item, display_columns)
            lines.append(row)

        # Total row
        total = sum((i.amount or 0) for i in sorted_items)
        if "amount" in display_columns:
            total_cells = []
            for col in display_columns:
                if col == "amount":
                    total_cells.append(f"**{total:.2f}**")
                elif col == "vendor":
                    total_cells.append("**TOTAL**")
                else:
                    total_cells.append("")
            lines.append("| " + " | ".join(total_cells) + " |")

        lines.append("")

    # Vendor summary
    if vendors.known:
        lines.append("## Known Vendors")
        lines.append("")
        for v in vendors.known:
            lines.append(f"- **{v.name}** ({v.category}) — {v.currency}")
        lines.append("")

    if vendors.discovered:
        lines.append("## Discovered Vendors (Needs Review)")
        lines.append("")
        for d in vendors.discovered:
            name = d.get("name", "Unknown")
            occurrences = d.get("occurrences", 1)
            lines.append(f"- **{name}** — seen {occurrences} time(s)")
        lines.append("")

    return "\n".join(lines)