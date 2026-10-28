"""Tests for Task 7: Demo Ledger Management Command from Synthetic Panel (Track B).

Verifies:
1. Exact ledger reconciliation: Received == Sold + Discarded + Donated + Adjusted + Remaining.
2. Idempotency guard: Refuses to overwrite existing transactions/batches without --force.
3. Overwrite with --force: Properly cleans and reseeds without duplication.
4. Batch lifecycle & status: Old batches (> 14 days) closed with ADJUSTMENT; recent batches stay ACTIVE.
5. Organization coordinates: Lat/Long set from shop in panel, and marked with [DEMO DATA - SYNTHETIC PANEL].
6. Tenant isolation: Seeding target organization never affects or touches other organizations.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounts.models import Organization
from inventory.models import Batch, Category, Product, StockTransaction, StorageLocation


class PanelSeedingCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.panel_path = "ml_service/data/raw/synthetic_panel_full.csv"

    def test_seed_from_panel_reconciliation_and_accounting(self):
        """Verify that every batch created from the panel strictly reconciles to zero discrepancy."""
        org_name = "Synthetic Panel Supermarket S01"
        call_command(
            "seed_demo_data",
            from_panel=self.panel_path,
            org=org_name,
            shops="S01",
            last_days=30,
            force=True,
        )

        org = Organization.objects.get(name=org_name)
        batches = Batch.objects.filter(organization=org)
        self.assertGreater(batches.count(), 0)

        total_received = Decimal("0")
        total_accounted = Decimal("0")

        for b in batches:
            txns = b.transactions.all()
            received = sum((t.quantity for t in txns if t.txn_type == StockTransaction.Type.RECEIVED), Decimal("0"))
            sold = sum((t.quantity for t in txns if t.txn_type == StockTransaction.Type.SOLD), Decimal("0"))
            discarded = sum((t.quantity for t in txns if t.txn_type == StockTransaction.Type.DISCARDED), Decimal("0"))
            donated = sum((t.quantity for t in txns if t.txn_type == StockTransaction.Type.DONATED), Decimal("0"))
            adjusted = sum((t.quantity for t in txns if t.txn_type == StockTransaction.Type.ADJUSTMENT), Decimal("0"))
            remaining = b.quantity

            accounted = sold + discarded + donated + adjusted + remaining

            self.assertEqual(
                received,
                accounted,
                f"Reconciliation error on batch {b.batch_code}: Received {received} != Accounted {accounted}",
            )

            total_received += received
            total_accounted += accounted

        self.assertEqual(total_received, total_accounted)

    def test_idempotency_refusal_without_force(self):
        """Verify command refuses to overwrite an organization with existing data unless --force is passed."""
        org_name = "Guard Test Org S01"
        call_command(
            "seed_demo_data",
            from_panel=self.panel_path,
            org=org_name,
            shops="S01",
            last_days=10,
            force=True,
        )

        # Attempt to run again without --force
        with self.assertRaises(CommandError) as ctx:
            call_command(
                "seed_demo_data",
                from_panel=self.panel_path,
                org=org_name,
                shops="S01",
                last_days=10,
            )

        self.assertIn("already has existing inventory data", str(ctx.exception))
        self.assertIn("Refusing to overwrite without --force", str(ctx.exception))

    def test_idempotency_with_force_cleans_and_reseeds(self):
        """Verify that passing --force cleanly purges prior batches and avoids duplication."""
        org_name = "Overwrite Org S01"
        call_command(
            "seed_demo_data",
            from_panel=self.panel_path,
            org=org_name,
            shops="S01",
            last_days=14,
            force=True,
        )
        org = Organization.objects.get(name=org_name)
        count_first_run = Batch.objects.filter(organization=org).count()

        # Reseed with --force
        call_command(
            "seed_demo_data",
            from_panel=self.panel_path,
            org=org_name,
            shops="S01",
            last_days=14,
            force=True,
        )
        count_second_run = Batch.objects.filter(organization=org).count()
        self.assertEqual(count_first_run, count_second_run)

    def test_batch_lifecycle_and_carried_forward_adjustment(self):
        """Verify old batches are closed with ADJUSTMENT while recent batches retain carried-forward quantity."""
        org_name = "Lifecycle Org S01"
        call_command(
            "seed_demo_data",
            from_panel=self.panel_path,
            org=org_name,
            shops="S01",
            last_days=45,
            force=True,
        )
        org = Organization.objects.get(name=org_name)

        # Find latest batch date
        latest_batch = Batch.objects.filter(organization=org).order_by("-received_date").first()
        recent_cutoff = latest_batch.received_date - timedelta(days=14)

        # Check old batches (expiry < recent_cutoff)
        old_batches = Batch.objects.filter(organization=org, expiry_date__lt=recent_cutoff)
        self.assertGreater(old_batches.count(), 0)
        for ob in old_batches:
            self.assertEqual(ob.quantity, Decimal("0.000"))
            self.assertIn(ob.status, [Batch.Status.EXPIRED, Batch.Status.DEPLETED])

        # Check recent batches
        recent_batches = Batch.objects.filter(organization=org, expiry_date__gte=recent_cutoff)
        self.assertGreater(recent_batches.count(), 0)
        has_active_with_qty = any(rb.status == Batch.Status.ACTIVE and rb.quantity > 0 for rb in recent_batches)
        self.assertTrue(has_active_with_qty)

    def test_organization_coordinates_and_demo_badge(self):
        """Verify organization latitude, longitude, and demo badge metadata match the panel shop."""
        org_name = "Geo Org S01"
        call_command(
            "seed_demo_data",
            from_panel=self.panel_path,
            org=org_name,
            shops="S01",
            last_days=7,
            force=True,
        )
        org = Organization.objects.get(name=org_name)
        # Shop S01 latitude and longitude in synthetic panel (Bhopal coordinates)
        self.assertIsNotNone(org.latitude)
        self.assertIsNotNone(org.longitude)
        self.assertAlmostEqual(float(org.latitude), 23.28811, places=3)
        self.assertAlmostEqual(float(org.longitude), 77.40077, places=3)

        # Verify demo metadata
        self.assertIn("[DEMO DATA - SYNTHETIC PANEL]", org.verification_note)
        self.assertEqual(org.verification_status, Organization.VerificationStatus.VERIFIED)

    def test_tenant_isolation(self):
        """Verify seeding organization A does not affect or alter organization B."""
        # Create control organization B with existing inventory
        org_b = Organization.objects.create(
            name="Control Org B",
            org_type=Organization.Type.BUSINESS,
        )
        cat = Category.objects.create(name="Dry Goods")
        prod_b = Product.objects.create(
            organization=org_b,
            name="Control Product",
            sku="SKU-CTRL-001",
            category=cat,
        )
        batch_b = Batch.objects.create(
            organization=org_b,
            product=prod_b,
            batch_code="B-CTRL-001",
            quantity=Decimal("150.000"),
            received_date=date(2025, 1, 1),
            expiry_date=date(2025, 12, 31),
            status=Batch.Status.ACTIVE,
        )
        StockTransaction.objects.create(
            organization=org_b,
            batch=batch_b,
            txn_type=StockTransaction.Type.RECEIVED,
            quantity=Decimal("150.000"),
        )

        # Seed organization A with --force
        call_command(
            "seed_demo_data",
            from_panel=self.panel_path,
            org="Isolated Org A",
            shops="S01",
            last_days=14,
            force=True,
        )

        # Verify Org B remains completely untouched
        self.assertEqual(Batch.objects.filter(organization=org_b).count(), 1)
        self.assertEqual(StockTransaction.objects.filter(organization=org_b).count(), 1)
        batch_b.refresh_from_db()
        self.assertEqual(batch_b.quantity, Decimal("150.000"))
