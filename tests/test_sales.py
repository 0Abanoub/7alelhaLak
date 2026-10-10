import io
import unittest
import pandas as pd
from analytics import analyze_sales
from data_loader import load_sales, validate_sales
from insights import generate_insights


class SalesTests(unittest.TestCase):
    def test_sample_totals(self):
        metrics = analyze_sales(load_sales("sample_data/sales.csv"))
        self.assertEqual(metrics["total_revenue"], 4800)
        self.assertEqual(metrics["total_profit"], 1920)
        self.assertEqual(metrics["profit_margin"], 40)
        self.assertEqual(metrics["units_sold"], 34)
        self.assertEqual(len(generate_insights(metrics)), 4)

    def test_no_cost(self):
        df = load_sales("sample_data/sales.csv").drop(columns="unit_cost")
        metrics = analyze_sales(df)
        self.assertIsNone(metrics["total_profit"])
        self.assertIsNone(metrics["profit_margin"])

    def test_zero_revenue(self):
        df = load_sales("sample_data/sales.csv")
        df["unit_price"] = 0
        self.assertIsNone(analyze_sales(df)["profit_margin"])

    def test_bad_data(self):
        valid = load_sales("sample_data/sales.csv")
        for column, value in [
            ("quantity", -1), ("unit_price", float("inf")),
            ("unit_cost", None), ("date", "not a date"), ("product", ""),
        ]:
            with self.subTest(column=column):
                df = valid.copy()
                df[column] = value
                with self.assertRaises(ValueError):
                    validate_sales(df)
        with self.assertRaises(ValueError):
            validate_sales(valid.iloc[:0])
        with self.assertRaises(ValueError):
            validate_sales(valid.drop(columns="quantity"))

    def test_file_errors(self):
        with self.assertRaises(ValueError):
            load_sales(io.BytesIO(b""), "empty.csv")
        with self.assertRaises(ValueError):
            load_sales(io.BytesIO(b"not excel"), "broken.xlsx")

    def test_excel(self):
        data = io.BytesIO()
        load_sales("sample_data/sales.csv").to_excel(data, index=False)
        metrics = analyze_sales(load_sales(data, "sales.xlsx"))
        self.assertEqual(metrics["total_revenue"], 4800)

    def test_normalized_columns(self):
        df = load_sales("sample_data/sales.csv")
        df.columns = [" Date ", "Product", "Quantity", "Unit Price", "Unit Cost"]
        self.assertIn("unit_price", validate_sales(df).columns)


if __name__ == "__main__":
    unittest.main()
