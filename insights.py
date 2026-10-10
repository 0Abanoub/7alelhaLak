"""Rule-based insights from analytics summaries, without cleaning sales data.

Rules (screening benchmarks, never statistical significance):
- Compare the latest two observed dates only if they are consecutive calendar
  days. A day-level snapshot is not evidence of a sustained trend or full-day
  coverage. Never fill missing dates with zero.
- High revenue means at least total revenue / number of summarized products.
  Weak margin means below the overall revenue-weighted margin.
- A substantial profit contributor has positive profit of at least total net
  profit / number of products; only evaluate when total net profit is positive.
  Its share may exceed 100% when other products lose money.

The existing list[str] interface is preserved. Four labeled sections separate
findings, suggested actions, rules, and limitations for app.py's string loop.
Product declines are deferred: the contract has no product-by-date summaries.
"""
import math
import pandas as pd


RULES = (
    "Compare only the latest two consecutive observed calendar dates. "
    "High revenue means at least an equal share of total revenue (total / product count); "
    "weak margin means below the overall margin. "
    "Substantial profit contribution means positive profit at least an equal share "
    "of positive total net profit. These are screening rules, not statistical significance."
)


def _finite(value) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (ValueError, TypeError, OverflowError):
        return False


def _numeric_summary(frame: pd.DataFrame, columns: tuple[str, ...]) -> bool:
    return all(
        column in frame
        and pd.api.types.is_numeric_dtype(frame[column])
        and frame[column].map(_finite).all()
        for column in columns
    )


def _compare_days(daily, findings: list[str], actions: list[str], limits: list[str]) -> None:
    if (
        not isinstance(daily, pd.DataFrame)
        or "date" not in daily
        or not _numeric_summary(daily, ("revenue",))
        or not pd.api.types.is_datetime64_any_dtype(daily["date"])
        or daily["date"].isna().any()
        or daily["date"].duplicated().any()
    ):
        limits.append("Daily revenue comparison is unavailable without valid dated summaries.")
        return
    if len(daily) < 2:
        limits.append("At least two observed dates are needed for a daily revenue comparison.")
        return
    ordered = daily.sort_values("date")
    previous, latest = ordered.iloc[-2], ordered.iloc[-1]
    first_date, second_date = previous["date"].date(), latest["date"].date()
    if (second_date - first_date).days != 1:
        limits.append(
            f"Latest observed dates {first_date} and {second_date} are not consecutive; "
            "no daily change is reported and missing dates are not treated as zero sales."
        )
        return
    before, after = float(previous["revenue"]), float(latest["revenue"])
    change = after - before
    if not _finite(change):
        limits.append("Daily revenue change is outside the supported numeric range.")
        return
    direction = "increased" if change > 0 else "decreased" if change < 0 else "was unchanged"
    percentage = change / before * 100 if before > 0 else None
    detail = f" ({abs(percentage):.1f}%)" if _finite(percentage) else ""
    findings.append(
        f"Observed daily revenue {direction} from {before:,.2f} on {first_date} "
        f"to {after:,.2f} on {second_date}; absolute change {change:+,.2f}{detail}."
    )
    if before == 0:
        limits.append("Percentage change is undefined because the earlier observed revenue is zero.")
    elif percentage is not None and not _finite(percentage):
        limits.append("Percentage change is outside the supported numeric range.")
    limits.append(
        "This compares recorded revenue on two days, not a sustained trend. "
        "Full-day coverage and comparable trading conditions are not established."
    )
    if change != 0:
        actions.append("Check reporting completeness and transaction details before interpreting the daily change.")


