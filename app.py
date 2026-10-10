"""7alelhaLak: minimal runnable sales analytics application."""
from pathlib import Path
import streamlit as st
from analytics import analyze_sales
from dashboard import render_dashboard
from data_loader import load_sales_with_report, SalesValidationError
from insights import generate_insights

st.set_page_config(page_title="7alelhaLak | حللهالك", layout="wide")
st.title("7alelhaLak | حللهالك")
st.caption("Understand your business data. Start with the demo or upload your own sales.")

with st.sidebar:
    st.header("Your data")
    mode = st.radio("Data source", ["Sample data", "Upload a file"])
    uploaded = None
    if mode == "Upload a file":
        uploaded = st.file_uploader("Sales file (up to 10 MB)", type=["csv", "xlsx"])
    st.caption("Required: date, product, quantity, unit_price. Optional: unit_cost.")
    st.caption("Dates: YYYY-MM-DD. Numbers must be non-negative; returns are not supported.")
    st.download_button(
        "Download sample CSV",
        Path(__file__).with_name("sample_data").joinpath("sales.csv").read_bytes(),
        "sales.csv",
        "text/csv",
    )
    st.caption("Uploads are analyzed in this session and are not saved to a database or sent to an AI provider.")

if mode == "Upload a file" and uploaded is None:
    st.info("Upload a CSV or Excel file to see your sales dashboard.")
    st.stop()


def show_validation_report(report):
    st.subheader("Data validation report")
    st.caption(
        f"{report['input_row_count']:,} source rows; "
        f"{report['output_row_count']:,} valid output rows. "
        "CSV record rows / Excel worksheet rows start at 2 after the header. "
        "No sales rows are discarded."
    )
    with st.expander("Cleaning details and rows needing attention", expanded=report["status"] == "invalid"):
        st.write("Status: " + report["status"])
        st.write("Successful transformations: " + ", ".join(
            f"{key.replace('_', ' ')}: {value}" for key, value in report["changes"].items()
        ))
        for key, title in [
            ("column_normalizations", "Header normalization"),
            ("aliases_mapped", "Column aliases"),
            ("issues", "Validation issues"),
            ("duplicate_groups", "Possible duplicate source rows"),
        ]:
            if report[key]:
                st.write(title)
                st.dataframe(report[key], hide_index=True, width="stretch")
    for warning in report["warnings"]:
        st.warning(warning)


try:
    df, validation_report = load_sales_with_report(
        Path(__file__).with_name("sample_data").joinpath("sales.csv")
        if mode == "Sample data" else uploaded
    )
except SalesValidationError as exc:
    st.error(str(exc))
    show_validation_report(exc.report)
    st.stop()
except ValueError as exc:
    st.error(str(exc))
    st.stop()

show_validation_report(validation_report)

if mode == "Sample data":
    st.info("Demo mode — these are fictional sales, not your business results.")

with st.sidebar:
    options = sorted(df["product"].unique())
    selected = st.multiselect("Products", options, default=options)
    dates = st.date_input(
        "Date range",
        value=(df["date"].min().date(), df["date"].max().date()),
        min_value=df["date"].min().date(),
        max_value=df["date"].max().date(),
    )
if len(dates) != 2:
    st.info("Choose both a start and an end date.")
    st.stop()
filtered = df[
    df["product"].isin(selected)
    & df["date"].dt.date.between(dates[0], dates[1])
]
if filtered.empty:
    st.info("No sales match these filters. Choose another date range or product.")
    st.stop()

metrics = analyze_sales(filtered)
render_dashboard(metrics)
st.subheader("Business observations")
st.caption("Calculated from your selected data. These are rule-based observations, not AI answers.")
for message in generate_insights(metrics):
    st.write("• " + message)
with st.expander("View selected sales data"):
    st.dataframe(filtered, hide_index=True, width="stretch")
st.caption("AI Business Analyst is not connected in this starter version.")
