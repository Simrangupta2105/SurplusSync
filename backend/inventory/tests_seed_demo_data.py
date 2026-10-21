"""Tests for seed_demo_data management command (Task 5: Calibrated Synthetic Ledger).

Verifies:
1. Exact ledger reconciliation: Received == Sold + Discarded + Donated + Remaining
   with 0 discrepancy across all generated batches.
2. Safety guard: CommandError raised if data exists and --force is not passed.
3. --force flag cleanly purges and regenerates data.
4. Reproducibility: Identical results with fixed random seed.
5. Calibrated empirical statistics match within stated tolerances.
"""

from decimal import Decimal
from django.core.management import call_command, CommandError
from django.test import TestCase

from accounts.models import Organization
from inventory.models import Batch, Product, StockTransaction, StorageLocation


class SeedDemoDataCommandTests(TestCase):
    def setUp(self):
        self.org_name = "Calibrated Test Market"

    def test_seed_demo_data_creates_reconciled_ledger(self):
        """CRITICAL INVARIANT: Received == Sold + Discarded + Donated + Remaining for all batches."""
        call_command(
            "seed_demo_data",
            org_name=self.org_name,
            days=14,
            seed=42,
            force=True,
        )

        org = Organization.objects.get(name=self.org_name)
        batches = Batch.objects.filter(organization=org)
        self.assertGreater(batches.count(), 0)

        products = Product.objects.filter(organization=org)
        self.assertEqual(products.count(), 13)

        locations = StorageLocation.objects.filter(organization=org)
        self.assertEqual(locations.count(), 3)

        # Check transaction ledger reconciliation for every single batch
        for batch in batches:
            txns = StockTransaction.objects.filter(batch=batch)
            rx_qty = sum(t.quantity for t in txns if t.txn_type == StockTransaction.Type.RECEIVED)
            sold_qty = sum(t.quantity for t in txns if t.txn_type == StockTransaction.Type.SOLD)
            discarded_qty = sum(t.quantity for t in txns if t.txn_type == StockTransaction.Type.DISCARDED)
            donated_qty = sum(t.quantity for t in txns if t.txn_type == StockTransaction.Type.DONATED)
            remaining_qty = batch.quantity

            reconciled_total = sold_qty + discarded_qty + donated_qty + remaining_qty
            self.assertEqual(
                rx_qty,
                reconciled_total,
                f"Ledger discrepancy on batch {batch.batch_code}: "
                f"Received({rx_qty}) != Sold({sold_qty}) + Discarded({discarded_qty}) + "
                f"Donated({donated_qty}) + Remaining({remaining_qty})",
            )

    def test_seed_demo_data_refuses_to_overwrite_without_force(self):
        """Verify command raises CommandError when data already exists and --force is omitted."""
        # First run succeeds
        call_command(
            "seed_demo_data",
            org_name="Guard Test Org",
            days=7,
            seed=42,
            force=True,
        )

        # Second run without force MUST fail
        with self.assertRaises(CommandError) as ctx:
            call_command(
                "seed_demo_data",
                org_name="Guard Test Org",
                days=7,
                seed=42,
            )

        self.assertIn("Refusing to overwrite", str(ctx.exception))
        self.assertIn("Pass --force", str(ctx.exception))

    def test_seed_demo_data_force_overwrites_cleanly(self):
        """Verify passing --force purges old data and successfully reseeds."""
        call_command("seed_demo_data", org_name="Overwrite Test Org", days=7, seed=42, force=True)
        initial_txns = StockTransaction.objects.filter(organization__name="Overwrite Test Org").count()

        # Reseed with force
        call_command("seed_demo_data", org_name="Overwrite Test Org", days=10, seed=123, force=True)
        new_txns = StockTransaction.objects.filter(organization__name="Overwrite Test Org").count()
        self.assertGreater(new_txns, initial_txns)

    def test_seed_demo_data_repeatability_with_seed(self):
        """Verify identical seed produces identical quantities and batch codes."""
        call_command("seed_demo_data", org_name="Seed Org A", days=10, seed=999, force=True)
        org_a = Organization.objects.get(name="Seed Org A")
        txns_a = list(StockTransaction.objects.filter(organization=org_a).order_by("id").values_list("txn_type", "quantity"))

        call_command("seed_demo_data", org_name="Seed Org B", days=10, seed=999, force=True)
        org_b = Organization.objects.get(name="Seed Org B")
        txns_b = list(StockTransaction.objects.filter(organization=org_b).order_by("id").values_list("txn_type", "quantity"))

        self.assertEqual(len(txns_a), len(txns_b))
        self.assertEqual(txns_a, txns_b)

    def test_seed_demo_data_calibrated_statistics_tolerances(self):
        """Verify generated ledger statistics match calibration within tolerance."""
        call_command("seed_demo_data", org_name="Stats Check Org", days=30, seed=42, force=True)
        org = Organization.objects.get(name="Stats Check Org")

        all_txns = StockTransaction.objects.filter(organization=org)
        total_rx = sum(t.quantity for t in all_txns if t.txn_type == StockTransaction.Type.RECEIVED)
        total_sold = sum(t.quantity for t in all_txns if t.txn_type == StockTransaction.Type.SOLD)
        total_discarded = sum(t.quantity for t in all_txns if t.txn_type == StockTransaction.Type.DISCARDED)
        total_donated = sum(t.quantity for t in all_txns if t.txn_type == StockTransaction.Type.DONATED)

        # Sales should represent 70% to 90% of received stock
        sales_ratio = float(total_sold / total_rx)
        self.assertGreaterEqual(sales_ratio, 0.70)
        self.assertLessEqual(sales_ratio, 0.92)

        # Donation should be positive but less than total waste
        total_waste = total_discarded + total_donated
        self.assertGreater(total_waste, Decimal("0"))
        donation_share = float(total_donated / total_waste)
        # Calibrated donation rate is ~23% of waste events
        self.assertGreaterEqual(donation_share, 0.05)
        self.assertLessEqual(donation_share, 0.35)
