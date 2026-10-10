"""Parse and validate sales data without storing uploaded records."""
from pathlib import Path
import numpy as np
import pandas as pd

MAX_BYTES = 10 * 1024 * 1024
REQUIRED = {"date", "product", "quantity", "unit_price"}


def validate_sales(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    if df.columns.duplicated().any():
        raise ValueError("Column names must be unique after normalization.")
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    if df.empty:
        raise ValueError("The dataset has no sales rows.")
    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed")
    if df["date"].isna().any():
        raise ValueError("Every row needs a valid date, preferably YYYY-MM-DD.")
    df["date"] = df["date"].dt.normalize()
    if df["product"].isna().any() or df["product"].astype(str).str.strip().eq("").any():
        raise ValueError("Every row needs a non-empty product name.")
    df["product"] = df["product"].astype(str).str.strip()
    for column in ["quantity", "unit_price"] + (["unit_cost"] if "unit_cost" in df else []):
        df[column] = pd.to_numeric(df[column], errors="coerce")
        if not np.isfinite(df[column]).all() or (df[column] < 0).any():
            raise ValueError(f"{column} must contain finite, non-negative numbers in every row.")
    with np.errstate(over="ignore", invalid="ignore"):
        revenue = df["quantity"] * df["unit_price"]
        cost = df["quantity"] * df["unit_cost"] if "unit_cost" in df else None
        if not np.isfinite(revenue).all() or not np.isfinite(revenue.sum()):
            raise ValueError("Sales values are too large to calculate reliably.")
        if cost is not None and (not np.isfinite(cost).all() or not np.isfinite(cost.sum())):
            raise ValueError("Cost values are too large to calculate reliably.")
    return df.sort_values("date").reset_index(drop=True)


def load_sales(source, filename: str | None = None) -> pd.DataFrame:
    name = filename or getattr(source, "name", str(source))
    suffix = Path(name).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise ValueError("Choose a CSV or .xlsx Excel file.")
    size = getattr(source, "size", None)
    if size is not None and size > MAX_BYTES:
        raise ValueError("Please upload a file smaller than 10 MB.")
    try:
        if hasattr(source, "seek"):
            source.seek(0)
        df = pd.read_csv(source) if suffix == ".csv" else pd.read_excel(source, engine="openpyxl")
    except Exception as exc:
        raise ValueError("Could not read this file. Check that it is a valid CSV or .xlsx workbook.") from exc
    return validate_sales(df)
