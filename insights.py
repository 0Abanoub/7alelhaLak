"""Evidence-based observations, not AI-generated causal claims."""


def generate_insights(metrics: dict) -> list[str]:
    products = metrics["products"]
    top = products.iloc[0]
    messages = [
        f"{top['product']} has the highest revenue in the selected data: {top['revenue']:,.2f}.",
        f"The selected data contains {metrics['transaction_count']:,} sales rows across {len(products):,} products.",
    ]
    if metrics["total_profit"] is None:
        messages.append("Profit is unavailable. Add a unit_cost column to calculate profit and margin.")
    else:
        losses = products[products["profit"] < 0]
        if len(losses):
            messages.append(
                f"{len(losses)} products have negative profit. Review their unit costs and selling prices."
            )
        elif metrics["profit_margin"] is not None:
            messages.append(f"Overall profit margin is {metrics['profit_margin']:.1f}% before expenses not included in unit_cost.")
    messages.append("Sales history alone cannot confirm causes of changes or current inventory levels.")
    return messages
