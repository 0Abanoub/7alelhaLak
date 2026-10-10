"""Conservative loader/report tests using in-memory files and sales frames."""
import copy
from datetime import date, datetime
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
from openpyxl import Workbook
import pandas as pd

from data_loader import (
    ALIASES, MAX_BYTES, SalesValidationError, load_sales, load_sales_with_report,
    validate_sales, validate_sales_with_report,
)


class LoaderReportTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({
            "date": ["2026-09-02", "2026-09-01"],
            "product": [" A ", "B"],
            "quantity": ["2", "3"],
            "unit_price": ["10.5", "20"],
            "unit_cost": ["6", "12"],
        })

    def excel(self, headers, records, formats=None):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for record in records:
            sheet.append(record)
        for cell, fmt in (formats or {}).items():
            sheet[cell].number_format = fmt
        stream = io.BytesIO()
        workbook.save(stream)
        workbook.close()
        stream.seek(0)
        return stream

    def csv(self, headers, row="2026-09-01,A,1,10"):
        return io.BytesIO((headers + "\n" + row + "\n").encode("utf-8"))

    def test_canonical_legacy_apis(self):
        df = validate_sales(self.frame())
        reported, report = validate_sales_with_report(self.frame())
        pd.testing.assert_frame_equal(df, reported)
        pd.testing.assert_frame_equal(load_sales("sample_data/sales.csv"),
                                     load_sales_with_report("sample_data/sales.csv")[0])
        self.assertEqual(report["status"], "valid")
        self.assertEqual(set(df.columns), set(self.frame().columns))

    def test_every_alias(self):
        for alias, canonical in ALIASES.items():
            with self.subTest(alias=alias):
                frame = self.frame().rename(columns={canonical: alias.replace("_", " ").title()})
                cleaned, report = validate_sales_with_report(frame)
                self.assertIn(canonical, cleaned.columns)
                self.assertEqual(report["aliases_mapped"][0]["canonical_field"], canonical)

    def test_unknown_columns_not_guessed_or_removed(self):
        frame = self.frame()
        frame[" Amount "] = [" untouched ", "002"]
        cleaned, _ = validate_sales_with_report(frame)
        self.assertEqual(cleaned["amount"].tolist(), ["002", " untouched "])
        frame = self.frame().rename(columns={"unit_price": "amount"})
        with self.assertRaises(SalesValidationError) as caught:
            validate_sales(frame)
        self.assertEqual(caught.exception.report["issues"][0]["canonical_field"], "unit_price")

    def test_all_collision_stages_dataframe(self):
        for headers, expected in [
            (["date", "product", "product", "quantity", "unit_price"], "original"),
            (["date", "Product Name", "product_name", "quantity", "unit_price"], "normalized"),
            (["date", "product", "Qty", "Quantity", "unit_price"], "alias"),
        ]:
            with self.subTest(stage=expected):
                frame = pd.DataFrame([["2026-09-01", "A", "A", 1, 10]], columns=headers)
                with self.assertRaises(SalesValidationError) as caught:
                    validate_sales(frame)
                report = caught.exception.report
                self.assertEqual(report["issues"][0]["issue_type"], expected + "_header_collision")
                self.assertEqual(report["issues"][0]["source_row"], 1)
                self.assertIn(repr(headers[1] if expected == "normalized" else headers[2]),
                              str(caught.exception))

    def test_original_and_mapped_collisions_csv_and_excel(self):
        for headers, kind in [
            (["date", "product", "quantity", "unit_price", "unit_price"], "original"),
            (["date", "Product Name", "product_name", "quantity", "unit_price"], "normalized"),
            (["date", "product", "Qty", "Quantity", "unit_price"], "alias"),
        ]:
            for suffix in ["csv", "xlsx"]:
                with self.subTest(headers=headers, suffix=suffix):
                    stream = (
                        self.csv(",".join(headers), "2026-09-01,A,1,10,10")
                        if suffix == "csv" else self.excel(headers, [["2026-09-01", "A", 1, 10, 10]])
                    )
                    with self.assertRaises(SalesValidationError) as caught:
                        load_sales(stream, "sales." + suffix)
                    self.assertEqual(caught.exception.report["issues"][0]["issue_type"],
                                     kind + "_header_collision")

    def test_header_whitespace_and_empty_header(self):
        frame = self.frame().rename(columns={"unit_price": "  Unit \t Price  "})
        cleaned, report = validate_sales_with_report(frame)
        self.assertIn("unit_price", cleaned)
        self.assertEqual(report["column_normalizations"][0]["original_header"], "  Unit \t Price  ")
        frame.columns = ["date", "product", "quantity", "", "unit_cost"]
        with self.assertRaises(SalesValidationError):
            validate_sales(frame)

    def test_alias_report_csv_excel_parity(self):
        headers = ["Sale Date", "Product Name", "Qty", "Price", "Cost Price"]
        row = ["2026-09-01", " A ", "1", "10", "6"]
        csv_result, csv_report = load_sales_with_report(self.csv(",".join(headers), ",".join(row)), "sales.csv")
        excel_result, excel_report = load_sales_with_report(self.excel(headers, [row]), "sales.xlsx")
        pd.testing.assert_frame_equal(csv_result, excel_result)
        self.assertEqual(csv_report["aliases_mapped"], excel_report["aliases_mapped"])
        self.assertEqual(len(csv_report["aliases_mapped"]), 5)
        self.assertEqual(csv_report["changes"], excel_report["changes"])

    def test_strict_accepted_date_formats_and_objects(self):
        values = [
            "2026-09-01", "2026/09/01", "2026-09-01 12:15",
            "2026-09-01 12:15:30", " 2026-09-01 ",
            date(2026, 9, 1), datetime(2026, 9, 1, 10), pd.Timestamp("2026-09-01 12:00"),
        ]
        for value in values:
            with self.subTest(value_type=type(value).__name__):
                frame = self.frame()
                frame["date"] = pd.Series([value, value], dtype=object)
                cleaned, _ = validate_sales_with_report(frame)
                self.assertEqual(cleaned["date"].tolist(), [pd.Timestamp("2026-09-01")] * 2)

    def test_invalid_calendar_ambiguous_timezone_and_numeric_dates(self):
        for value in [
            "2026-02-30", "2025-02-29", "2026-13-01", "2026-09-01 25:00",
            "01/02/2026", "2026-9-1", "2026-09-01T12:00:00Z",
            "2026-09-01 12:00+02:00", pd.Timestamp("2026-09-01", tz="UTC"),
            datetime.fromisoformat("2026-09-01T12:00:00+02:00"),
            20260901, 46266.0, True, None,
        ]:
            with self.subTest(value_type=type(value).__name__):
                frame = self.frame()
                frame["date"] = pd.Series([value, "2026-09-01"], dtype=object)
                with self.assertRaises(SalesValidationError) as caught:
                    validate_sales(frame)
                self.assertEqual(caught.exception.report["issues"][0]["source_row"], 2)
                self.assertEqual(caught.exception.report["issues"][0]["canonical_field"], "date")

    def test_genuine_excel_dates_and_general_numeric_dates(self):
        headers = ["date", "product", "quantity", "unit_price"]
        native = self.excel(headers, [[datetime(2026, 9, 1, 12), "A", 1, 10]])
        cleaned, report = load_sales_with_report(native, "sales.xlsx")
        self.assertEqual(cleaned.loc[0, "date"], pd.Timestamp("2026-09-01"))
        self.assertEqual(report["changes"]["times_removed"], 1)
        # A serial explicitly date-formatted is decoded by OpenPyXL, not guessed.
        formatted = self.excel(headers, [[46266, "A", 1, 10]], {"A2": "yyyy-mm-dd"})
        self.assertEqual(load_sales(formatted, "sales.xlsx").loc[0, "date"].year, 2026)
        general = self.excel(headers, [[46266, "A", 1, 10]])
        with self.assertRaises(SalesValidationError):
            load_sales(general, "sales.xlsx")

    def test_accepted_numbers(self):
        for value, expected in [
            (" 1.5 ", 1.5), ("+2", 2.0), (".5", 0.5), ("1.", 1.0),
            ("1e2", 100.0), ("2E-2", 0.02), (0, 0.0), (np.int64(2), 2.0),
        ]:
            with self.subTest(value=value):
                frame = self.frame()
                frame["quantity"] = pd.Series([value, value], dtype=object)
                cleaned, _ = validate_sales_with_report(frame)
                self.assertEqual(cleaned["quantity"].tolist(), [expected] * 2)

    def test_invalid_numeric_values(self):
        for value in [
            True, False, np.bool_(True), "1,000", "1,5", "$10", "10%", "inf",
            "NaN", float("inf"), float("nan"), -1, "-0.5", "1e999", None, "",
        ]:
            for field in ["quantity", "unit_price", "unit_cost"]:
                with self.subTest(value_type=type(value).__name__, field=field):
                    frame = self.frame()
                    frame[field] = pd.Series([value, "1"], dtype=object)
                    with self.assertRaises(SalesValidationError) as caught:
                        validate_sales(frame)
                    issue = caught.exception.report["issues"][0]
                    self.assertEqual(issue["source_row"], 2)
                    self.assertEqual(issue["canonical_field"], field)
                    if isinstance(value, (bool, np.bool_)):
                        self.assertEqual(issue["issue_type"], "boolean")

    def test_excel_boolean_rejected(self):
        stream = self.excel(["date", "product", "quantity", "unit_price"],
                            [["2026-09-01", "A", True, 10]])
        with self.assertRaises(SalesValidationError) as caught:
            load_sales(stream, "sales.xlsx")
        self.assertEqual(caught.exception.report["issues"][0]["issue_type"], "boolean")

    def test_rows_survive_sort_and_nondefault_index(self):
        frame = self.frame()
        frame.index = [99, 42]
        cleaned, report = validate_sales_with_report(frame)
        self.assertEqual(report["output_source_rows"], [3, 2])
        self.assertEqual(cleaned.index.tolist(), [0, 1])
        self.assertEqual(cleaned["product"].tolist(), ["B", "A"])
        self.assertEqual(set(cleaned.columns), set(frame.columns))
        frame.loc[99, "quantity"] = "invalid"
        with self.assertRaises(SalesValidationError) as caught:
            validate_sales(frame)
        self.assertEqual(caught.exception.report["issues"][0]["source_row"], 2)

    def test_multiline_csv_uses_logical_records(self):
        stream = io.BytesIO(
            b'date,product,quantity,unit_price\n2026-09-01,"A\nB",1,10\n2026-09-02,C,no,10\n'
        )
        with self.assertRaises(SalesValidationError) as caught:
            load_sales(stream, "sales.csv")
        self.assertEqual(caught.exception.report["issues"][0]["source_row"], 3)

    def test_internal_blank_rows_rejected(self):
        csv_stream = io.BytesIO(b"date,product,quantity,unit_price\n2026-09-01,A,1,10\n\n2026-09-02,B,1,10\n")
        excel_stream = self.excel(["date", "product", "quantity", "unit_price"],
                                 [["2026-09-01", "A", 1, 10], [None] * 4, ["2026-09-02", "B", 1, 10]])
        for stream, name in [(csv_stream, "sales.csv"), (excel_stream, "sales.xlsx")]:
            with self.subTest(name=name):
                with self.assertRaises(SalesValidationError) as caught:
                    load_sales(stream, name)
                self.assertIn(3, [issue["source_row"] for issue in caught.exception.report["issues"]])
                self.assertEqual(caught.exception.report["input_row_count"], 3)

    def test_excel_formatting_only_trailing_rows_columns(self):
        stream = self.excel(["date", "product", "quantity", "unit_price"],
                            [["2026-09-01", "A", 1, 10]], {"G10": "0.00"})
        cleaned, report = load_sales_with_report(stream, "sales.xlsx")
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(report["input_row_count"], 1)
        self.assertEqual(len(cleaned.columns), 4)

    def test_duplicates_retained_with_original_rows(self):
        frame = self.frame()
        frame = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
        cleaned, report = validate_sales_with_report(frame)
        self.assertEqual(len(cleaned), 3)
        self.assertEqual(report["duplicate_groups"], [{"source_rows": [2, 4]}])
        self.assertEqual(report["output_source_rows"], [3, 2, 4])
        self.assertTrue(any("legitimate sales" in warning for warning in report["warnings"]))

    def test_extra_columns_affect_duplicates(self):
        frame = pd.concat([self.frame().iloc[:1]] * 2, ignore_index=True)
        frame["order_id"] = ["001", "002"]
        self.assertEqual(validate_sales_with_report(frame)[1]["duplicate_groups"], [])
        frame["order_id"] = ["001", "001"]
        self.assertEqual(validate_sales_with_report(frame)[1]["duplicate_groups"],
                         [{"source_rows": [2, 3]}])
        frame["order_id"] = [None, float("nan")]
        self.assertEqual(validate_sales_with_report(frame)[1]["duplicate_groups"],
                         [{"source_rows": [2, 3]}])

    def test_report_never_exposes_customer_values(self):
        frame = self.frame()
        frame["product"] = "PRIVATE_CUSTOMER_PRODUCT_827"
        frame["quantity"] = "PRIVATE_BAD_VALUE_910"
        with self.assertRaises(SalesValidationError) as caught:
            validate_sales(frame)
        rendered = json.dumps(caught.exception.report) + str(caught.exception)
        self.assertNotIn("PRIVATE_", rendered)
        self.assertIsInstance(caught.exception, ValueError)
        self.assertFalse(hasattr(caught.exception, "dataframe"))
        self.assertEqual(caught.exception.report["output_row_count"], 0)
        self.assertEqual(caught.exception.report["output_source_rows"], [])
        self.assertEqual(set(caught.exception.report["issues"][0]),
                         {"source_row", "canonical_field", "issue_type", "actionable_fix"})
        frame["quantity"] = "1"
        cleaned, report = validate_sales_with_report(frame)
        self.assertIn("PRIVATE_", cleaned["product"].iloc[0])
        self.assertNotIn("PRIVATE_", json.dumps(report))

    def test_cleaning_counts_on_failure_and_success(self):
        frame = self.frame()
        frame["date"] = [" 2026-09-02 12:00 ", "2026-09-01"]
        _, report = validate_sales_with_report(frame)
        self.assertEqual(report["changes"]["products_trimmed"], 1)
        self.assertEqual(report["changes"]["dates_parsed"], 2)
        self.assertEqual(report["changes"]["date_whitespace_trimmed"], 1)
        self.assertEqual(report["changes"]["times_removed"], 1)
        self.assertEqual(report["changes"]["numeric_strings_converted"], 6)
        frame.loc[0, "quantity"] = "invalid"
        with self.assertRaises(SalesValidationError) as caught:
            validate_sales(frame)
        self.assertEqual(caught.exception.report["status"], "invalid")
        self.assertEqual(caught.exception.report["changes"]["products_trimmed"], 1)
        self.assertTrue(caught.exception.report["issues"])

    def test_missing_cost_warning_and_incomplete_cost_error(self):
        frame = self.frame().drop(columns="unit_cost")
        _, report = validate_sales_with_report(frame)
        self.assertIn("profit and margins are unavailable", report["warnings"][0])
        frame["unit_cost"] = [None, 1]
        with self.assertRaises(SalesValidationError):
            validate_sales(frame)

    def test_missing_fields_and_empty_frame(self):
        for frame in [self.frame().drop(columns="unit_price"), self.frame().iloc[:0]]:
            with self.subTest(columns=list(frame.columns)):
                with self.assertRaises(SalesValidationError):
                    validate_sales(frame)

    def test_overflow_and_integer_wraparound(self):
        for field in ["unit_price", "unit_cost", "quantity"]:
            with self.subTest(field=field):
                frame = self.frame()
                frame[field] = 1e308
                with self.assertRaises(SalesValidationError):
                    validate_sales(frame)
        frame = self.frame()
        frame["quantity"] = 4_000_000_000
        frame["unit_price"] = 4_000_000_000
        cleaned = validate_sales(frame)
        self.assertEqual((cleaned["quantity"] * cleaned["unit_price"]).iloc[0], 1.6e19)

    def test_total_units_overflow(self):
        frame = self.frame()
        frame["quantity"] = 1e308
        frame["unit_price"] = 0
        frame["unit_cost"] = 0
        with self.assertRaises(SalesValidationError) as caught:
            validate_sales(frame)
        self.assertEqual(caught.exception.report["issues"][0]["canonical_field"], "quantity")

    def test_csv_literal_na_product_preserved(self):
        cleaned = load_sales(self.csv("date,product,quantity,unit_price", "2026-09-01,NA,1,10"), "sales.csv")
        self.assertEqual(cleaned.loc[0, "product"], "NA")

    def test_invalid_files_and_size_limit(self):
        for stream, name in [
            (io.BytesIO(b""), "empty.csv"),
            (io.BytesIO(b"not excel"), "broken.xlsx"),
            (io.BytesIO(b"PRIVATE_BAD"), "bad.txt"),
            (io.BytesIO(b"\xff"), "bad.csv"),
            (io.BytesIO(b"date,product,quantity,unit_price\n\"PRIVATE_BAD"), "bad.csv"),
            (io.BytesIO(b"x" * (MAX_BYTES + 1)), "large.csv"),
        ]:
            with self.subTest(name=name):
                with self.assertRaises(SalesValidationError) as caught:
                    load_sales(stream, name)
                self.assertNotIn("PRIVATE_BAD", json.dumps(caught.exception.report))

    def test_inputs_not_mutated(self):
        frame = self.frame()
        original = copy.deepcopy(frame)
        validate_sales_with_report(frame)
        pd.testing.assert_frame_equal(frame, original)


class ReportDisplayTests(unittest.TestCase):
    def test_success_report_and_dashboard(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertIn("Data validation report", [item.value for item in app.subheader])
        self.assertEqual(len(app.metric), 5)

    def test_failure_report_stops_before_analytics(self):
        from streamlit.testing.v1 import AppTest
        frame = LoaderReportTests().frame()
        frame.loc[0, "quantity"] = "SECRET_INVALID_VALUE"
        try:
            validate_sales(frame)
        except SalesValidationError as error:
            failure = error
        with patch("data_loader.load_sales_with_report", side_effect=failure), \
                patch("analytics.analyze_sales") as analytics:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(len(app.metric), 0)
        self.assertIn("Data validation report", [item.value for item in app.subheader])
        self.assertNotIn("SECRET", app.error[0].value)
        analytics.assert_not_called()


if __name__ == "__main__":
    unittest.main()
