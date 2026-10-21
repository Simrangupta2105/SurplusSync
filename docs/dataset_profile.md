# Food Waste Dataset Profile & Data Card

## 1. Overview & Dataset Shape

The raw dataset (`ml_service/data/raw/food_waste_dataset.csv`) contains daily operational records spanning multiple retail and food-service business categories.

- **Total Records (Rows):** 8,000
- **Total Features (Columns):** 16
- **Date Range:** 2025-01-01 to 2025-12-31 (365 distinct calendar days, exactly one year)
- **Granularity:** Independent daily snapshot observations (no continuous shop/store identifier)

### Feature Schema

| Column Name | Schema Data Type | Non-Null Count | Missing Count | Missing Pct | Description |
|:---|:---|---:|---:|---:|:---|
| `Inventory_ID` | String (Identifier) | 8,000 | 0 | 0.00% | Unique record identifier (e.g. `INV000001` to `INV008000`) |
| `Date` | Date (`YYYY-MM-DD`) | 8,000 | 0 | 0.00% | Observation date spanning 2025-01-01 through 2025-12-31 |
| `Business_Type` | Categorical (4 levels) | 8,000 | 0 | 0.00% | `Restaurant`, `Supermarket`, `Cafeteria`, `Cloud Kitchen` |
| `Food_Category` | Categorical (6 levels) | 8,000 | 0 | 0.00% | `Bakery`, `Dairy`, `Fruits`, `Meat`, `Prepared Food`, `Vegetables` |
| `Purchase_Quantity` | Integer | 8,000 | 0 | 0.00% | Total units stocked/purchased for the day |
| `Units_Sold` | Integer | 8,000 | 0 | 0.00% | Total units sold during the day |
| `Remaining_Stock` | Integer | 8,000 | 0 | 0.00% | Stock remaining after sales |
| `Shelf_Life_Days` | Float (Integer-valued) | 7,765 | 235 | 2.94% | Nominal batch shelf-life in days |
| `Storage_Temperature`| Float (°C) | 7,814 | 186 | 2.33% | Storage temperature in degrees Celsius |
| `Daily_Demand` | Float (Integer-valued) | 7,790 | 210 | 2.62% | True customer demand for the day |
| `Promotion` | Binary (`Yes`/`No`) | 8,000 | 0 | 0.00% | Whether a discount/promotion was active |
| `Weather` | Categorical (4 levels) | 7,797 | 203 | 2.54% | `Sunny`, `Rainy`, `Cloudy`, `Hot` |
| `Waste_Quantity` | Integer | 8,000 | 0 | 0.00% | Number of units wasted from remaining stock |
| `Waste_Reason` | Categorical (5 levels) | 8,000 | 0 | 0.00% | Cause of waste: `Expired`, `Overproduction`, `Low Demand`, `Storage Issue`, `No Waste` |
| `Donation_Made` | Binary (`Yes`/`No`) | 7,767 | 233 | 2.91% | Whether surplus/waste was donated |
| `Waste_Level` | Categorical (Target) | 8,000 | 0 | 0.00% | Severity label: `Low`, `Medium`, `High` |

---

## 2. Temporal & Sampling Distribution

### Rows Per Day
- **Minimum:** 9 rows/day
- **Maximum:** 38 rows/day
- **Mean:** 21.92 rows/day
- **Median:** 22 rows/day
- **Standard Deviation:** 4.70 rows/day

### Distribution by Business Type
| Business Type | Record Count | Proportion |
|:---|---:|---:|
| Restaurant | 2,455 | 30.69% |
| Supermarket | 2,404 | 30.05% |
| Cafeteria | 1,572 | 19.65% |
| Cloud Kitchen | 1,569 | 19.61% |
| **Total** | **8,000** | **100.00%** |

