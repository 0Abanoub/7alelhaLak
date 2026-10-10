# 7alelhaLak

Python 3.11 / Streamlit starter app. Keep the existing root-level Python
structure and Pandas/Plotly stack; no database or separate backend is needed.

## Run

Use the **Start application** workflow, or run:

```sh
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 5000
```

Dependencies are in `requirements.txt`. Replit manages the Python runtime and
installed packages; no virtual environment is needed here.

## Implemented

- Fictional sample sales and CSV/.xlsx uploads (10 MB limit).
- Required schema validation: date, product, quantity, unit_price.
- Optional unit_cost enables profit and margin; missing costs are never assumed.
- Date/product filters, sales KPIs, charts, tables, and rule-based observations.
- Sample CSV download.

Uploads are processed in the current session, not persisted or sent to external
services. Returns and negative amounts are not supported. Currency is unspecified
and follows the input data; files should use a single consistent currency.

AI chat, inventory analysis, and automatic column aliases remain planned,
not implemented. No secrets or external services are required for this starter.

## Verify

```sh
python -m unittest discover -s tests -v
```
