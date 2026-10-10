"""Focused privacy, margin-range, and zero-revenue upload regressions."""
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from analytics import analyze_sales
from data_loader import SalesValidationError, load_sales_with_report
from streamlit.testing.v1 import AppTest


HEADER = "date,product,quantity,unit_price,unit_cost\n"
APP = str(Path(__file__).resolve().parents[1] / "app.py")


class UploadRegressionTests(unittest.TestCase):
    def load(self, content):
        return load_sales_with_report(io.BytesIO(content.encode()), "review.csv")

    def run_app(self, content):
        # Real in-memory parsing/validation; this is not a browser file upload.
        with patch("data_loader.load_sales_with_report",
                   side_effect=lambda *args, **kwargs: self.load(content)):
            return AppTest.from_file(APP).run(timeout=20)

    def test_headerless_csv_redacts_sales_values(self):
        content = (
            "2026-09-01, PRIVATE_REVIEW_MARKER ,2,10,6\n"
            "2026-09-02,Other,1,5,3\n"
        )
        with self.assertRaises(SalesValidationError) as caught:
            self.load(content)
        report = caught.exception.report
        self.assertNotIn("PRIVATE_REVIEW_MARKER", json.dumps(report))
        self.assertNotIn("PRIVATE_REVIEW_MARKER", str(caught.exception))
        self.assertEqual(report["status"], "invalid")
        self.assertTrue(any(issue["issue_type"] == "missing_column"
                            for issue in report["issues"]))
        self.assertEqual(report["column_normalizations"][0]["column_position"], 2)
        self.assertEqual(report["output_row_count"], 0)
        with patch("analytics.analyze_sales") as analytics, \
                patch("dashboard.render_dashboard") as dashboard, \
                patch("insights.generate_insights") as insights:
            app = self.run_app(content)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertNotIn("PRIVATE_REVIEW_MARKER", app.error[0].value)
        for table in app.dataframe:
            self.assertNotIn("PRIVATE_REVIEW_MARKER", table.value.to_json())
        analytics.assert_not_called()
        dashboard.assert_not_called()
        insights.assert_not_called()

    def test_untrusted_header_collisions_still_detected_without_leaks(self):
        for headers, kind in [
            ("PRIVATE_REVIEW_MARKER,PRIVATE_REVIEW_MARKER", "original"),
            (" Private Review Marker ,private_review_marker", "normalized"),
        ]:
            with self.subTest(kind=kind):
                content = "date,product,quantity,unit_price," + headers + "\n"
                content += "2026-09-01,A,1,10,extra,extra\n"
                with self.assertRaises(SalesValidationError) as caught:
                    self.load(content)
                issue = caught.exception.report["issues"][0]
                self.assertEqual(issue["issue_type"], kind + "_header_collision")
                self.assertEqual(issue["canonical_field"], "header")
                self.assertIn("Columns 5", issue["actionable_fix"])
                self.assertIn("and 6", issue["actionable_fix"])
                serialized = (json.dumps(caught.exception.report)
                              + str(caught.exception)).lower()
                self.assertNotIn("private_review_marker", serialized)
                self.assertNotIn("private review marker", serialized)

    def test_unknown_columns_preserved_but_not_echoed_in_report(self):
        content = (
            HEADER.rstrip("\n") + ", PRIVATE_REVIEW_MARKER \n"
            "2026-09-01,A,1,10,6,original-extra\n"
        )
        frame, report = self.load(content)
        self.assertEqual(frame["private_review_marker"].iloc[0], "original-extra")
        self.assertNotIn("PRIVATE_REVIEW_MARKER", json.dumps(report).upper())

    def test_exact_margin_overflow_rejected_with_actionable_report(self):
        content = HEADER + "2026-09-01,A,1,1e-308,100\n"
        with self.assertRaises(SalesValidationError) as caught:
            self.load(content)
        report = caught.exception.report
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["output_row_count"], 0)
        self.assertEqual(report["output_source_rows"], [])
        issue = next(issue for issue in report["issues"] if issue["source_row"] == 2)
        self.assertEqual(issue["canonical_field"], "profit_margin")
        self.assertEqual(issue["issue_type"], "overflow")
        self.assertIn("Review unit prices and unit costs", issue["actionable_fix"])
        with patch("analytics.analyze_sales") as analytics:
            app = self.run_app(content)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertIn("profit margin", app.error[0].value)
        self.assertEqual(len(app.metric), 0)
        analytics.assert_not_called()

    def test_overflowing_filter_has_safe_error_and_no_dashboard(self):
        # The whole product is representable; selecting only the first day is not.
        content = (
            HEADER + "2026-09-01,A,1,1e-308,100\n"
            "2026-09-02,A,1,100,0\n"
        )
        frame, report = self.load(content)
        self.assertEqual(report["status"], "valid")
        self.assertEqual(analyze_sales(frame)["total_profit"], 0)
        with patch("data_loader.load_sales_with_report",
                   side_effect=lambda *args, **kwargs: self.load(content)):
            app = AppTest.from_file(APP).run(timeout=20)
            self.assertEqual(len(app.metric), 5)
            app.date_input[0].set_value(
                (frame["date"].iloc[0].date(), frame["date"].iloc[0].date())
            )
            with patch("dashboard.render_dashboard") as dashboard, \
                    patch("insights.generate_insights") as insights:
                app.run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertIn("Review quantities, unit prices and unit costs", app.error[0].value)
        self.assertEqual(len(app.metric), 0)
        dashboard.assert_not_called()
        insights.assert_not_called()

    def test_calculation_error_text_is_not_echoed(self):
        with patch("analytics.analyze_sales",
                   side_effect=ValueError("PRIVATE_REVIEW_MARKER")):
            app = self.run_app(HEADER + "2026-09-01,A,1,10,6\n")
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertNotIn("PRIVATE_REVIEW_MARKER", app.error[0].value)
        self.assertEqual(len(app.metric), 0)

    def test_zero_revenue_keeps_profit_and_explains_margin(self):
        content = HEADER + "2026-09-01,A,1,0,10\n"
        frame, report = self.load(content)
        metrics = analyze_sales(frame)
        self.assertEqual(report["status"], "valid")
        self.assertEqual(metrics["total_profit"], -10)
        self.assertIsNone(metrics["profit_margin"])
        app = self.run_app(content)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        values = {item.label: item.value for item in app.metric}
        self.assertEqual(values["Total profit"], "-10.00")
        self.assertEqual(values["Profit margin"], "Unavailable")
        messages = "\n".join(item.value for item in app.info)
        self.assertIn("total revenue is zero", messages)
        self.assertNotIn("cost data is missing", messages)

    def test_negative_profit_and_missing_costs_still_supported(self):
        content = HEADER + "2026-09-01,A,1,5,10\n"
        frame, report = self.load(content)
        metrics = analyze_sales(frame)
        self.assertEqual(report["status"], "valid")
        self.assertEqual(metrics["total_profit"], -5)
        self.assertEqual(metrics["profit_margin"], -100)
        no_cost = "date,product,quantity,unit_price\n2026-09-01,A,1,10\n"
        app = self.run_app(no_cost)
        self.assertEqual(len(app.exception), 0)
        self.assertIn("cost data is missing", "\n".join(item.value for item in app.info))


if __name__ == "__main__":
    unittest.main()