### Distribution by Food Category
| Food Category | Record Count | Proportion |
|:---|---:|---:|
| Prepared Food | 1,479 | 18.49% |
| Fruits | 1,431 | 17.89% |
| Vegetables | 1,429 | 17.86% |
| Meat | 1,252 | 15.65% |
| Bakery | 1,247 | 15.59% |
| Dairy | 1,162 | 14.52% |
| **Total** | **8,000** | **100.00%** |

### Rows per Business Type × Category × Day
Across the theoretical grid of $4 \times 6 \times 365 = 8,760$ combinations:
- **Observed non-empty combinations:** 5,139 (58.66% coverage)
- **Mean records per active cell:** 1.56
- **Breakdown of cell sizes:**
  - 1 record: 3,061 days (59.56%)
  - 2 records: 1,479 days (28.78%)
  - 3 records: 454 days (8.83%)
  - 4 records: 113 days (2.20%)
  - 5 records: 25 days (0.49%)
  - 6 records: 7 days (0.14%)

---

## 3. Demand Profiling & Drivers

Demand is heavily structured by **Business Type**, **Promotions**, and **Weather Conditions**.

### Demand by Business Type
| Business Type | Count (non-null) | Mean Demand | Std Dev | Median | Min | Max |
|:---|---:|---:|---:|---:|---:|---:|
| Supermarket | 2,335 | 156.10 | 38.69 | 153.00 | 63.00 | 316.00 |
| Cloud Kitchen | 1,520 | 103.58 | 25.56 | 102.00 | 45.00 | 214.00 |
| Restaurant | 2,403 | 83.43 | 21.13 | 81.00 | 37.00 | 193.00 |
| Cafeteria | 1,532 | 62.86 | 15.93 | 61.00 | 26.00 | 131.00 |

### Demand by Promotion
| Promotion Active | Count | Mean Demand | Std Dev | Median | Lift vs No-Promo |
|:---|---:|---:|---:|---:|---:|
| No | 6,280 | 98.77 | 40.50 | 89.00 | Baseline |
| Yes | 1,510 | 131.42 | 53.31 | 119.00 | **+33.05%** |

### Demand by Weather Condition
| Weather | Count | Mean Demand | Std Dev | Median | Relative Effect |
|:---|---:|---:|---:|---:|:---|
| Hot | 1,556 | 119.25 | 47.99 | 106.00 | +3.85% vs Sunny |
| Sunny | 2,629 | 114.83 | 45.55 | 103.00 | Baseline |
| Missing | 196 | 107.51 | 48.87 | 95.00 | Near overall mean |
| Cloudy | 1,891 | 102.44 | 40.67 | 91.00 | -10.79% vs Sunny |
| Rainy | 1,518 | 76.74 | 31.07 | 69.00 | **-33.17% vs Sunny** |

---

## 4. Time Series Autocorrelation Diagnostics

Category-level daily time series were evaluated for temporal dependency. Because daily row counts fluctuate between 9 and 38 per day, series were evaluated using both:
1. **Daily Mean Demand per record** (missing days imputed with category global mean)
2. **Daily Aggregated Sum Demand**

### Autocorrelation Function (ACF) by Category

| Category | Missing Days (Mean Series) | Lag-1 ACF | Lag-7 ACF | Lag-14 ACF | Lag-28 ACF |
|:---|---:|---:|---:|---:|---:|
| **Bakery** | 9 | +0.0472 | -0.0621 | +0.0873 | -0.0332 |
| **Dairy** | 10 | -0.0422 | -0.0350 | -0.0542 | -0.0228 |
| **Fruits** | 6 | -0.1498 | +0.0685 | -0.0724 | -0.0006 |
| **Meat** | 12 | +0.0853 | -0.0443 | -0.0397 | -0.0709 |
| **Prepared Food** | 11 | +0.0473 | -0.0410 | -0.0113 | -0.0069 |
| **Vegetables** | 4 | -0.0185 | -0.0463 | +0.0481 | +0.0790 |

### Aggregated Sum Daily Series ACF

