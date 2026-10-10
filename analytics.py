"""Deterministic calculations for an already-cleaned sales DataFrame.

Input contract, not a loader integration: date contains normalized pandas
timestamps; product contains non-empty names; quantity and unit_price contain
finite non-negative numbers. unit_cost is optional. No parsing, cleaning,
renaming, or row dropping happens here. The caller owns data validation.
"""
import numpy as np
import pandas as pd


def _require_finite(values) -> None:
    if not np.isfinite(values).all():
        raise ValueError("Sales values are too large to calculate reliably.")


def analyze_sales(df: pd.DataFrame) -> dict:
    """Compute only supported metrics without changing the caller's data."""
    required = {"date", "product", "quantity", "unit_price"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError("Analytics requires cleaned columns: " + ", ".join(sorted(missing)))
    if df.empty:
        raise ValueError("Analytics requires at least one cleaned sales row.")
    rows = df.copy()
    # Floating-point arithmetic prevents silent fixed-width integer wraparound.
    quantity = rows["quantity"].astype(float)
    with np.errstate(over="ignore", invalid="ignore"):
        rows["revenue"] = quantity * rows["unit_price"].astype(float)
    _require_finite(rows["revenue"])
    # Incomplete costs cannot support a complete-dataset profit calculation.
    has_cost = "unit_cost" in rows and rows["unit_cost"].notna().all()
    warnings = []
    if not has_cost:
        warnings.append("Profit and margin are unavailable because unit costs are missing or incomplete.")
    columns = ["quantity", "revenue"]
    if has_cost:
        with np.errstate(over="ignore", invalid="ignore"):
            rows["cost"] = quantity * rows["unit_cost"].astype(float)
        _require_finite(rows["cost"])
        rows["profit"] = rows["revenue"] - rows["cost"]
        columns.append("profit")
    rows["quantity"] = quantity
    with np.errstate(over="ignore", invalid="ignore"):
        total = float(rows["revenue"].sum())
        cost = float(rows["cost"].sum()) if has_cost else None
        units = float(quantity.sum())
    profit = total - cost if has_cost else None
    _require_finite(np.array([total, units] + ([cost, profit] if has_cost else [])))
    products = rows.groupby("product", as_index=False)[columns].sum().sort_values(
        ["revenue", "product"], ascending=[False, True]
    ).reset_index(drop=True)
    _require_finite(products[columns].to_numpy())
    daily_sales = rows.groupby("date", as_index=False)["revenue"].sum()
    _require_finite(daily_sales["revenue"])
    if has_cost:
        products["profit_margin"] = products["profit"].div(
            products["revenue"].where(products["revenue"].ne(0))
        ) * 100
        _require_finite(products["profit_margin"].dropna())
    margin = profit / total * 100 if has_cost and total else None
    if margin is not None:
        _require_finite(np.array([margin]))
    if total == 0:
        warnings.append("Profit margin is unavailable when total revenue is zero.")
    return {
        "total_revenue": total,
        "total_cost": cost,
        "total_profit": profit,
        "profit_margin": margin,
        "units_sold": units,
        "transaction_count": len(rows),
        "daily_sales": daily_sales,
        "products": products,
        "best_selling_products": products.loc[
            products["quantity"].eq(products["quantity"].max()), "product"
        ].tolist(),
        "most_profitable_products": products.loc[
            products["profit"].eq(products["profit"].max()), "product"
        ].tolist() if has_cost else None,
        "warnings": warnings,
    }
