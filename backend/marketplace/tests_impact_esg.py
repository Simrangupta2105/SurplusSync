"""
backend/marketplace/tests_impact_esg.py
Comprehensive test suite for Task 3:
- Only COMPLETED donations count
- Date range filtering (30d, 90d, 12m, custom, all)
- Multiplier constants pulled from Django settings
- Server-side PDF export (ReportLab, tenant-scoped)
- Server-side CSV audit export (tenant-scoped)
- Public aggregate view (zeros shown honestly, 10-min cache)
- Activity heatmap matrix and geo-density points
"""
from datetime import timedelta, date
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Organization, User
from inventory.models import Category, Product, Batch
from marketplace.models import SurplusListing, DonationRequest


class ImpactAnalyticsESGTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.now = timezone.now()

        # Organizations
        self.donor_org = Organization.objects.create(
            name="Organic Harvest Co",
            org_type=Organization.Type.BUSINESS,
            address="10 Indiranagar, Bangalore",
            latitude=Decimal("12.9784"),
            longitude=Decimal("77.6408"),
        )
        self.donor_org_b = Organization.objects.create(
            name="Apex Food Hub",
            org_type=Organization.Type.BUSINESS,
            address="45 Whitefield, Bangalore",
            latitude=Decimal("12.9698"),
            longitude=Decimal("77.7500"),
        )
        self.ngo_org = Organization.objects.create(
            name="Food For All Shelter",
            org_type=Organization.Type.NGO,
            is_verified=True,
            address="20 Koramangala, Bangalore",
            latitude=Decimal("12.9352"),
            longitude=Decimal("77.6245"),
        )
        self.ngo_org_b = Organization.objects.create(
            name="Hope Mission NGO",
            org_type=Organization.Type.NGO,
            is_verified=True,
            address="15 Jayanagar, Bangalore",
            latitude=Decimal("12.9308"),
            longitude=Decimal("77.5838"),
        )

        # Users
        self.donor_user = User.objects.create_user(
            username="donor_esg",
            email="donor@esg.test",
            password="Password123!",
            organization=self.donor_org,
        )
        self.donor_b_user = User.objects.create_user(
            username="donor_b_esg",
            email="donorb@esg.test",
            password="Password123!",
            organization=self.donor_org_b,
        )
        self.ngo_user = User.objects.create_user(
            username="ngo_esg",
            email="ngo@esg.test",
            password="Password123!",
            organization=self.ngo_org,
        )
        self.admin_user = User.objects.create_user(
            username="platform_admin_esg",
            email="admin@esg.test",
            password="Password123!",
            is_staff=True,
        )

        # Category & Products
        self.cat_produce = Category.objects.create(name="Produce")
        self.cat_bakery = Category.objects.create(name="Bakery")

        self.prod_apples = Product.objects.create(
            organization=self.donor_org,
            name="Fresh Apples",
            category=self.cat_produce,
            sku="APP-001",
            unit="kg",
        )
        self.batch_apples = Batch.objects.create(
            organization=self.donor_org,
            product=self.prod_apples,
            batch_code="B-APP-01",
            quantity=Decimal("100.000"),
            received_date=self.now.date() - timedelta(days=5),
            expiry_date=self.now.date() + timedelta(days=2),
        )

        self.listing_apples = SurplusListing.objects.create(
            donor=self.donor_org,
            batch=self.batch_apples,
            title="Fresh Shimla Apples",
            category=self.cat_produce,
            quantity_offered=Decimal("50.000"),
            unit="kg",
            available_from=self.now - timedelta(days=5),
            available_until=self.now + timedelta(days=1),
            latitude=self.donor_org.latitude,
            longitude=self.donor_org.longitude,
        )

        self.prod_bread = Product.objects.create(
            organization=self.donor_org,
            name="Sourdough Loaves",
            category=self.cat_bakery,
            sku="BRD-001",
            unit="kg",
        )
        self.batch_bread = Batch.objects.create(
            organization=self.donor_org,
            product=self.prod_bread,
            batch_code="B-BRD-01",
            quantity=Decimal("80.000"),
            received_date=self.now.date() - timedelta(days=65),
            expiry_date=self.now.date() + timedelta(days=1),
        )
        self.listing_bread = SurplusListing.objects.create(
            donor=self.donor_org,
            batch=self.batch_bread,
            title="Artisan Sourdough",
            category=self.cat_bakery,
            quantity_offered=Decimal("30.000"),
            unit="kg",
            available_from=self.now - timedelta(days=60),
            available_until=self.now - timedelta(days=58),
            latitude=self.donor_org.latitude,
            longitude=self.donor_org.longitude,
        )

        # 1. COMPLETED Donation 10 days ago (40 kg apples)
        self.req_completed_recent = DonationRequest.objects.create(
            code="REQ-ESG-01",
            listing=self.listing_apples,
            ngo=self.ngo_org,
            quantity_requested=Decimal("40.000"),
            quantity_approved=Decimal("40.000"),
            quantity_collected=Decimal("40.000"),
            proposed_pickup_start=self.now - timedelta(days=10, hours=2),
            proposed_pickup_end=self.now - timedelta(days=10),
            status=DonationRequest.Status.COMPLETED,
            completed_at=self.now - timedelta(days=10),
        )

        # 2. COMPLETED Donation 45 days ago (20 kg sourdough)
        self.req_completed_older = DonationRequest.objects.create(
            code="REQ-ESG-02",
            listing=self.listing_bread,
            ngo=self.ngo_org,
            quantity_requested=Decimal("20.000"),
            quantity_approved=Decimal("20.000"),
            quantity_collected=Decimal("20.000"),
            proposed_pickup_start=self.now - timedelta(days=45, hours=2),
            proposed_pickup_end=self.now - timedelta(days=45),
            status=DonationRequest.Status.COMPLETED,
            completed_at=self.now - timedelta(days=45),
        )

        # 3. Active / In-Progress requests (Should NOT count in completed impact)
        self.req_requested = DonationRequest.objects.create(
            code="REQ-ESG-03",
            listing=self.listing_apples,
            ngo=self.ngo_org_b,
            quantity_requested=Decimal("15.000"),
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
            status=DonationRequest.Status.REQUESTED,
        )
        self.req_scheduled = DonationRequest.objects.create(
            code="REQ-ESG-04",
            listing=self.listing_apples,
            ngo=self.ngo_org,
            quantity_requested=Decimal("10.000"),
            quantity_approved=Decimal("10.000"),
            proposed_pickup_start=self.now + timedelta(hours=4),
            proposed_pickup_end=self.now + timedelta(hours=6),
            status=DonationRequest.Status.SCHEDULED,
        )
        self.req_cancelled = DonationRequest.objects.create(
            code="REQ-ESG-05",
            listing=self.listing_apples,
            ngo=self.ngo_org,
            quantity_requested=Decimal("5.000"),
            proposed_pickup_start=self.now - timedelta(days=2, hours=2),
            proposed_pickup_end=self.now - timedelta(days=2),
            status=DonationRequest.Status.CANCELLED,
        )

    def test_only_completed_donations_count_in_analytics(self):
        """Only requests in COMPLETED status count towards impact metrics."""
        self.client.force_authenticate(user=self.donor_user)
        res = self.client.get("/api/v1/marketplace/impact/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # 40 kg + 20 kg = 60 kg total
        self.assertEqual(res.data["total_donations_completed"], 2)
        self.assertEqual(res.data["total_quantity_donated_kg"], 60.0)
        # Meals: 60 / 0.42 = 142.85 -> 143
        self.assertEqual(res.data["meals_provided"], int(round(60.0 / 0.42)))
        # CO2e: 60 * 2.5 = 150.0
        self.assertEqual(res.data["co2_diverted_kg"], 150.0)

    def test_date_range_filtering_30d_and_90d(self):
        """Range parameter correctly scopes to 30d, 90d, or all."""
        self.client.force_authenticate(user=self.donor_user)

        # 30d: only the recent 40kg request completed 10 days ago
        res_30d = self.client.get("/api/v1/marketplace/impact/?range=30d")
        self.assertEqual(res_30d.status_code, status.HTTP_200_OK)
        self.assertEqual(res_30d.data["total_donations_completed"], 1)
        self.assertEqual(res_30d.data["total_quantity_donated_kg"], 40.0)
        self.assertEqual(res_30d.data["meals_provided"], int(round(40.0 / 0.42)))

        # 90d: includes both 10d and 45d requests
        res_90d = self.client.get("/api/v1/marketplace/impact/?range=90d")
        self.assertEqual(res_90d.status_code, status.HTTP_200_OK)
        self.assertEqual(res_90d.data["total_donations_completed"], 2)
        self.assertEqual(res_90d.data["total_quantity_donated_kg"], 60.0)

    def test_custom_date_range_filtering(self):
        """Custom range with start_date and end_date filters correctly."""
        self.client.force_authenticate(user=self.donor_user)

        d_from = (self.now - timedelta(days=20)).strftime("%Y-%m-%d")
        d_to = (self.now).strftime("%Y-%m-%d")
        res = self.client.get(f"/api/v1/marketplace/impact/?range=custom&start_date={d_from}&end_date={d_to}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_donations_completed"], 1)
        self.assertEqual(res.data["total_quantity_donated_kg"], 40.0)

    @override_settings(IMPACT_MEAL_KG_FACTOR=0.50, IMPACT_CO2E_KG_FACTOR=3.0)
    def test_constants_come_from_django_settings(self):
        """Multipliers honor settings.IMPACT_MEAL_KG_FACTOR and IMPACT_CO2E_KG_FACTOR."""
        self.client.force_authenticate(user=self.donor_user)
        res = self.client.get("/api/v1/marketplace/impact/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # 60 kg / 0.50 = 120 meals
        self.assertEqual(res.data["meals_provided"], 120)
        # 60 kg * 3.0 = 180.0 kg CO2e
        self.assertEqual(res.data["co2_diverted_kg"], 180.0)
        # Constants payload included
        consts = res.data.get("calculation_constants", {})
        self.assertEqual(consts.get("meal_kg_factor"), 0.50)
        self.assertEqual(consts.get("co2e_kg_factor"), 3.0)

    def test_pdf_export_endpoint_tenant_scoped(self):
        """GET /api/v1/marketplace/impact/export-pdf/ returns valid PDF scoped to organization."""
        self.client.force_authenticate(user=self.donor_user)
        res = self.client.get("/api/v1/marketplace/impact/export-pdf/?range=30d")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertIn("attachment; filename=", res["Content-Disposition"])
        self.assertTrue(res.content.startswith(b"%PDF-"))
        self.assertGreater(len(res.content), 1000)

    def test_csv_export_endpoint_tenant_scoped(self):
        """GET /api/v1/marketplace/impact/export-csv/ returns valid CSV with header and records."""
        self.client.force_authenticate(user=self.donor_user)
        res = self.client.get("/api/v1/marketplace/impact/export-csv/?range=all")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", res["Content-Type"])
        self.assertIn("attachment; filename=", res["Content-Disposition"])
        csv_text = res.content.decode("utf-8")
        self.assertIn("SurplusSync Sustainability Impact & ESG Audit Report", csv_text)
        self.assertIn("Organic Harvest Co", csv_text)
        self.assertIn("REQ-ESG-01", csv_text)
        self.assertIn("Fresh Shimla Apples", csv_text)

    def test_tenant_isolation_cannot_see_counterparty_other_donor(self):
        """Organization B sees only its own metrics (zeros if no completed transfers)."""
        self.client.force_authenticate(user=self.donor_b_user)
        res = self.client.get("/api/v1/marketplace/impact/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_donations_completed"], 0)
        self.assertEqual(res.data["total_quantity_donated_kg"], 0.0)
        self.assertEqual(res.data["meals_provided"], 0)

    def test_public_impact_endpoint_cached_and_shows_completed_only(self):
        """GET /api/v1/marketplace/impact/public/ returns platform-wide metrics and caches."""
        self.client.force_authenticate(user=None)
        res1 = self.client.get("/api/v1/marketplace/impact/public/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data["total_quantity_donated_kg"], 60.0)
        self.assertEqual(res1.data["meals_provided"], int(round(60.0 / 0.42)))
        self.assertEqual(res1.data["co2_diverted_kg"], 150.0)

        # Check cache is populated
        cached = cache.get("marketplace_public_impact_metrics")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["total_quantity_donated_kg"], 60.0)

    def test_activity_heatmap_and_geo_density_payload(self):
        """Activity heatmap matrix (7x6) and geo density points are generated."""
        self.client.force_authenticate(user=self.donor_user)
        res = self.client.get("/api/v1/marketplace/impact/?range=all")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        activity_matrix = res.data.get("activity_heatmap", [])
        self.assertEqual(len(activity_matrix), 42)  # 7 days * 6 time slots
        total_matrix_count = sum(cell["count"] for cell in activity_matrix)
        self.assertEqual(total_matrix_count, 2)

        geo_points = res.data.get("geo_density", [])
        self.assertEqual(len(geo_points), 2)
        p1 = geo_points[0]
        self.assertIn("latitude", p1)
        self.assertIn("longitude", p1)
        self.assertIn("quantity_kg", p1)