| Category | Lag-1 ACF | Lag-7 ACF | Lag-14 ACF | Lag-28 ACF |
|:---|---:|---:|---:|---:|
| **Bakery** | +0.0223 | -0.0156 | +0.0449 | -0.0089 |
| **Dairy** | +0.0129 | -0.0098 | +0.1042 | -0.0282 |
| **Fruits** | -0.0621 | +0.0997 | +0.0207 | +0.0523 |
| **Meat** | +0.0823 | -0.0978 | +0.0402 | +0.0535 |
| **Prepared Food** | +0.0018 | +0.0092 | -0.0751 | +0.0176 |
| **Vegetables** | +0.0806 | +0.0357 | +0.0359 | -0.0410 |

> **Diagnostic Insight:** Across all categories and lags, autocorrelation is practically zero ($|r| \le 0.15$). This proves empirically that the dataset does not possess persistent autoregressive time-series structure. Variations are generated from cross-sectional features (`Business_Type`, `Promotion`, `Weather`) rather than temporal momentum.

---

## 5. Waste & Loss Breakdown

### Aggregate Units & Waste Ratio by Category
Across all 8,000 records:
- **Total Purchase Quantity:** 946,310 units
- **Total Units Sold:** 775,677 units
- **Total Remaining Stock:** 170,633 units
- **Total Waste Quantity:** 46,179 units
- **Overall Waste / Purchase Ratio:** **4.88%**
- **Overall Waste / Remaining Stock Ratio:** **27.06%**

| Food Category | Purchase Units | Sold Units | Remaining Units | Waste Units | Waste / Purchase | Waste / Remaining |
|:---|---:|---:|---:|---:|---:|---:|
| Prepared Food | 175,514 | 141,030 | 34,484 | 13,362 | **7.61%** | 38.75% |
| Bakery | 145,988 | 120,944 | 25,044 | 7,055 | **4.83%** | 28.17% |
| Meat | 148,185 | 121,920 | 26,265 | 6,654 | **4.49%** | 25.33% |
| Fruits | 169,050 | 139,350 | 29,700 | 7,123 | **4.21%** | 23.98% |
| Vegetables | 168,969 | 138,904 | 30,065 | 6,684 | **3.96%** | 22.23% |
| Dairy | 138,604 | 113,529 | 25,075 | 5,301 | **3.82%** | 21.14% |

### Waste Reason Mix

| Food Category | Expired | Low Demand | No Waste | Overproduction | Storage Issue | Total |
|:---|---:|---:|---:|---:|---:|---:|
| **Bakery** | 249 (20.0%) | 176 (14.1%) | 519 (41.6%) | 231 (18.5%) | 72 (5.8%) | 1,247 |
| **Dairy** | 91 (7.8%) | 242 (20.8%) | 524 (45.1%) | 280 (24.1%) | 25 (2.2%) | 1,162 |
| **Fruits** | 144 (10.1%) | 293 (20.5%) | 622 (43.5%) | 314 (21.9%) | 58 (4.1%) | 1,431 |
| **Meat** | 211 (16.9%) | 212 (16.9%) | 554 (44.2%) | 253 (20.2%) | 22 (1.8%) | 1,252 |
| **Prepared Food** | 600 (40.6%) | 77 (5.2%) | 563 (38.1%) | 160 (10.8%) | 79 (5.3%) | 1,479 |
| **Vegetables** | 116 (8.1%) | 295 (20.6%) | 633 (44.3%) | 312 (21.8%) | 73 (5.1%) | 1,429 |
| **Overall Total** | **1,411 (17.64%)** | **1,295 (16.19%)** | **3,415 (42.69%)** | **1,550 (19.38%)** | **329 (4.11%)** | **8,000** |

---

## 6. Donation Distribution

- **Total Records:** 8,000
- **`Donation_Made` = No:** 6,711 (83.89%)
- **`Donation_Made` = Yes:** 1,056 (13.20%)
- **`Donation_Made` = Missing:** 233 (2.91%)

