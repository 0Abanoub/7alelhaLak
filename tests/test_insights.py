"""In-memory insight checks: no loaders, external services, or Streamlit."""
import copy
import unittest
import pandas as pd
from analytics import analyze_sales
from insights import generate_insights


class InsightTests(unittest.TestCase):
    def metrics(self):
        return {
            "total_revenue": 400.0, "total_profit": 100.0,
            "profit_margin": 25.0, "transaction_count": 8,
            "daily_sales": pd.DataFrame({
                "date": pd.to_datetime(["2026-09-01", "2026-09-02"]),
                "revenue": [250.0, 150.0],
            }),
            "products": pd.DataFrame({
                "product": ["A", "B"], "quantity": [10.0, 10.0],
                "revenue": [300.0, 100.0], "profit": [30.0, 70.0],
                "profit_margin": [10.0, 70.0],
            }), "warnings": [],
        }

    def text(self, metrics):
        return "\n".join(generate_insights(metrics))

    def test_public_interface_and_labeled_sections(self):
        messages = generate_insights(self.metrics())
        self.assertEqual(len(messages), 4)
        for message, prefix in zip(messages, ["Findings:", "Suggested actions:", "Rules:", "Limitations:"]):
            self.assertIsInstance(message, str)
            self.assertTrue(message.startswith(prefix))

    def test_observed_daily_decline(self):
        text = self.text(self.metrics())
        self.assertIn("decreased from 250.00 on 2026-09-01 to 150.00 on 2026-09-02", text)
        self.assertIn("absolute change -100.00 (40.0%)", text)
        self.assertIn("not a sustained trend", text)
        self.assertIn("not statistical significance", text)

    def test_daily_increase_and_unchanged(self):
        for revenues, phrase in [([100.0, 150.0], "increased"), ([100.0, 100.0], "was unchanged")]:
            with self.subTest(revenues=revenues):
                m = self.metrics()
                m["daily_sales"]["revenue"] = revenues
                self.assertIn(f"Observed daily revenue {phrase}", self.text(m))

    def test_latest_pair_sorted(self):
        m = self.metrics()
        m["daily_sales"] = pd.DataFrame({
            "date": pd.to_datetime(["2026-09-03", "2026-09-01", "2026-09-02"]),
            "revenue": [200.0, 50.0, 150.0],
        })
        self.assertIn("from 150.00 on 2026-09-02 to 200.00 on 2026-09-03", self.text(m))

    def test_missing_dates_not_zero_filled(self):
        m = self.metrics()
        m["daily_sales"]["date"] = pd.to_datetime(["2026-09-01", "2026-09-03"])
        text = self.text(m)
        self.assertIn("not consecutive", text)
        self.assertIn("missing dates are not treated as zero", text)
        self.assertNotIn("Observed daily revenue", text)

    def test_sparse_history(self):
        for daily in [self.metrics()["daily_sales"].iloc[:1], self.metrics()["daily_sales"].iloc[:0], None]:
            with self.subTest(daily=daily):
                m = self.metrics()
                m["daily_sales"] = daily
                self.assertNotIn("Observed daily revenue", self.text(m))

    def test_zero_previous_revenue(self):
        m = self.metrics()
        m["daily_sales"]["revenue"] = [0.0, 150.0]
        text = self.text(m)
        self.assertIn("absolute change +150.00", text)
        self.assertIn("Percentage change is undefined", text)
        self.assertNotIn("absolute change +150.00 (", text)

    def test_high_revenue_weak_margin(self):
        text = self.text(self.metrics())
        self.assertIn("High-revenue / weak-margin product A:", text)
        self.assertIn("revenue 300.00 (benchmark 200.00)", text)
        self.assertIn("margin 10.0% versus overall 25.0%", text)
        self.assertNotIn("High-revenue / weak-margin product B:", text)

    def test_weak_margin_boundary_and_zero_revenue_product(self):
        m = self.metrics()
        m["products"].loc[0, "profit_margin"] = 25.0
        self.assertNotIn("High-revenue / weak-margin product A:", self.text(m))
        m["products"].loc[0, "profit_margin"] = 10.0
        m["products"].loc[1, "revenue"] = 0.0
        m["products"].loc[1, "profit_margin"] = float("nan")
        self.assertIn("High-revenue / weak-margin product A:", self.text(m))
        self.assertNotIn("High-revenue / weak-margin product B:", self.text(m))

    def test_profit_contribution(self):
        text = self.text(self.metrics())
        self.assertIn("Substantial profit contributor B: profit 70.00, 70.0%", text)
        self.assertNotIn("Substantial profit contributor A:", text)

    def test_all_tied_leaders_and_contributors(self):
        m = self.metrics()
        m["products"]["revenue"] = 200.0
        m["products"]["profit"] = 50.0
        m["products"]["profit_margin"] = 25.0
        text = self.text(m)
        self.assertIn("Highest-revenue product(s): A, B;", text)
        self.assertIn("Substantial profit contributor A:", text)
        self.assertIn("Substantial profit contributor B:", text)
        self.assertNotIn("High-revenue / weak-margin product ", text)

    def test_missing_and_incomplete_cost_summaries(self):
        for remove_profit in [True, False]:
            with self.subTest(remove_profit=remove_profit):
                m = self.metrics()
                m["total_profit"] = None
                m["profit_margin"] = None
                if remove_profit:
                    m["products"] = m["products"].drop(columns=["profit", "profit_margin"])
                else:
                    m["products"].loc[0, "profit"] = float("nan")
                text = self.text(m)
                self.assertIn("cost summaries are missing or incomplete", text)
                self.assertNotIn("High-revenue / weak-margin product ", text)
                self.assertNotIn("Substantial profit contributor ", text)

    def test_zero_and_negative_profit_denominators(self):
        for total in [0.0, -10.0]:
            with self.subTest(total=total):
                m = self.metrics()
                m["total_profit"] = total
                text = self.text(m)
                self.assertIn("total net profit is zero or negative", text)
                self.assertNotIn("Substantial profit contributor ", text)

    def test_losses_and_share_over_100(self):
        m = self.metrics()
        m["products"]["profit"] = [-50.0, 150.0]
        m["products"]["profit_margin"] = [-50.0 / 3, 150.0]
        text = self.text(m)
        self.assertIn("Negative-profit products: A.", text)
        self.assertIn("profit 150.00, 150.0% of total net profit", text)
        self.assertIn("losing products offset positive contributions", text)

    def test_zero_total_revenue(self):
        m = self.metrics()
        m["total_revenue"] = 0.0
        m["total_profit"] = -40.0
        m["profit_margin"] = None
        m["products"]["revenue"] = 0.0
        m["products"]["profit"] = -20.0
        m["products"]["profit_margin"] = float("nan")
        text = self.text(m)
        self.assertIn("without positive total revenue", text)
        self.assertNotIn("High-revenue / weak-margin product ", text)
        self.assertNotIn("Substantial profit contributor ", text)

    def test_empty_product_summaries(self):
        m = self.metrics()
        m["products"] = m["products"].iloc[:0]
        text = self.text(m)
        self.assertIn("product summaries are empty or incomplete", text)
        self.assertNotIn("Highest-revenue product(s):", text)
        self.assertIn("Observed daily revenue decreased", text)
        self.assertEqual(len(generate_insights({})), 4)

    def test_no_product_declines_or_inventory_claims(self):
        text = self.text(self.metrics())
        self.assertIn("Product declines cannot be assessed", text)
        self.assertIn("cannot establish causes or current inventory", text)

    def test_warnings_preserved(self):
        m = self.metrics()
        m["warnings"] = ["Source coverage is limited."]
        self.assertIn("Source coverage is limited.", self.text(m))

    def test_inputs_unchanged(self):
        m = self.metrics()
        original = copy.deepcopy(m)
        generate_insights(m)
        for key in ["products", "daily_sales"]:
            pd.testing.assert_frame_equal(m[key], original[key])
        self.assertEqual(m["warnings"], original["warnings"])

    def test_actual_analytics_output(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2026-09-01", "2026-09-02"]),
            "product": ["A", "B"], "quantity": [1.0, 1.0],
            "unit_price": [100.0, 50.0], "unit_cost": [70.0, 10.0],
        })
        text = self.text(analyze_sales(df))
        self.assertIn("decreased from 100.00", text)
        self.assertIn("High-revenue / weak-margin product A:", text)
        self.assertIn("Substantial profit contributor B:", text)
        text_without_cost = self.text(analyze_sales(df.drop(columns="unit_cost")))
        self.assertNotIn("Substantial profit contributor ", text_without_cost)
        self.assertIn("cost summaries are missing or incomplete", text_without_cost)

    def test_unusable_daily_summary(self):
        m = self.metrics()
        m["daily_sales"]["revenue"] = [float("inf"), 100.0]
        self.assertIn("without valid dated summaries", self.text(m))
        m["daily_sales"] = self.metrics()["daily_sales"]
        m["daily_sales"]["date"] = pd.to_datetime(["2026-09-01", "2026-09-01"])
        self.assertIn("without valid dated summaries", self.text(m))


if __name__ == "__main__":
    unittest.main()
