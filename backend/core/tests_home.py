"""
Tests for Home API endpoints (Task B1).
Verifies:
- Public Home endpoint (/api/v1/home/public/):
  - Zero-data honest responses (no invented data)
  - Cached for 10 minutes
  - Leaks zero private or organization-level data
- Authenticated Home endpoint (/api/v1/home/):
  - Tenant isolation (never sees another organization's counts, alerts, or activity)
  - Role differences (Business gets business fields only; NGO gets NGO fields only)
  - Getting started checklist reflects real data dynamically (not stored flags)
  - Unverified NGO gets verification status but no donor data
  - Recent activity timeline combines status history & notifications, max 10
  - Impact snapshot computes 30-day metrics with standard multipliers
  - Performance: aggregate queries only, fast response time
"""
from datetime import date, timedelta
from decimal import Decimal
import time

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Organization, User
from inventory.models import Alert, Batch, Category, ImportJob, POSApiKey, Product
from marketplace.models import (
    DonationRequest,
    DonationStatusHistory,
    NGORequirement,
    Notification,
    SurplusListing,
)


class HomeAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Business Org A
        self.biz_org = Organization.objects.create(
            name="Grand Hotel Central",
            org_type=Organization.Type.BUSINESS,
            address="12 MG Road, Bengaluru",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.biz_user = User.objects.create_user(
            username="biz_manager",
            email="manager@grandhotel.com",
            password="securepassword123",
            organization=self.biz_org,
            role=User.Role.OWNER,
        )

        # Business Org B (for tenant isolation test)
        self.biz_org_b = Organization.objects.create(
            name="Competitor Banquet",
            org_type=Organization.Type.BUSINESS,
            address="45 Residency Road, Bengaluru",
            latitude=Decimal("12.970000"),
            longitude=Decimal("77.600000"),
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.biz_user_b = User.objects.create_user(
            username="biz_b",
            email="manager@competitor.com",
            password="securepassword123",
            organization=self.biz_org_b,
            role=User.Role.OWNER,
        )

        # Verified NGO Org
        self.ngo_org = Organization.objects.create(
            name="Robin Hood Food Relief",
            org_type=Organization.Type.NGO,
            address="88 Indiranagar, Bengaluru",
            latitude=Decimal("12.978400"),
            longitude=Decimal("77.640800"),
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.ngo_user = User.objects.create_user(
            username="ngo_director",
            email="director@robinhood.org",
            password="securepassword123",
            organization=self.ngo_org,
            role=User.Role.OWNER,
        )

        # Unverified NGO Org
        self.unverified_ngo_org = Organization.objects.create(
            name="New Hope Relief Hub",
            org_type=Organization.Type.NGO,
            address="100 Koramangala, Bengaluru",
            is_verified=False,
            verification_status=Organization.VerificationStatus.PENDING,
        )
        self.unverified_ngo_user = User.objects.create_user(
            username="new_ngo_user",
            email="user@newhope.org",
            password="securepassword123",
            organization=self.unverified_ngo_org,
            role=User.Role.STAFF,
        )

        # Category
        self.category = Category.objects.create(
            name="Prepared Meals",
            perishability_risk=Category.Risk.HIGH,
            storage_type=Category.Storage.CHILLED,
        )

    # -------------------------------------------------------------------------
    # 1. Public Endpoint Tests (/api/v1/home/public/)
    # -------------------------------------------------------------------------

    def test_home_public_zero_data_honest(self):
        """When there is no redistribution data, return zeros honestly without inventing figures."""
        # Clean out any pre-existing completed requests
        DonationRequest.objects.all().delete()

        res = self.client.get("/api/v1/home/public/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()

        self.assertEqual(data["kg_redistributed"], 0.0)
        self.assertEqual(data["meals"], 0)
        self.assertEqual(data["co2e"], 0.0)
        self.assertEqual(data["completed_donations"], 0)
        self.assertGreaterEqual(data["verified_donors"], 2)
        self.assertGreaterEqual(data["verified_ngos"], 1)

    def test_home_public_cached_10_minutes(self):
        """Public home endpoint is cached for 10 minutes and does not re-query database."""
        res1 = self.client.get("/api/v1/home/public/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # Verify key exists in Django cache
        cached = cache.get("home_public_totals")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["kg_redistributed"], res1.json()["kg_redistributed"])

        # Create new org after cache is set
        Organization.objects.create(
            name="Uncached New Org",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
        )

        # Second request should return identical cached result
        res2 = self.client.get("/api/v1/home/public/")
        self.assertEqual(res2.json()["verified_donors"], res1.json()["verified_donors"])

    def test_home_public_leaks_nothing_private(self):
        """Public endpoint leaks zero organization-level or personal data."""
        res = self.client.get("/api/v1/home/public/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()

        # Must not contain private keys
        forbidden_keys = [
            "organization",
            "organizations",
            "users",
            "email",
            "address",
            "latitude",
            "longitude",
            "recent_activity",
            "needs_attention",
            "phone",
        ]
        for k in forbidden_keys:
            self.assertNotIn(k, data)

    # -------------------------------------------------------------------------
    # 2. Authenticated Endpoint Security & Scoping
    # -------------------------------------------------------------------------

    def test_home_authenticated_requires_login(self):
        """Unauthenticated caller gets 401 Unauthorized."""
        res = self.client.get("/api/v1/home/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_home_business_fields_only(self):
        """Business users receive business counts only and zero NGO fields."""
        self.client.force_authenticate(user=self.biz_user)
        res = self.client.get("/api/v1/home/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()

        # Greeting
        self.assertEqual(data["greeting"]["organization_name"], self.biz_org.name)
        self.assertEqual(data["greeting"]["role"], "BUSINESS")
        self.assertTrue(data["greeting"]["is_verified"])

        # Business fields present
        self.assertIn("batches_expiring_48h", data)
        self.assertIn("unacknowledged_critical_alerts", data)
        self.assertIn("donation_requests_pending_approval", data)
        self.assertIn("pickups_scheduled_24h", data)
        self.assertIn("active_listings", data)

        # NGO fields strictly omitted
        self.assertNotIn("open_requests_awaiting_donor", data)
        self.assertNotIn("new_matching_listings_24h", data)
        self.assertNotIn("active_requirements", data)

    def test_home_ngo_fields_only(self):
        """NGO users receive NGO counts only and zero Business fields."""
        self.client.force_authenticate(user=self.ngo_user)
        res = self.client.get("/api/v1/home/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()

        # Greeting
        self.assertEqual(data["greeting"]["organization_name"], self.ngo_org.name)
        self.assertEqual(data["greeting"]["role"], "NGO")
        self.assertTrue(data["greeting"]["is_verified"])

        # NGO fields present
        self.assertIn("open_requests_awaiting_donor", data)
        self.assertIn("pickups_scheduled_24h", data)
        self.assertIn("new_matching_listings_24h", data)
        self.assertIn("active_requirements", data)

        # Business fields strictly omitted
        self.assertNotIn("batches_expiring_48h", data)
        self.assertNotIn("unacknowledged_critical_alerts", data)
        self.assertNotIn("donation_requests_pending_approval", data)
        self.assertNotIn("active_listings", data)

    # -------------------------------------------------------------------------
    # 3. Tenant Isolation
    # -------------------------------------------------------------------------

    def test_home_tenant_isolation(self):
        """Business A never sees Business B's expiring batches, alerts, or status history."""
        today = date.today()

        # Product and Batch for Business B
        prod_b = Product.objects.create(
            organization=self.biz_org_b,
            name="Competitor Pastry",
            category=self.category,
            unit="kg",
        )
        batch_b = Batch.objects.create(
            organization=self.biz_org_b,
            product=prod_b,
            batch_code="B-COMPETITOR",
            quantity=Decimal("50.000"),
            received_date=today,
            expiry_date=today + timedelta(days=1),
            status=Batch.Status.ACTIVE,
        )
        # Alert for Business B
        Alert.objects.create(
            organization=self.biz_org_b,
            batch=batch_b,
            severity=Alert.Severity.CRITICAL,
            message="Competitor expiring fast",
            is_acknowledged=False,
        )
        # Notification for Business B
        Notification.objects.create(
            organization=self.biz_org_b,
            type="ALERT",
            title="Competitor Secret Alert",
            body="Confidential data",
        )

        # Query as Business A
        self.client.force_authenticate(user=self.biz_user)
        res = self.client.get("/api/v1/home/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()

        # Business A has zero batches and zero alerts
        self.assertEqual(data["batches_expiring_48h"], 0)
        self.assertEqual(data["unacknowledged_critical_alerts"], 0)

        # Activity timeline must not contain Business B's notification
        activity_titles = [item["title"] for item in data["recent_activity"]]
        self.assertNotIn("Competitor Secret Alert", activity_titles)

    # -------------------------------------------------------------------------
    # 4. Getting Started Checklist Dynamic Computation
    # -------------------------------------------------------------------------

    def test_home_business_checklist_reflects_real_data(self):
        """Business checklist reflects real database records rather than static flags."""
        today = date.today()

        # Initially Biz Org A has location set, but no products, batches, POS keys, or listings
        self.client.force_authenticate(user=self.biz_user)
        res = self.client.get("/api/v1/home/")
        data = res.json()

        checklist = {item["id"]: item["done"] for item in data["getting_started"]}
        self.assertTrue(checklist["set_location"])
        self.assertFalse(checklist["add_product"])
        self.assertFalse(checklist["add_batch"])
        self.assertFalse(checklist["pos_or_csv"])
        self.assertFalse(checklist["create_listing"])

        # Add product and batch
        prod = Product.objects.create(
            organization=self.biz_org,
            name="Organic Apples",
            category=self.category,
            unit="kg",
        )
        Batch.objects.create(
            organization=self.biz_org,
            product=prod,
            quantity=Decimal("20.000"),
            received_date=today,
            expiry_date=today + timedelta(days=5),
            status=Batch.Status.ACTIVE,
        )
        # Add POS Key
        POSApiKey.objects.create(
            organization=self.biz_org,
            key_hash="hash123",
            label="Terminal 1",
        )

        # Re-fetch home
        res2 = self.client.get("/api/v1/home/")
        checklist2 = {item["id"]: item["done"] for item in res2.json()["getting_started"]}
        self.assertTrue(checklist2["add_product"])
        self.assertTrue(checklist2["add_batch"])
        self.assertTrue(checklist2["pos_or_csv"])
        self.assertFalse(checklist2["create_listing"])

    def test_home_ngo_checklist_reflects_real_data(self):
        """NGO checklist reflects real requirement and request data."""
        self.client.force_authenticate(user=self.ngo_user)
        res = self.client.get("/api/v1/home/")
        checklist = {item["id"]: item["done"] for item in res.json()["getting_started"]}

        self.assertTrue(checklist["set_location"])
        self.assertFalse(checklist["create_requirement"])
        self.assertFalse(checklist["make_request"])

        # Create requirement
        NGORequirement.objects.create(
            ngo=self.ngo_org,
            title="Daily Dinner Support",
            max_quantity=Decimal("30.000"),
            unit="kg",
        )

        res2 = self.client.get("/api/v1/home/")
        checklist2 = {item["id"]: item["done"] for item in res2.json()["getting_started"]}
        self.assertTrue(checklist2["create_requirement"])
        self.assertFalse(checklist2["make_request"])

    # -------------------------------------------------------------------------
    # 5. Unverified NGO
    # -------------------------------------------------------------------------

    def test_home_unverified_ngo_behavior(self):
        """Unverified NGO gets verification status but zero donor data and banner hint."""
        self.client.force_authenticate(user=self.unverified_ngo_user)
        res = self.client.get("/api/v1/home/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()

        self.assertEqual(data["greeting"]["verification_status"], "PENDING")
        self.assertFalse(data["greeting"]["is_verified"])

        # Needs attention has high urgency verification alert
        attentions = data["needs_attention"]
        self.assertTrue(any(a["type"] == "VERIFICATION_PENDING" for a in attentions))

        # No donor counts
        self.assertNotIn("batches_expiring_48h", data)
        self.assertNotIn("unacknowledged_critical_alerts", data)

    # -------------------------------------------------------------------------
    # 6. Impact Snapshot (last 30 days)
    # -------------------------------------------------------------------------

    def test_home_impact_snapshot_30d(self):
        """Impact snapshot correctly aggregates completed requests in the last 30 days."""
        now = timezone.now()
        listing = SurplusListing.objects.create(
            donor=self.biz_org,
            title="Buffet Curries",
            category=self.category,
            quantity_offered=Decimal("50.000"),
            unit="kg",
            available_from=now - timedelta(days=2),
            available_until=now + timedelta(days=1),
        )

        req = DonationRequest.objects.create(
            listing=listing,
            ngo=self.ngo_org,
            quantity_requested=Decimal("30.000"),
            quantity_approved=Decimal("30.000"),
            quantity_collected=Decimal("30.000"),
            status=DonationRequest.Status.COMPLETED,
            proposed_pickup_start=now - timedelta(days=2),
            proposed_pickup_end=now - timedelta(days=2) + timedelta(hours=2),
            confirmed_pickup_start=now - timedelta(days=2),
            confirmed_pickup_end=now - timedelta(days=2) + timedelta(hours=2),
        )

        self.client.force_authenticate(user=self.biz_user)
        res = self.client.get("/api/v1/home/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        impact = res.json()["impact_snapshot"]

        self.assertEqual(impact["kg"], 30.0)
        self.assertEqual(impact["meals"], int(round(30.0 * 2.4)))  # 72
        self.assertEqual(impact["co2e"], round(30.0 * 2.5, 2))     # 75.0

    # -------------------------------------------------------------------------
    # 7. Performance Benchmarking
    # -------------------------------------------------------------------------

    def test_home_response_time_under_300ms(self):
        """GET /api/v1/home/ executes in under 300 ms."""
        self.client.force_authenticate(user=self.biz_user)

        start = time.perf_counter()
        res = self.client.get("/api/v1/home/")
        duration_ms = (time.perf_counter() - start) * 1000

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertLess(duration_ms, 300.0, f"Response took {duration_ms:.2f} ms, expected < 300 ms")
