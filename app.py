"""7alelhaLak: minimal runnable sales analytics application."""
from hashlib import sha256
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

UPLOAD_CACHE_KEY = "_latest_validated_upload_v1"
if mode != "Upload a file" or uploaded is None:
    st.session_state.pop(UPLOAD_CACHE_KEY, None)

if mode == "Upload a file" and uploaded is None:
    st.info("Upload a CSV or Excel file to see your sales dashboard.")
    st.stop()


def show_validation_report(report, source_key):
    st.subheader("Data validation report")
    st.caption(
        f"{report['input_row_count']:,} source rows; "
        f"{report['output_row_count']:,} valid output rows. "
        "CSV record rows / Excel worksheet rows start at 2 after the header. "
        "No sales rows are discarded."
    )
    with st.expander(
        "Cleaning details and rows needing attention",
        expanded=report["status"] == "invalid",
        key=f"validation_details:{source_key!r}:{report['status']}",
        on_change="rerun",
    ) as details:
        if details.open:
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


source_key = (mode,)
try:
    if mode == "Upload a file":
        # The extension affects parsing; equal names/sizes alone are not identity.
        source_key = (
            mode, Path(uploaded.name).suffix.lower(),
            sha256(uploaded.getvalue()).hexdigest(),
        )
        cached = st.session_state.get(UPLOAD_CACHE_KEY)
        if cached is not None and cached["source_key"] == source_key:
            df, validation_report = cached["dataframe"], cached["report"]
        else:
            # Invalidate before loading: a failed replacement cannot revive old data.
            st.session_state.pop(UPLOAD_CACHE_KEY, None)
            df, validation_report = load_sales_with_report(uploaded)
            st.session_state[UPLOAD_CACHE_KEY] = {
                "source_key": source_key, "dataframe": df, "report": validation_report,
            }
    else:
        df, validation_report = load_sales_with_report(
            Path(__file__).with_name("sample_data").joinpath("sales.csv")
        )
except SalesValidationError as exc:
    st.session_state.pop(UPLOAD_CACHE_KEY, None)
    st.error(str(exc))
    show_validation_report(exc.report, source_key)
    st.stop()
except ValueError as exc:
    st.session_state.pop(UPLOAD_CACHE_KEY, None)
    st.error(str(exc))
    st.stop()

show_validation_report(validation_report, source_key)

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

try:
    metrics = analyze_sales(filtered)
except (ValueError, OverflowError, FloatingPointError):
    st.error(
        "The selected sales are outside the supported calculation range. "
        "Review quantities, unit prices and unit costs, or choose a different "
        "selection. No dashboard or observations were generated."
    )
    st.stop()
render_dashboard(metrics)
st.subheader("Business observations")
st.caption("Calculated from your selected data. These are rule-based observations, not AI answers.")
for message in generate_insights(metrics):
    st.write("• " + message)
with st.expander(
    "View selected sales data", key=f"raw_sales:{source_key!r}", on_change="rerun",
) as raw_sales:
    if raw_sales.open:
        st.dataframe(filtered, hide_index=True, width="stretch")
st.caption("AI Business Analyst is not connected in this starter version.")
