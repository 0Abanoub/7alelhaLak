"""Strict sales validation with safe diagnostics and legacy DataFrame APIs."""
import csv
from datetime import date, datetime
import io
import math
from pathlib import Path
import re

import numpy as np
from openpyxl import load_workbook
import pandas as pd

MAX_BYTES = 10 * 1024 * 1024
REQUIRED = {"date", "product", "quantity", "unit_price"}
ALIASES = {
    "sale_date": "date", "sales_date": "date", "product_name": "product",
    "qty": "quantity", "units_sold": "quantity",
    "price": "unit_price", "selling_price": "unit_price",
    "cost_price": "unit_cost",
}
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
DATE_FORMATS = (
    (r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "%Y-%m-%d"),
    (r"[0-9]{4}/[0-9]{2}/[0-9]{2}", "%Y/%m/%d"),
    (r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}", "%Y-%m-%d %H:%M"),
    (r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", "%Y-%m-%d %H:%M:%S"),
)


class SalesValidationError(ValueError):
    """A safe message and report; never contains a partially valid DataFrame."""

    def __init__(self, report: dict):
        self.report = report
        first = report["issues"][0]
        location = f"Row {first['source_row']}: " if first["source_row"] is not None else ""
        super().__init__(f"{location}{first['actionable_fix']} ({len(report['issues'])} issue(s).)")


def _report(kind: str, rows: int = 0) -> dict:
    return {
        "status": "invalid", "source_kind": kind, "input_row_count": rows,
        "output_row_count": 0, "output_source_rows": [],
        "column_normalizations": [], "aliases_mapped": [],
        "changes": {"products_trimmed": 0, "dates_parsed": 0,
                    "date_whitespace_trimmed": 0, "times_removed": 0,
                    "numeric_strings_converted": 0},
        "issues": [], "duplicate_groups": [], "warnings": [],
    }


def _issue(report: dict, row, field: str, kind: str, fix: str) -> None:
    report["issues"].append({
        "source_row": row, "canonical_field": field,
        "issue_type": kind, "actionable_fix": fix,
    })


def _stop(report: dict) -> None:
    if report["issues"]:
        raise SalesValidationError(report)


def _missing(value) -> bool:
    if value is None or (isinstance(value, str) and not value.strip()):
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _headers(headers: list, report: dict) -> list[str]:
    """Check originals, normalized names, and aliases before Pandas sees them."""
    original_seen, normalized_seen, canonical_seen = {}, {}, {}
    result = []
    for position, header in enumerate(headers, start=1):
        original = str(header) if not _missing(header) else ""
        normalized = re.sub(r"\s+", "_", original.strip().lower())
        canonical = ALIASES.get(normalized, normalized)
        result.append(canonical)
        if not original.strip():
            _issue(report, 1, "header", "empty_header",
                   f"Name column {position}; every retained column needs a header.")
            continue
        collision = None
        for stage, key, seen in (
            ("original", original, original_seen),
            ("normalized", normalized, normalized_seen),
            ("alias", canonical, canonical_seen),
        ):
            if key in seen:
                earlier, earlier_position = seen[key]
                collision = (
                    stage,
                    f"Columns {earlier_position} ({earlier!r}) and {position} "
                    f"({original!r}) collide at {canonical!r}. Rename or remove one column.",
                )
                break
        if collision:
            _issue(report, 1, canonical, f"{collision[0]}_header_collision", collision[1])
        original_seen.setdefault(original, (original, position))
        normalized_seen.setdefault(normalized, (original, position))
        canonical_seen.setdefault(canonical, (original, position))
        if original != normalized:
            report["column_normalizations"].append({
                "column_position": position, "original_header": original,
                "normalized_header": normalized,
            })
        if normalized != canonical:
            report["aliases_mapped"].append({
                "column_position": position, "original_header": original,
                "canonical_field": canonical,
            })
    _stop(report)
    return result


def _date_value(value) -> tuple[pd.Timestamp, dict]:
    changes = {}
    if _missing(value):
        raise ValueError("missing")
    if isinstance(value, str):
        stripped = value.strip()
        if stripped != value:
            changes["date_whitespace_trimmed"] = 1
        for pattern, fmt in DATE_FORMATS:
            if re.fullmatch(pattern, stripped):
                parsed = datetime.strptime(stripped, fmt)
                changes["dates_parsed"] = 1
                break
        else:
            raise ValueError("invalid_date")
    elif isinstance(value, (pd.Timestamp, datetime, date)):
        parsed = value
    else:
        # Numbers, including Excel serial-like values and booleans, are not dates.
        raise ValueError("invalid_date")
    stamp = pd.Timestamp(parsed)
    if stamp.tzinfo is not None:
        raise ValueError("invalid_date")
    normalized = stamp.normalize().as_unit("ns")
    if normalized != stamp:
        changes["times_removed"] = 1
    return normalized, changes


def _number_value(value) -> tuple[float, bool]:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("boolean")
    if _missing(value):
        raise ValueError("missing")
    converted = isinstance(value, str)
    if converted and not NUMBER.fullmatch(value.strip()):
        raise ValueError("numeric_format")
    if not converted and not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError("numeric_format")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("non_finite")
    if numeric < 0:
        raise ValueError("negative")
    return numeric, converted


def _validate(df: pd.DataFrame, report: dict, source_rows: list[int]) -> tuple[pd.DataFrame, dict]:
    rows = df.copy(deep=True).reset_index(drop=True)
    rows.columns = _headers(list(df.columns), report)
    for field in sorted(REQUIRED - set(rows.columns)):
        _issue(report, 1, field, "missing_column", f"Add the required {field} column.")
    if rows.empty:
        _issue(report, None, "dataset", "empty_dataset", "Provide at least one sales row.")
    _stop(report)
    parsed_dates, products = [], []
    for position, value in enumerate(rows["date"]):
        try:
            parsed, changes = _date_value(value)
            parsed_dates.append(parsed)
            for key, count in changes.items():
                report["changes"][key] += count
        except (ValueError, TypeError, OverflowError):
            parsed_dates.append(pd.NaT)
            _issue(report, source_rows[position], "date", "invalid_date",
                   "Supply a valid year-first date (YYYY-MM-DD or YYYY/MM/DD), "
                   "or a supported naive datetime; do not use ambiguous dates, numbers, or timezones.")
    for position, value in enumerate(rows["product"]):
        if _missing(value):
            products.append("")
            _issue(report, source_rows[position], "product", "missing",
                   "Supply a non-empty product name.")
        else:
            text = str(value)
            products.append(text.strip())
            report["changes"]["products_trimmed"] += int(text != text.strip())
    rows["date"] = pd.Series(parsed_dates, dtype="datetime64[ns]")
    rows["product"] = products
    for field in ["quantity", "unit_price"] + (["unit_cost"] if "unit_cost" in rows else []):
        numbers = []
        for position, value in enumerate(rows[field]):
            try:
                number, converted = _number_value(value)
                numbers.append(number)
                report["changes"]["numeric_strings_converted"] += int(converted)
            except (ValueError, TypeError, OverflowError) as exc:
                numbers.append(float("nan"))
                # Only our controlled classification is exposed, never cell values.
                kind = str(exc) if str(exc) in {
                    "missing", "boolean", "numeric_format", "non_finite", "negative"
                } else "invalid_number"
                _issue(report, source_rows[position], field, kind,
                       f"Supply a finite non-negative number for {field}; "
                       "booleans, grouping/decimal commas, currency symbols and percentages are unsupported.")
        rows[field] = numbers
    _stop(report)
    with np.errstate(over="ignore", invalid="ignore"):
        calculated = {"revenue": rows["quantity"] * rows["unit_price"]}
        if "unit_cost" in rows:
            calculated["cost"] = rows["quantity"] * rows["unit_cost"]
        for field, values in calculated.items():
            for position in np.flatnonzero(~np.isfinite(values.to_numpy())):
                _issue(report, source_rows[int(position)], field, "overflow",
                       "Reduce the magnitude of quantity and price/cost; the calculated amount is outside the supported range.")
            if not np.isfinite(values.sum()):
                _issue(report, None, field, "total_overflow",
                       "Reduce sales value magnitudes; the total is outside the supported numeric range.")
        if not np.isfinite(rows["quantity"].sum()):
            _issue(report, None, "quantity", "total_overflow",
                   "Reduce quantity magnitudes; total units are outside the supported numeric range.")
    _stop(report)
    if "unit_cost" not in rows:
        report["warnings"].append("Unit costs are absent; profit and margins are unavailable.")
    # Group only duplicate rows. No customer cell values enter the report.
    repeated = rows.loc[rows.duplicated(keep=False)]
    remaining = repeated.index.tolist()
    while remaining:
        anchor = remaining[0]
        equal = repeated.eq(rows.loc[anchor]) | (repeated.isna() & rows.loc[anchor].isna())
        group = equal.all(axis=1)
        positions = repeated.index[group].tolist()
        report["duplicate_groups"].append({"source_rows": [source_rows[p] for p in positions]})
        grouped = set(positions)
        remaining = [p for p in remaining if p not in grouped]
    if report["duplicate_groups"]:
        report["warnings"].append(
            "Possible duplicate rows were retained. Identical rows can represent legitimate sales; review before deciding."
        )
    ordered = rows.sort_values("date", kind="stable")
    report.update(
        status="valid", output_row_count=len(rows),
        output_source_rows=[source_rows[p] for p in ordered.index],
    )
    return ordered.reset_index(drop=True), report


def validate_sales_with_report(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Validate positional rows (first data row = 2), preserving the input."""
    return _validate(df, _report("dataframe", len(df)), list(range(2, len(df) + 2)))


def validate_sales(df: pd.DataFrame) -> pd.DataFrame:
    return validate_sales_with_report(df)[0]


def _read_bytes(source, report: dict) -> bytes:
    try:
        if getattr(source, "size", 0) > MAX_BYTES:
            raise OverflowError
        if hasattr(source, "read"):
            if hasattr(source, "seek"):
                source.seek(0)
            content = source.read(MAX_BYTES + 1)
        else:
            with open(source, "rb") as handle:
                content = handle.read(MAX_BYTES + 1)
        if isinstance(content, str):
            content = content.encode("utf-8")
        if len(content) > MAX_BYTES:
            raise OverflowError
        return content
    except OverflowError:
        _issue(report, None, "file", "file_too_large", "Choose a file no larger than 10 MB.")
    except (OSError, ValueError, TypeError):
        _issue(report, None, "file", "unreadable_file", "Supply a readable CSV or .xlsx file.")
    _stop(report)


def _read_csv(content: bytes, report: dict) -> pd.DataFrame:
    try:
        records = list(csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True))
    except (UnicodeError, csv.Error):
        _issue(report, None, "file", "invalid_csv", "Supply a UTF-8 CSV with valid quoting and a header row.")
        _stop(report)
    if not records:
        _issue(report, None, "dataset", "empty_dataset", "Supply a header and at least one sales row.")
        _stop(report)
    headers, records = records[0], records[1:]
    report["input_row_count"] = len(records)
    # This check happens before DataFrame construction, so duplicates cannot be mangled.
    _headers(headers, report)
    for row, values in enumerate(records, start=2):
        if len(values) != len(headers):
            _issue(report, row, "record", "column_count",
                   "Supply exactly one cell per header; blank or ragged records cannot be discarded.")
    _stop(report)
    return pd.DataFrame(records, columns=headers, dtype=object)


def _read_excel(content: bytes, report: dict) -> pd.DataFrame:
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
        try:
            # OpenPyXL decodes date-formatted cells; ordinary numbers remain numbers.
            records = list(workbook.worksheets[0].iter_rows(values_only=True))
        finally:
            workbook.close()
    except Exception:
        _issue(report, None, "file", "invalid_excel", "Supply a valid .xlsx workbook with a first worksheet.")
        _stop(report)
    # Exclude formatting-only trailing rows/columns, never internal empty rows.
    while records and all(value is None for value in records[-1]):
        records.pop()
    if not records:
        _issue(report, None, "dataset", "empty_dataset", "Supply a header and at least one sales row.")
        _stop(report)
    width = max(i + 1 for row in records for i, value in enumerate(row) if value is not None)
    headers = list(records[0][:width])
    report["input_row_count"] = len(records) - 1
    _headers(headers, report)
    return pd.DataFrame([row[:width] for row in records[1:]], columns=headers, dtype=object)


def load_sales_with_report(source, filename: str | None = None) -> tuple[pd.DataFrame, dict]:
    name = filename or getattr(source, "name", str(source))
    suffix = Path(name).suffix.lower()
    report = _report("csv" if suffix == ".csv" else "excel" if suffix == ".xlsx" else "file")
    if suffix not in {".csv", ".xlsx"}:
        _issue(report, None, "file", "unsupported_type", "Choose a CSV or .xlsx Excel file.")
        _stop(report)
    content = _read_bytes(source, report)
    frame = _read_csv(content, report) if suffix == ".csv" else _read_excel(content, report)
    # Header checks at read time have already recorded transformations once.
    report["column_normalizations"] = []
    report["aliases_mapped"] = []
    return _validate(frame, report, list(range(2, len(frame) + 2)))


def load_sales(source, filename: str | None = None) -> pd.DataFrame:
    return load_sales_with_report(source, filename)[0]