### Conditional Donation Rates
- **When `Waste_Quantity > 0` (4,585 rows):**
  - `Donation_Made = Yes`: 1,056 rows (**23.03%** of all waste rows; **23.74%** of non-missing)
  - `Donation_Made = No`: 3,392 rows (73.98%)
  - `Donation_Made = Missing`: 137 rows (2.99%)
- **When `Waste_Quantity == 0` (3,415 rows):**
  - `Donation_Made = Yes`: **0 rows (0.00%)**
  - `Donation_Made = No`: 3,319 rows (97.19%)
  - `Donation_Made = Missing`: 96 rows (2.81%)

> **Invariant Check:** Food is donated **only** when waste has occurred (`Waste_Quantity > 0`). When waste is zero, donation is strictly 0%.

---

## 7. Target Distribution: `Waste_Level`

| Waste_Level | Frequency | Percentage |
|:---|---:|---:|
| **Low** | 4,331 | 54.14% |
| **Medium** | 2,397 | 29.96% |
| **High** | 1,272 | 15.90% |
| **Total** | **8,000** | **100.00%** |

---

## 8. Verified Data Invariants

Five structural accounting invariants were evaluated and verified across all 8,000 records:

1. **`Remaining_Stock == Purchase_Quantity - Units_Sold`**
   - Result: **0 violations** (100% compliant, 8,000/8,000).
2. **`Waste_Quantity <= Remaining_Stock`**
   - Result: **0 violations** (100% compliant, 8,000/8,000).
3. **`Units_Sold <= Purchase_Quantity`**
   - Result: **0 violations** (100% compliant, 8,000/8,000).
4. **`Units_Sold == min(Purchase_Quantity, Daily_Demand)` (where Daily_Demand is present)**
   - Evaluated across all 7,790 records with known demand.
   - Result: **0 violations** (100% compliant, 7,790/7,790).
5. **`Donation_Made == 'Yes' only when Waste_Quantity > 0`**
   - Evaluated across all 8,000 records.
   - Result: **0 violations** (100% compliant; zero donations when waste is zero).

---

## 9. Dataset Card & Provenance

### Provenance Placeholder
- **Source & Origin:** External benchmarking dataset provided for SurplusSync Module 2 foundation calibration.
- **Licence:** **TO BE CONFIRMED** (Raw CSV files are explicitly added to `.gitignore` to prevent licensing exposure).
- **Collection Methodology:** Synthetically generated microdata benchmark simulating retail and food service operations.

### Data Nature & Synthetic Indications
- Deterministic relationship $Sold = \min(Purchase, Demand)$ holds with mathematical exactness ($0$ noise).
- Mass balance $Remaining = Purchase - Sold$ is exact.
- Demand distributions exhibit exact multiplicative segments ($Supermarket > Cloud Kitchen > Restaurant > Cafeteria$) with fixed weather multipliers and promotion lift (+33%).
- Missingness is artificially injected at ~2.3% to ~2.9% across specific columns (`Shelf_Life_Days`, `Storage_Temperature`, `Daily_Demand`, `Weather`, `Donation_Made`).

### Limitations
1. **Independent Daily Snapshots:** The dataset lacks a persistent enterprise/store identifier (no store-level time series or repeated measures on the same outlet).
2. **No Batch or Expiry Tracking:** Records capture single-day aggregates rather than inventory lots with distinct shelf life depletion or FEFO lot allocation.
3. **No Financial Cost / Price:** Unit cost, wholesale purchase price, and retail sales price are absent (value-at-risk must rely on SurplusSync's native ledger).
4. **No Spatial / Geographic Coordinates:** Weather conditions are categorical; no latitude/longitude or regional weather station links.
5. **Single Year Horizon:** Exactly 365 calendar days (2025-01-01 to 2025-12-31), preventing multi-year trend or cycle decomposition.
