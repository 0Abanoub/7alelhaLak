# Analytics handoff

This is an analytics input/output contract, not an assumption about the future
data loader's function name, return type, or integration API.

`analyze_sales(df)` accepts a non-empty, already-cleaned Pandas DataFrame:

- `date`: normalized Pandas timestamps for each sale date.
- `product`: non-empty product names.
- `quantity`, `unit_price`: finite, non-negative numeric values.
- `unit_cost`: optional numeric unit costs. If absent or incomplete, all profit
  and cost summaries are unavailable (`None`), not zero.

The analytics layer does not load files, map columns, clean data, or drop rows.
The integration caller must supply a DataFrame meeting the contract after the
team's validation work is ready. Adapt that handoff only after inspecting and
agreeing on the actual loader interface.

## Results

- `total_revenue`, `total_cost`, `total_profit`, `profit_margin` (percentage),
  `units_sold`, `transaction_count` (sales rows, not distinct orders).
- `daily_sales`: DataFrame with `date`, `revenue`, sorted by date. Dates with no
  records are not invented or filled as zero.
- `products`: DataFrame with `product`, `quantity`, `revenue`, and, only with
  complete costs, `profit` and `profit_margin`. Sorted by revenue descending.
- `best_selling_products`: all products tied for most units sold.
- `most_profitable_products`: all tied profit leaders, or `None` without costs.
- `warnings`: understandable limitations such as incomplete costs or zero
  revenue. Product margin is missing when that product has zero revenue.

Revenue = quantity × unit_price; cost = quantity × unit_cost; total profit =
total revenue − total cost. Negative profit is valid. Zero costs are valid.
No currency conversion, taxes, discounts, returns, overhead, inventory
estimation, causal claims, or AI interpretation are included.

## Independent verification

```sh
python -m unittest discover -s tests -p 'test_analytics.py' -v
```

These tests build cleaned DataFrames directly and never import the data loader.
Full upload and application integration still need verification against the
completed teammate implementation.
