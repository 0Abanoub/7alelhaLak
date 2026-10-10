# Sales data validation and cleaning

`validate_sales(df)` and `load_sales(source, filename=None)` still return a
DataFrame or raise `ValueError`. The corresponding `*_with_report` functions
return `(cleaned_dataframe, report)`. They share one validation implementation.
Failures raise `SalesValidationError`, a `ValueError` subclass with a `report`
but no cleaned or partial DataFrame. Invalid data must not reach analytics.

## Headers

Trim, lowercase, replace each whitespace run with `_`, then apply only:

| Alias | Canonical field |
| --- | --- |
| sale_date, sales_date | date |
| product_name | product |
| qty, units_sold | quantity |
| price, selling_price | unit_price |
| cost_price | unit_cost |

Canonical names remain valid. Unknown columns remain present. No punctuation
removal, fuzzy matching, or locale guessing is performed.

Original CSV/Excel headers are inspected before DataFrame construction.
Reject exact original duplicates, normalization collisions (`Product Name`
and `product_name`), and alias collisions (`Qty` and `Quantity`). Diagnostics
retain original header names and column positions. Empty headers are rejected.

## Values

- Product names: trim surrounding whitespace; preserve case/internal spaces.
- Dates: native Python date/naive datetime and Pandas Timestamp, or exact
  year-first strings `YYYY-MM-DD`, `YYYY/MM/DD`, `YYYY-MM-DD HH:MM`,
  `YYYY-MM-DD HH:MM:SS`. Surrounding whitespace is trimmed. Calendar validity
  and Pandas nanosecond date range are checked; times are removed and counted.
- No ambiguous day/month formats, timezones, or numeric date-like values.
  OpenPyXL decodes genuine date-formatted Excel cells into native objects.
  General-format numeric cells are not manually interpreted as Excel serials.
- Numbers: numeric cells or strings with optional sign, dot decimal syntax,
  and optional scientific notation; surrounding whitespace is allowed.
  Booleans, grouping/decimal commas, currencies, percentages, missing values,
  negatives and non-finite values are rejected. Zero values remain valid.
- Check revenue, cost and total units for overflow using floating-point
  arithmetic, not fixed-width integer multiplication.
- All required values must be present. Missing `unit_cost` columns are allowed
  with a warning; invalid/incomplete supplied unit costs are rejected.

CSV is UTF-8 (optional BOM), comma-delimited, with a header record. CSV cells
are read without Pandas type or missing-value inference, preserving text such
as the product name `NA`. Excel uses the first worksheet; formulas are not
evaluated and formulas in required numeric/date fields are rejected.
The 10 MB input limit applies to streams and paths, not just objects with size.

## Source rows and duplicates

CSV uses logical record numbers: header = 1, first data record = 2; embedded
newlines within quoted fields do not create additional record rows. Excel uses
actual worksheet row numbers. In-memory DataFrames use positional rows starting
at 2, independently of their index. Blank/ragged CSV records and internal empty
Excel data rows are errors, not silently discarded. Formatting-only trailing
Excel rows and columns are outside the data region.

All retained columns, including extras, participate in exact cleaned-row
duplicate matching. Extra values are not cleaned; different order IDs mean
different rows. Null extra values compare as missing values. Every row is
retained. Identical rows can represent legitimate sales; duplicate groups
are review warnings, not deletion instructions.

Source row identity stays separate from the public DataFrame. Stable date
sorting preserves ties; `output_source_rows` maps each output position back to
its source row. No helper columns are returned.

## Safe report

- `status`: valid/invalid.
- `source_kind`, `input_row_count`, `output_row_count`, `output_source_rows`.
- `column_normalizations`, `aliases_mapped`: header-only provenance.
- `changes`: counts of successful product trimming, date parsing, date
  whitespace trimming, time removal and numeric string conversion.
- `issues`: source_row (null for file/aggregate errors), canonical_field,
  issue_type, actionable_fix. Headers/schema issues refer to row 1.
- `duplicate_groups`: original source row numbers only.
- `warnings`: unavailable costs and retained possible duplicates.

No raw customer cell values appear in reports or exception messages. Parser
exception text is not displayed. Header names are included only for required
column diagnostics. Failed reports retain counts of successful transformations
attempted but distinguish these from unresolved issues; output row count stays
zero and no DataFrame is returned. Report display does not log customer records.

Streamlit displays the cleaning report before analytics; failures display the
issues and stop. This does not introduce a confirmation button.

## Verification

```sh
python -m unittest discover -s tests -p 'test_data_loader.py' -v
python -m unittest discover -s tests -v
```
