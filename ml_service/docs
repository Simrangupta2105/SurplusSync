# Synthetic Food-Waste Panel Data Profile & Verification Report

> **STATUS: SYNTHETIC DEMONSTRATION DATA (synthetic_v1)**
> Every value in `synthetic_panel_full.csv` and `synthetic_panel_core16.csv` was generated synthetically (seed 42).
> Nothing in this dataset was observed in a real business. It is designed to provide learnable time structure
> (day-of-week, seasonal, weather, promotional, and festival patterns) for Time-series Track B while maintaining
> calibration with the benchmark dataset (`food_waste_dataset.csv`). Wins on this dataset demonstrate pipeline
> correctness and feature engineering validity, not real-world forecasting accuracy.

## 1. Structural Checks & Invariant Verification

| Structural Check | Expected | Actual | Status |
|:---|---:|---:|:---|
| Total Rows | 52,608 | 52,608 | PASS |
| Continuous Time Series (Shops x Categories) | 48 (8 x 6) | 48 | PASS |
| Calendar Days per Series | 1,096 | 1,096 | PASS |
| Date Range | 2023-01-01 to 2025-12-31 | 2023-01-01 to 2025-12-31 | PASS |
| Duplicate (Date, Shop_ID, Food_Category) | 0 | 0 | PASS |
| Missing Days in any of the 48 series | 0 | 0 | PASS |

### Row-wise Invariants Verification

| Invariant Property | Invariant Rule | Evaluated Rows | Result |
|:---|:---|---:|:---|
| Remaining Stock | `Remaining_Stock == Purchase_Quantity - Units_Sold` | 52,608 | PASS |
| Truncated Sales | `Units_Sold == min(Purchase_Quantity, Daily_Demand)` | 52,608 | PASS |
| Waste Bound | `Waste_Quantity <= Remaining_Stock` | 52,608 | PASS |
| Donation Quantity | `Donated_Units <= Waste_Quantity` | 52,608 | PASS |
| Donation Logic | `Donation_Made == "Yes"` only when `Waste_Quantity > 0` | 52,608 | PASS |
| Carried Forward | `Carried_Forward_Units == Remaining_Stock - Waste_Quantity` | 52,608 | PASS |
| Expiry Consistency | `Expiry_Date == Date + Shelf_Life_Days` | 52,608 | PASS |
| Quantity Positivity | Non-negative quantities (`Purchase`, `Sold`, `Demand`, `Waste`, `Remaining` >= 0) | 52,608 | PASS |
| Null Values (excl. Festival) | Zero missing / NaN values in any column | 52,608 | PASS |
| Blank Festival Mapping | Blank/missing Festival parsed as `"no festival"` | 52,608 | PASS |

---

## 2. Statistical Calibration vs. Benchmark Dataset

