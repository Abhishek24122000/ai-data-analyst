"""
Generates a realistic synthetic sales dataset used as the built-in demo
dataset. Deliberately injects missing values and duplicate rows so the
data-quality panel and profiler have something real to report.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REGIONS = ["North", "South", "East", "West"]
SEGMENTS = ["Enterprise", "SMB", "Consumer"]
CATEGORIES = ["Electronics", "Home & Kitchen", "Apparel", "Sporting Goods", "Office Supplies"]
CHANNELS = ["Online", "Retail", "Partner"]

REGION_WEIGHTS = [0.32, 0.18, 0.28, 0.22]
CATEGORY_BASE_PRICE = {
    "Electronics": 220.0,
    "Home & Kitchen": 65.0,
    "Apparel": 40.0,
    "Sporting Goods": 55.0,
    "Office Supplies": 25.0,
}


def generate_sales_dataset(n_rows: int = 48_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    start = pd.Timestamp("2024-07-01")
    end = pd.Timestamp("2026-07-31")
    total_days = (end - start).days

    # Slight upward trend + yearly seasonality (Nov/Dec spike) baked into the
    # day-of-year sampling weights so month-over-month growth questions have
    # a real, non-random answer.
    day_offsets = np.arange(total_days + 1)
    dates_all = start + pd.to_timedelta(day_offsets, unit="D")
    month_of = dates_all.month
    seasonal = 1.0 + 0.35 * np.isin(month_of, [11, 12]) + 0.10 * np.isin(month_of, [6, 7])
    trend = 1.0 + 0.00035 * day_offsets  # ~+12% revenue drift over the period
    weights = seasonal * trend
    weights = weights / weights.sum()

    day_idx = rng.choice(day_offsets, size=n_rows, p=weights)
    order_date = start + pd.to_timedelta(day_idx, unit="D")

    region = rng.choice(REGIONS, size=n_rows, p=REGION_WEIGHTS)
    segment = rng.choice(SEGMENTS, size=n_rows, p=[0.22, 0.38, 0.40])
    category = rng.choice(CATEGORIES, size=n_rows)
    channel = rng.choice(CHANNELS, size=n_rows, p=[0.55, 0.30, 0.15])

    base_price = np.array([CATEGORY_BASE_PRICE[c] for c in category])
    unit_price = np.round(base_price * rng.lognormal(mean=0.0, sigma=0.25, size=n_rows), 2)
    units = rng.integers(1, 12, size=n_rows)

    # Enterprise customers buy in larger bulk on average.
    units = np.where(segment == "Enterprise", units + rng.integers(3, 20, size=n_rows), units)

    discount_pct = rng.choice([0, 0, 0, 5, 10, 15, 20], size=n_rows) / 100.0
    revenue = np.round(unit_price * units * (1 - discount_pct), 2)

    customer_id = rng.integers(10_000, 10_000 + n_rows // 3, size=n_rows)
    order_id = np.arange(1, n_rows + 1)

    df = pd.DataFrame(
        {
            "order_id": order_id,
            "order_date": order_date,
            "customer_id": customer_id,
            "region": region,
            "customer_segment": segment,
            "product_category": category,
            "sales_channel": channel,
            "units": units,
            "unit_price": unit_price,
            "discount_pct": discount_pct,
            "revenue": revenue,
        }
    )

    # --- Inject realistic data-quality issues -------------------------------
    # 1) Missing values in a few columns
    for col, frac in [("unit_price", 0.006), ("region", 0.004), ("customer_segment", 0.003)]:
        idx = rng.choice(df.index, size=int(len(df) * frac), replace=False)
        df.loc[idx, col] = np.nan

    # 2) Duplicate rows (common in real exports)
    dup_idx = rng.choice(df.index, size=int(len(df) * 0.007), replace=False)
    df = pd.concat([df, df.loc[dup_idx]], ignore_index=True)

    # 3) A few outlier revenue rows (data-entry errors)
    outlier_idx = rng.choice(df.index, size=8, replace=False)
    df.loc[outlier_idx, "revenue"] = df.loc[outlier_idx, "revenue"] * 55

    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return df


if __name__ == "__main__":
    out = generate_sales_dataset()
    out.to_csv("sample_sales.csv", index=False)
    print(f"Wrote sample_sales.csv with {len(out):,} rows")
