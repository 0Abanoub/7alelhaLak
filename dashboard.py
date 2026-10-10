"""Streamlit dashboard for 7alelhaLak sales analytics."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


_INK = "#203b3d"
_MUTED = "#6f8583"
_TEAL = "#237d79"
_TEAL_LIGHT = "#d9ebe5"
_CORAL = "#d47a5b"


def _number(value: Any, decimals: int = 2) -> str:
    """Format a real numeric value without assuming a currency."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "Unavailable"
    if pd.isna(numeric):
        return "Unavailable"
    return f"{numeric:,.{decimals}f}"


def _frame(metrics: dict, key: str, required: tuple[str, ...]) -> pd.DataFrame:
    value = metrics.get(key)
    if not isinstance(value, pd.DataFrame):
        return pd.DataFrame(columns=list(required))
    frame = value.copy()
    if not all(column in frame.columns for column in required):
        return pd.DataFrame(columns=list(required))
    return frame


def _apply_dashboard_style() -> None:
    st.markdown(
        """
        <style>
        :root {
          --dash-ink: #203b3d;
          --dash-muted: #6f8583;
          --dash-teal: #237d79;
          --dash-paper: #f3f6f1;
          --dash-line: #dce7e1;
        }
        .stApp {
          background:
            radial-gradient(ellipse at 88% 4%, rgba(217, 235, 229, .55), transparent 28rem),
            #f3f6f1;
          color: var(--dash-ink);
        }
        [data-testid="stHeader"] { background: transparent; }
        .block-container {
          max-width: 1440px;
          padding-top: 2.35rem;
          padding-bottom: 3rem;
        }
        .dash-kicker {
          color: var(--dash-teal);
          font-size: .72rem;
          font-weight: 750;
          letter-spacing: .16em;
          text-transform: uppercase;
          margin: 0 0 .65rem;
        }
        .dash-title {
          color: var(--dash-ink);
          font-size: clamp(2rem, 4vw, 3.1rem);
          font-weight: 720;
          letter-spacing: -.055em;
          line-height: 1.05;
          margin: 0;
        }
        .dash-subtitle {
          color: var(--dash-muted);
          font-size: 1rem;
          line-height: 1.55;
          margin: .7rem 0 1.35rem;
        }
        .dash-section {
          color: var(--dash-ink);
          font-size: 1.15rem;
          font-weight: 700;
          letter-spacing: -.025em;
          margin: 0 0 .15rem;
        }
        .dash-section-note {
          color: var(--dash-muted);
          font-size: .84rem;
          margin: 0 0 .85rem;
        }
        [data-testid="stMetric"] {
          background: rgba(255, 255, 255, .74);
          border: 1px solid var(--dash-line);
          border-radius: 14px;
          padding: 1rem 1.05rem .95rem;
          min-height: 112px;
          box-shadow: 0 5px 18px rgba(42, 74, 67, .035);
        }
        [data-testid="stMetricLabel"] {
          color: var(--dash-muted);
          font-size: .8rem;
          font-weight: 600;
        }
        [data-testid="stMetricValue"] {
          color: var(--dash-ink);
          font-size: clamp(1.35rem, 2vw, 1.8rem);
          font-weight: 720;
          letter-spacing: -.04em;
        }
        div[data-testid="stVerticalBlock"] div[data-testid="stPlotlyChart"] {
          background: rgba(255, 255, 255, .76);
          border: 1px solid var(--dash-line);
          border-radius: 16px;
          padding: .45rem .55rem .15rem;
        }
        [data-testid="stDataFrame"] {
          border: 1px solid var(--dash-line);
          border-radius: 14px;
          overflow: hidden;
        }
        .dash-divider {
          height: 1px;
          background: var(--dash-line);
          margin: .6rem 0 1.25rem;
        }
        @media (max-width: 700px) {
          .block-container { padding: 1.4rem 1rem 2rem; }
          [data-testid="stMetric"] { min-height: 96px; padding: .8rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _section(title: str, note: str) -> None:
    st.markdown(
        f'<div class="dash-section">{title}</div>'
        f'<div class="dash-section-note">{note}</div>',
        unsafe_allow_html=True,
    )


def render_dashboard(metrics: dict) -> None:
    """Render business KPIs, revenue trend, product ranking, and product table."""
    _apply_dashboard_style()

    st.markdown(
        '<div class="dash-kicker">7alelhaLak / Business overview</div>'
        '<h1 class="dash-title">Your numbers, in focus.</h1>'
        '<p class="dash-subtitle">A clear view of sales performance and product movement.</p>',
        unsafe_allow_html=True,
    )
    st.caption("Values are shown as neutral numbers; currency follows the uploaded input data.")

    profit = metrics.get("total_profit")
    margin = metrics.get("profit_margin")
    profit_value = _number(profit) if profit is not None else "Unavailable"
    margin_value = f"{_number(margin)}%" if margin is not None else "Unavailable"
    revenue = _number(metrics.get("total_revenue"))
    units = _number(metrics.get("units_sold"), decimals=2)
    transactions = metrics.get("transaction_count")
    try:
        transaction_value = f"{int(transactions):,}" if transactions is not None else "Unavailable"
    except (TypeError, ValueError, OverflowError):
        transaction_value = "Unavailable"

    kpi_columns = st.columns(5)
    for column, label, value in zip(
        kpi_columns,
        ("Total revenue", "Total profit", "Profit margin", "Units sold", "Transactions"),
        (revenue, profit_value, margin_value, units, transaction_value),
    ):
        with column:
            st.metric(label, value)

    if profit is None:
        st.info(
            "Profit and margin are unavailable because cost data is missing. "
            "No profit has been estimated."
        )
    elif margin is None:
        if metrics.get("total_revenue") == 0:
            st.info(
                "Profit margin is unavailable because total revenue is zero. "
                "Profit is calculated from the supplied costs."
            )
        else:
            st.info("Profit margin is unavailable; calculated profit is shown.")

    st.markdown('<div class="dash-divider"></div>', unsafe_allow_html=True)
    daily_sales = _frame(metrics, "daily_sales", ("date", "revenue"))
    products = _frame(metrics, "products", ("product", "quantity", "revenue"))

    trend_column, ranking_column = st.columns([1.45, 1], gap="large")
    with trend_column:
        _section("Revenue over time", "Daily revenue from the available sales history.")
        if daily_sales.empty:
            st.info("No dated sales records are available to display a revenue trend.")
        else:
            daily_sales["date"] = pd.to_datetime(daily_sales["date"], errors="coerce")
            daily_sales["revenue"] = pd.to_numeric(daily_sales["revenue"], errors="coerce")
            trend = (
                daily_sales.dropna(subset=["date", "revenue"])
                .groupby("date", as_index=False, sort=True)["revenue"]
                .sum()
            )
            if trend.empty:
                st.info("The available dates or revenue values could not be plotted.")
            else:
                chart = go.Figure()
                chart.add_trace(
                    go.Scatter(
                        x=trend["date"],
                        y=trend["revenue"],
                        mode="lines+markers",
                        line={"color": _TEAL, "width": 3, "shape": "spline"},
                        marker={"color": _TEAL, "size": 6},
                        fill="tozeroy",
                        fillcolor="rgba(35, 125, 121, .10)",
                        hovertemplate="%{x|%b %d, %Y}<br>Revenue: %{y:,.2f}<extra></extra>",
                    )
                )
                chart.update_layout(
                    height=330,
                    margin={"l": 12, "r": 18, "t": 18, "b": 8},
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    font={"family": "sans-serif", "color": _INK, "size": 12},
                    hoverlabel={"bgcolor": "#203b3d", "font_color": "#f3f6f1"},
                )
                chart.update_xaxes(
                    showgrid=False,
                    linecolor="#dce7e1",
                    tickfont={"color": _MUTED},
                    title_text=None,
                )
                chart.update_yaxes(
                    rangemode="tozero",
                    gridcolor="#e8efeb",
                    zeroline=False,
                    tickformat=",.0f",
                    tickfont={"color": _MUTED},
                    title_text=None,
                )
                st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})

    with ranking_column:
        _section("Product ranking", "Best sellers ranked by units sold.")
        if products.empty:
            st.info("No product-level sales data is available to rank.")
        else:
            product_data = products.copy()
            product_data["quantity"] = pd.to_numeric(product_data["quantity"], errors="coerce")
            ranked = (
                product_data.dropna(subset=["product", "quantity"])
                .groupby("product", as_index=False)["quantity"]
                .sum()
                .sort_values("quantity", ascending=False, kind="stable")
                .head(10)
                .sort_values("quantity", ascending=True, kind="stable")
            )
            if ranked.empty:
                st.info("Product names or unit counts are not available for ranking.")
            else:
                chart = go.Figure(
                    go.Bar(
                        x=ranked["quantity"],
                        y=ranked["product"].astype(str),
                        orientation="h",
                        marker={"color": _TEAL, "cornerradius": 5},
                        hovertemplate="%{y}<br>Units sold: %{x:,.2f}<extra></extra>",
                    )
                )
                chart.update_layout(
                    height=max(330, 42 * len(ranked) + 45),
                    margin={"l": 8, "r": 18, "t": 18, "b": 8},
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    font={"family": "sans-serif", "color": _INK, "size": 12},
                    hoverlabel={"bgcolor": "#203b3d", "font_color": "#f3f6f1"},
                )
                chart.update_xaxes(
                    rangemode="tozero",
                    gridcolor="#e8efeb",
                    zeroline=False,
                    tickfont={"color": _MUTED},
                    title_text=None,
                )
                chart.update_yaxes(showgrid=False, tickfont={"color": _INK}, title_text=None)
                st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="dash-divider"></div>', unsafe_allow_html=True)
    _section("Product performance", "Revenue and units for each product in the analyzed data.")
    if products.empty:
        st.info("The product performance table will appear when product data is available.")
    else:
        table = products.copy()
        table["quantity"] = pd.to_numeric(table["quantity"], errors="coerce")
        table["revenue"] = pd.to_numeric(table["revenue"], errors="coerce")
        if "profit" in table.columns:
            table["profit"] = pd.to_numeric(table["profit"], errors="coerce")
            has_profit = table["profit"].notna().any()
        else:
            has_profit = False
        table = table.groupby("product", as_index=False, dropna=False).agg(
            quantity=("quantity", "sum"),
            revenue=("revenue", "sum"),
            **({"profit": ("profit", "sum")} if has_profit else {}),
        )
        table = table.sort_values("revenue", ascending=False, na_position="last", kind="stable")
        if not has_profit:
            table["profit"] = "Unavailable (cost data missing)"
        else:
            table["profit"] = table["profit"].map(
                lambda value: _number(value) if pd.notna(value) else "Unavailable"
            )
        table = table.rename(
            columns={
                "product": "Product",
                "quantity": "Units sold",
                "revenue": "Revenue",
                "profit": "Profit",
            }
        )
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Units sold": st.column_config.NumberColumn(format="%.2f"),
                "Revenue": st.column_config.NumberColumn(format="%,.2f"),
            },
        )
        if not has_profit:
            st.caption("Product profit is unavailable because product-level cost data is missing.")
