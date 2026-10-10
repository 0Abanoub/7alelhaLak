"""Analytics-only checks: intentionally do not import the data loader."""
import unittest
import pandas as pd
from analytics import analyze_sales


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        # Fixture matches the README schema and represents already-cleaned data.
        self.df = pd.DataFrame({
            "date": pd.to_datetime(["2026-09-01", "2026-09-01", "2026-09-02"]),
            "product": ["A", "B", "A"],
            "quantity": [2.0, 3.0, 1.0],
            "unit_price": [10.0, 20.0, 10.0],
            "unit_cost": [6.0, 12.0, 6.0],
        })

    def test_totals_and_rankings(self):
        m = analyze_sales(self.df)
        self.assertEqual(m["total_revenue"], 90)
        self.assertEqual(m["total_cost"], 54)
        self.assertEqual(m["total_profit"], 36)
        self.assertEqual(m["profit_margin"], 40)
        self.assertEqual(m["units_sold"], 6)
        self.assertEqual(m["transaction_count"], 3)
        self.assertCountEqual(m["best_selling_products"], ["A", "B"])
        self.assertEqual(m["most_profitable_products"], ["B"])
        self.assertEqual(m["warnings"], [])

    def test_daily_and_product_results(self):
        m = analyze_sales(self.df)
        self.assertEqual(m["daily_sales"]["revenue"].tolist(), [80, 10])
        products = m["products"].set_index("product")
        self.assertEqual(products.loc["A", "revenue"], 30)
        self.assertEqual(products.loc["A", "profit"], 12)
        self.assertEqual(products.loc["B", "quantity"], 3)
        self.assertEqual(products.loc["B", "profit_margin"], 40)

    def test_missing_or_incomplete_cost_never_becomes_zero(self):
        absent = self.df.drop(columns="unit_cost")
        partial = self.df.copy()
        partial.loc[0, "unit_cost"] = float("nan")
        for df in [absent, partial]:
            with self.subTest(columns=list(df.columns)):
                m = analyze_sales(df)
                self.assertEqual(m["total_revenue"], 90)
                for key in ["total_cost", "total_profit", "profit_margin", "most_profitable_products"]:
                    self.assertIsNone(m[key])
                self.assertNotIn("profit", m["products"])
                self.assertTrue(m["warnings"])

    def test_zero_revenue(self):
        self.df["unit_price"] = 0.0
        m = analyze_sales(self.df)
        self.assertEqual(m["total_profit"], -54)
        self.assertIsNone(m["profit_margin"])
        self.assertTrue(m["products"]["profit_margin"].isna().all())

    def test_zero_cost_is_valid(self):
        self.df["unit_cost"] = 0.0
        m = analyze_sales(self.df)
        self.assertEqual(m["total_profit"], 90)
        self.assertEqual(m["profit_margin"], 100)

    def test_input_unchanged(self):
        original = self.df.copy(deep=True)
        analyze_sales(self.df)
        pd.testing.assert_frame_equal(self.df, original)

    def test_empty_and_missing_schema(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            analyze_sales(self.df.iloc[:0])
        with self.assertRaisesRegex(ValueError, "unit_price"):
            analyze_sales(self.df.drop(columns="unit_price"))

    def test_fractional_units_and_negative_profit(self):
        self.df["quantity"] = [0.5, 1.0, 0.5]
        self.df["unit_cost"] = 30.0
        m = analyze_sales(self.df)
        self.assertEqual(m["units_sold"], 2)
        self.assertEqual(m["total_revenue"], 30)
        self.assertEqual(m["total_profit"], -30)


if __name__ == "__main__":
    unittest.main()