def generate_insights(metrics: dict) -> list[str]:
    """Return labeled findings/actions/rules/limitations without mutating metrics."""
    findings, actions = [], []
    limits = [
        "Product declines cannot be assessed: dated product-level sales are not supplied.",
        "These summaries cannot establish causes or current inventory. "
        "Profit excludes expenses not included in unit_cost.",
    ]
    products = metrics.get("products")
    total_revenue = metrics.get("total_revenue")
    total_profit = metrics.get("total_profit")
    overall_margin = metrics.get("profit_margin")
    _compare_days(metrics.get("daily_sales"), findings, actions, limits)
    valid_products = (
        isinstance(products, pd.DataFrame)
        and not products.empty
        and "product" in products
        and products["product"].notna().all()
        and not products["product"].duplicated().any()
        and _numeric_summary(products, ("quantity", "revenue"))
    )
    if not valid_products:
        limits.append("Product findings are unavailable because product summaries are empty or incomplete.")
    else:
        count = len(products)
        top_revenue = products["revenue"].max()
        leaders = sorted(products.loc[products["revenue"].eq(top_revenue), "product"].astype(str))
        findings.append(
            f"Highest-revenue product(s): {', '.join(leaders)}; each has revenue {top_revenue:,.2f}."
        )
        rows = metrics.get("transaction_count")
        if _finite(rows) and float(rows) >= 0:
            findings.append(f"The selection contains {float(rows):,.0f} sales rows across {count:,} products.")
        costs_complete = _finite(total_profit) and _numeric_summary(products, ("profit",))
        if not costs_complete:
            limits.append("Profit and margin findings are unavailable because cost summaries are missing or incomplete.")
            actions.append("Supply complete unit costs before reviewing profitability.")
        else:
            if _finite(overall_margin):
                findings.append(f"Overall profit margin is {float(overall_margin):.1f}%.")
            else:
                limits.append("Overall margin is unavailable; no weak-margin screening is performed.")
            losses = products.loc[products["profit"].lt(0), "product"].astype(str).sort_values()
            if len(losses):
                findings.append(f"Negative-profit products: {', '.join(losses)}.")
                actions.append("Review selling prices and unit costs for the negative-profit products.")
            if _finite(total_revenue) and float(total_revenue) > 0 and _finite(overall_margin):
                positive = products.loc[products["revenue"].gt(0)]
                if _numeric_summary(positive, ("profit_margin",)):
                    revenue_benchmark = float(total_revenue) / count
                    weak = positive.loc[
                        positive["revenue"].ge(revenue_benchmark)
                        & positive["profit_margin"].lt(float(overall_margin))
                    ].sort_values("product")
                    for _, product in weak.iterrows():
                        findings.append(
                            f"High-revenue / weak-margin product {product['product']}: "
                            f"revenue {product['revenue']:,.2f} (benchmark {revenue_benchmark:,.2f}), "
                            f"margin {product['profit_margin']:.1f}% versus overall {float(overall_margin):.1f}%."
                        )
                    if not weak.empty:
                        actions.append("Review pricing and unit costs for the flagged high-revenue / weak-margin products.")
                else:
                    limits.append("Weak-margin screening needs complete margins for positive-revenue products.")
            elif not _finite(total_revenue) or float(total_revenue) <= 0:
                limits.append("Revenue-based screening is unavailable without positive total revenue.")
            if float(total_profit) > 0:
                benchmark = float(total_profit) / count
                contributors = products.loc[
                    products["profit"].gt(0) & products["profit"].ge(benchmark)
                ].sort_values(["profit", "product"], ascending=[False, True])
                for _, product in contributors.iterrows():
                    share = float(product["profit"]) / float(total_profit) * 100
                    if _finite(share):
                        findings.append(
                            f"Substantial profit contributor {product['product']}: "
                            f"profit {product['profit']:,.2f}, {share:.1f}% of total net profit "
                            f"(equal-share benchmark {benchmark:,.2f})."
                        )
                    else:
                        limits.append("A profit contribution share is outside the supported numeric range.")
                if not contributors.empty:
                    actions.append("Review the listed profit contributors when prioritizing product decisions.")
                if len(losses):
                    limits.append("Profit shares can exceed 100% because losing products offset positive contributions.")
            else:
                limits.append("Profit contribution percentages are unavailable when total net profit is zero or negative.")
    for warning in metrics.get("warnings", []) or []:
        if isinstance(warning, str) and warning not in limits:
            limits.append(warning)
    return [
        "Findings: " + (" ".join(findings) if findings else "No supported findings are available."),
        "Suggested actions: " + (" ".join(actions) if actions else "No specific action is supported by these summaries."),
        "Rules: " + RULES,
        "Limitations: " + " ".join(limits),
    ]