| Metric / Feature | Benchmark (`food_waste_dataset.csv`) | Synthetic Panel (`synthetic_v1`) | Absolute Difference | Relative Difference |
|:---|---:|---:|---:|---:|
| Mean Demand: Cafeteria | 62.860 | 62.933 | +0.072 | +0.12% |
| Mean Demand: Restaurant | 83.429 | 82.968 | -0.461 | -0.55% |
| Mean Demand: Cloud Kitchen | 103.578 | 104.313 | +0.735 | +0.71% |
| Mean Demand: Supermarket | 156.104 | 156.151 | +0.047 | +0.03% |
| Promotion Demand Lift Ratio | 1.331 | 1.331 | +0.001 | +0.06% |
| Promotion Row Share | 0.194 | 0.194 | -0.000 | -0.19% |
| Weather Demand Ratio vs. Sunny: Cloudy | 0.892 | 0.928 | +0.036 | +4.01% |
| Weather Demand Ratio vs. Sunny: Hot | 1.039 | 1.062 | +0.023 | +2.22% |
| Weather Demand Ratio vs. Sunny: Rainy | 0.668 | 0.680 | +0.012 | +1.78% |
| Weather Share: Sunny | 0.337 | 0.327 | -0.010 | -2.97% |
| Weather Share: Cloudy | 0.241 | 0.295 | +0.053 | +22.10% |
| Weather Share: Hot | 0.201 | 0.201 | +0.001 | +0.28% |
| Weather Share: Rainy | 0.196 | 0.177 | -0.019 | -9.46% |
| Waste / Purchase Rate: Bakery | 0.048 | 0.048 | +0.000 | +0.24% |
| Waste / Purchase Rate: Dairy | 0.038 | 0.038 | +0.000 | +0.49% |
| Waste / Purchase Rate: Fruits | 0.042 | 0.043 | +0.001 | +1.23% |
| Waste / Purchase Rate: Meat | 0.045 | 0.045 | +0.000 | +0.54% |
| Waste / Purchase Rate: Prepared Food | 0.076 | 0.076 | -0.000 | -0.16% |
| Waste / Purchase Rate: Vegetables | 0.040 | 0.040 | +0.001 | +2.37% |
| Mean Shelf Life (Days): Bakery | 3.081 | 3.121 | +0.040 | +1.31% |
| Mean Shelf Life (Days): Dairy | 6.881 | 6.949 | +0.068 | +0.98% |
| Mean Shelf Life (Days): Fruits | 5.097 | 5.091 | -0.006 | -0.11% |
| Mean Shelf Life (Days): Meat | 3.988 | 4.039 | +0.052 | +1.29% |
| Mean Shelf Life (Days): Prepared Food | 1.552 | 1.554 | +0.001 | +0.08% |
| Mean Shelf Life (Days): Vegetables | 5.945 | 5.916 | -0.029 | -0.48% |
| Mean Storage Temp (°C): Bakery | 21.987 | 21.965 | -0.021 | -0.10% |
| Mean Storage Temp (°C): Dairy | 3.893 | 3.933 | +0.041 | +1.04% |
| Mean Storage Temp (°C): Fruits | 7.898 | 7.876 | -0.021 | -0.27% |
| Mean Storage Temp (°C): Meat | 1.935 | 1.874 | -0.062 | -3.18% |
| Mean Storage Temp (°C): Prepared Food | 19.898 | 19.905 | +0.007 | +0.04% |
| Mean Storage Temp (°C): Vegetables | 5.934 | 5.793 | -0.142 | -2.39% |
| Positive Waste Share (`Waste > 0`) | 0.573 | 0.577 | +0.004 | +0.64% |
| Zero Remaining Share (`Remaining == 0`) | 0.374 | 0.375 | +0.000 | +0.06% |
| Over-Purchase Share (`Purchase > Demand`) | 0.624 | 0.625 | +0.002 | +0.29% |
| Stock-out Share (`Demand > Purchase`) | 0.364 | 0.361 | -0.003 | -0.69% |
| Over-Order Ratio (Mean `Purchase / Demand`) | 1.187 | 1.190 | +0.004 | +0.32% |
| Donation Share among Waste Rows | 0.230 | 0.227 | -0.003 | -1.29% |
| Waste_Level Share: Low | 0.541 | 0.531 | -0.010 | -1.84% |
| Waste_Level Share: Medium | 0.300 | 0.314 | +0.014 | +4.65% |
| Waste_Level Share: High | 0.159 | 0.155 | -0.004 | -2.48% |
| Waste Reason Share: Expired | 0.308 | 0.307 | -0.001 | -0.35% |
| Waste Reason Share: Low Demand | 0.282 | 0.279 | -0.003 | -1.20% |
| Waste Reason Share: Overproduction | 0.338 | 0.341 | +0.002 | +0.74% |
| Waste Reason Share: Storage Issue | 0.072 | 0.074 | +0.002 | +2.74% |

---

## 3. Learnable Time Structure

In contrast to the benchmark CSV where sequential records had zero autocorrelation (ACF lag 1 = -0.005, lag 7 = -0.005), the synthetic panel contains genuine, learnable time-series structure:

### Autocorrelation across the 48 Series
| Lag | Calendar Horizon | Mean Autocorrelation (ACF) | Standard Deviation | Min ACF | Max ACF | Benchmark CSV Daily Mean ACF |
|---:|:---|---:|---:|---:|---:|---:|
| 1 | Daily lag (persistence) | 0.359 | 0.054 | 0.207 | 0.491 | -0.005 |
| 7 | Weekly seasonal cycle | 0.431 | 0.128 | 0.169 | 0.648 | -0.005 |
| 14 | Bi-weekly seasonal cycle | 0.421 | 0.127 | 0.163 | 0.629 | N/A |
| 365 | Annual seasonal cycle | 0.146 | 0.051 | 0.043 | 0.258 | N/A |

### Day-of-Week Profile by Business Type
| Business Type | Monday Mean | Tuesday Mean | Wednesday Mean | Thursday Mean | Friday Mean | Saturday Mean | Sunday Mean | Weekday Min | Weekday Max | Max / Min Ratio |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Restaurant | 66.74 | 67.14 | 70.36 | 74.97 | 93.76 | 106.48 | 101.49 | 66.74 | 106.48 | 1.595 |
| Supermarket | 136.37 | 131.51 | 138.15 | 147.65 | 161.91 | 193.68 | 184.01 | 131.51 | 193.68 | 1.473 |
| Cafeteria | 75.33 | 77.55 | 76.84 | 75.90 | 68.70 | 36.60 | 29.56 | 29.56 | 77.55 | 2.624 |
| Cloud Kitchen | 91.81 | 92.55 | 96.33 | 100.87 | 111.31 | 122.08 | 115.38 | 91.81 | 122.08 | 1.330 |

