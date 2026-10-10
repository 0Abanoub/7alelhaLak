"""Deterministic calculations for validated sales rows."""
import pandas as pd


def analyze_sales(df: pd.DataFrame) -> dict:
    rows = df.copy()
    rows["revenue"] = rows["quantity"] * rows["unit_price"]
    has_cost = "unit_cost" in rows
    columns = ["quantity", "revenue"]
    if has_cost:
        rows["profit"] = rows["revenue"] - rows["quantity"] * rows["unit_cost"]
        columns.append("profit")
    total = float(rows["revenue"].sum())
    profit = float(rows["profit"].sum()) if has_cost else None
    return {
        "total_revenue": total,
        "total_profit": profit,
        "profit_margin": profit / total * 100 if has_cost and total else None,
        "units_sold": float(rows["quantity"].sum()),
        "transaction_count": len(rows),
        "daily_sales": rows.groupby("date", as_index=False)["revenue"].sum(),
        "products": rows.groupby("product", as_index=False)[columns].sum().sort_values(
            "revenue", ascending=False
        ),
    }
