# Operational Assumptions and Accounting Rules for Synthetic Panel Ledger `[SYNTHETIC DATA]`

This document records the exact operational assumptions, accounting ledger mapping rules, and mathematical invariants used to translate `synthetic_panel_full.csv` into SurplusSync's double-entry inventory ledger (`seed_demo_data --from-panel`).

---

## 1. Carried-Forward Inventory & Batch Closure Assumption

In daily retail inventory management, excess stock remaining after customer sales (`Daily_Demand`) and discards/donations (`Waste_Quantity`) carries forward to subsequent calendar days (`Carried_Forward_Units`).

### Challenge:
The synthetic panel is generated as daily accounting slices. While each row records `Carried_Forward_Units`, the CSV does not track individual physical inventory barcodes across multi-day lifecycles.

### Operational Resolution Rule:
1. **Recent and Future Batches (Active Window: within 14 days of panel conclusion)**:
   - For batches whose `Expiry_Date` is within 14 days of the latest panel date (`Date >= 2025-12-17`), the batch remains **`ACTIVE`** with current stock on shelf equal to `Carried_Forward_Units`:
     $$\text{Batch.quantity} = \text{Carried\_Forward\_Units}$$
     $$\text{Batch.status} = \begin{cases} \text{ACTIVE} & \text{if } \text{quantity} > 0 \\ \text{DEPLETED} & \text{otherwise} \end{cases}$$
2. **Historical Closed Batches (> 14 days before panel conclusion)**:
   - For historical batches whose shelf-life expired well before the current operations period, the inventory cycle has concluded.
   - To reconcile the accounting ledger without fictitious remaining stock on shelf, an **`ADJUSTMENT`** transaction is posted for the carried-forward units:
     $$\text{Transaction.Type} = \text{ADJUSTMENT}$$
     $$\text{Transaction.quantity} = \text{Carried\_Forward\_Units}$$
     $$\text{Transaction.reason} = \text{"carried forward, not tracked in synthetic data"}$$
     $$\text{Batch.quantity} = 0.000$$
     $$\text{Batch.status} = \begin{cases} \text{EXPIRED} & \text{if } \text{Expiry\_Date} < \text{last\_panel\_date} \\ \text{DEPLETED} & \text{otherwise} \end{cases}$$

---

## 2. Ledger Reconciliation Invariant

Every batch created from a panel row strictly obeys double-entry conservation of mass:

$$\text{Received} = \text{Sold} + \text{Discarded} + \text{Donated} + \text{Adjusted} + \text{Remaining}$$

Where:
- $\text{Received} = \text{Purchase\_Quantity}$ (`StockTransaction.Type.RECEIVED`)
- $\text{Sold} = \text{Units\_Sold}$ (`StockTransaction.Type.SOLD`)
- $\text{Donated} = \text{Donated\_Units}$ (`StockTransaction.Type.DONATED`)
- $\text{Discarded} = \text{Waste\_Quantity} - \text{Donated\_Units}$ (`StockTransaction.Type.DISCARDED`)
- $\text{Adjusted} = \begin{cases} \text{Carried\_Forward\_Units} & \text{if batch expired} > 14 \text{ days ago} \\ 0 & \text{otherwise} \end{cases}$ (`StockTransaction.Type.ADJUSTMENT`)
- $\text{Remaining} = \begin{cases} \text{Carried\_Forward\_Units} & \text{if batch within active 14-day window} \\ 0 & \text{otherwise} \end{cases}$ (`Batch.quantity`)

From dataset Invariant 3:
$$\text{Purchase\_Quantity} \equiv \text{Units\_Sold} + \text{Waste\_Quantity} + \text{Carried\_Forward\_Units}$$
And Invariant 6:
$$\text{Waste\_Quantity} \equiv \text{Discarded\_Units} + \text{Donated\_Units}$$

Therefore, mathematical reconciliation is guaranteed with $0.000$ discrepancy across all seeded rows.

---

## 3. Geographic Coordinates and Organization Metadata

1. **Latitude and Longitude**:
   - Organization coordinates are assigned directly from the shop's empirical `Latitude` and `Longitude` columns in the panel CSV (e.g. Shop S01 in central Bengaluru).
   - This ensures the matching engine, route optimization, and distance calculations use genuine physical coordinates.
2. **Demo Data Identification**:
   - The organization's `verification_note` is marked with:
     `[DEMO DATA - SYNTHETIC PANEL] Seeded from synthetic_panel_full.csv (Shop: S01)`
   - The UI surfaces the standard **Demo Data** badge to clearly identify the organization to users.
3. **Tenant Isolation**:
   - The management command operates strictly within the specified `--org`.
   - Never touches or alters inventory, batches, or transactions of other organizations.
   - Idempotency guard: refuses to overwrite an organization with existing data unless `--force` is explicitly provided.