---

## 4. Covariates and Feature Classification

| Column Name | Category | Status in Time-Series Models | Description |
|:---|:---|:---|:---|
| `Daily_Demand` | Target | **Forecasting Target** | True latent demand. Primary target for Track B models. |
| `Units_Sold` | Truncated Sales | **NEVER A TARGET (Leakage)** | `min(Purchase, Demand)`. Capped by purchase quantity. |
| `Purchase_Quantity` | Operational Decision | Input to Reorder / Waste Model | Units stocked on Date. Known at inventory placement time. |
| `Promotion` | Exogenous Covariate | **Known-in-Advance** | Marketing campaign active (0/1). |
| `Weather` | Exogenous Covariate | **Known-in-Advance** | Forecasted weather condition (`Sunny`, `Cloudy`, `Hot`, `Rainy`). |
| `Temperature_C` | Exogenous Covariate | **Known-in-Advance** | Ambient temperature forecast in °C. |
| `Rain_mm` | Exogenous Covariate | **Known-in-Advance** | Rainfall forecast in mm. |
| `Day_Of_Week` | Calendar | **Known-in-Advance** | Day of week index (0=Monday .. 6=Sunday). |
| `Is_Weekend` | Calendar | **Known-in-Advance** | Weekend indicator flag (Saturday or Sunday). |
| `Is_Holiday` | Calendar | **Known-in-Advance** | Gazetted holiday flag on the festival day itself. |
| `Festival` | Calendar | **Known-in-Advance** | Active festival window (`Republic Day`, `Holi`, `Eid al-Fitr`, etc., or `no festival`). |
| `Shelf_Life_Days` | Product Specification | **Known-in-Advance** | Nominal batch shelf-life in days. |
| `Lead_Time_Days` | Operational Parameter | **Known-in-Advance** | Supplier lead time in days. |
| `Unit_Cost_INR` | Economic Feature | **Known-in-Advance** | Purchase cost per unit in INR. |
| `Unit_Price_INR` | Economic Feature | **Known-in-Advance** | Retail selling price per unit in INR. |
| `Remaining_Stock` | Inventory Outcome | **Leakage for Demand** | `Purchase - Sold`. Realized only at end of day. |
| `Waste_Quantity` | Waste Outcome | **Leakage for Demand** | Spoiled units discarded/donated. Realized at end of day. |
| `Waste_Reason` | Waste Outcome | **Leakage for Demand** | Root cause for waste (`Expired`, `Overproduction`, etc.). |
| `Donation_Made` | Operational Outcome | **Leakage for Demand** | Binary flag if donation was completed. |
| `Donated_Units` | Operational Outcome | **Leakage for Demand** | Units redistributed to community/NGOs. |
| `Carried_Forward_Units` | Operational Outcome | **Leakage for Demand** | Remaining stock carried into next shelf-life window. |
| `Waste_Level` | Classification Target | **Target for Classifier (Task 6)** | `Low` (<0.015), `Medium` (0.015-0.085), `High` (>=0.085). |

---

## 5. Verification Disagreements and Discrepancies Report

As required by Task 0 specifications, every metric was independently recomputed from raw data.
Here is the verification comparison against `DATA_CARD.md` and `validation_report.md`:

1. **Invariants & Shape:**
   - Total rows (52,608), series count (48), distinct days (1,096), and all 8 row-wise invariants hold with 0 violations across 100% of rows. Exactly matches `validation_report.md`.

2. **Stock-out Share Precision:**
   - In `validation_report.md`, the benchmark stock-out share is reported as `0.364`. When computed across non-null demand rows (`d = bench.dropna(subset=["Daily_Demand"])`), the exact benchmark stock-out is `0.36367` (`0.364`), which matches the synthetic panel share of `0.361` (difference `-0.003`).
   - If evaluated naively across all 8,000 raw benchmark rows without dropping missing demand, the apparent ratio is `0.354`. The data card and validation report correctly used non-null demand evaluation.

3. **Weather Distribution:**
   - As flagged in `DATA_CARD.md`, cloudy days in the synthetic generator (`0.295`) have a slight positive offset (+0.053) relative to the benchmark CSV (`0.241`). This was documented in the original generator design notes and does not violate invariant logic.

4. **Festival Representation:**
   - Blank strings and nulls in the `Festival` column represent regular non-festival days and are explicitly normalized to `"no festival"` by `ml_service/data/synthetic_panel.py`.
