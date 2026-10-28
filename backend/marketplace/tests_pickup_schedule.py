from datetime import timedelta
from decimal import Decimal
from io import StringIO
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Organization, User
from inventory.models import Batch, Category, Product
from marketplace.ics_calendar import escape_ics_text, fold_line, generate_ics_calendar
from marketplace.models import DonationRequest, Notification, SurplusListing
from marketplace.tasks import send_pickup_reminders_task, track_overdue_pickups_task


class PickupScheduleEnhancementsTestCase(APITestCase):
    def setUp(self):
        # 1. Organizations
        self.donor_biz = Organization.objects.create(
            name="Green Grocers",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
            address="100 Organic Way, Sector 4",
            phone="+91 80 5555 1111",
        )
        self.other_biz = Organization.objects.create(
            name="City Bakery",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
            address="200 Flour Street",
        )
        self.ngo = Organization.objects.create(
            name="Care FoodBank",
            org_type=Organization.Type.NGO,
            is_verified=True,
            address="50 Relief Colony",
            phone="+91 80 5555 2222",
        )
        self.other_ngo = Organization.objects.create(
            name="Hope Mission",
            org_type=Organization.Type.NGO,
            is_verified=True,
            address="75 Shelter Road",
        )

        # 2. Users
        self.donor_user = User.objects.create_user(
            username="donor_biz_user",
            password="password123",
            organization=self.donor_biz,
        )
        self.other_biz_user = User.objects.create_user(
            username="other_biz_user",
            password="password123",
            organization=self.other_biz,
        )
        self.ngo_user = User.objects.create_user(
            username="ngo_manager",
            password="password123",
            organization=self.ngo,
        )
        self.other_ngo_user = User.objects.create_user(
            username="other_ngo_user",
            password="password123",
            organization=self.other_ngo,
        )
        self.admin_user = User.objects.create_superuser(
            username="sys_admin",
            password="password123",
            is_staff=True,
        )

        # 3. Product & Listing
        self.category = Category.objects.create(name="Fresh Produce")
        self.product = Product.objects.create(
            organization=self.donor_biz,
            category=self.category,
            name="Fresh Apples",
            sku="APPL-001",
        )
        self.batch = Batch.objects.create(
            organization=self.donor_biz,
            product=self.product,
            batch_code="B-APP-01",
            quantity=Decimal("100.000"),
            received_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timedelta(days=5),
        )
        self.listing = SurplusListing.objects.create(
            donor=self.donor_biz,
            category=self.category,
            title="Fresh Crisp Apples",
            quantity_offered=Decimal("50.000"),
            unit="kg",
            pickup_address="100 Organic Way, Loading Bay 3",
            available_from=timezone.now() - timedelta(days=1),
            available_until=timezone.now() + timedelta(days=2),
            status=SurplusListing.Status.OPEN,
        )

    # -------------------------------------------------------------------------
    # 1. RFC 5545 iCalendar Generator Unit Tests
    # -------------------------------------------------------------------------
    def test_escape_ics_text(self):
        raw = "Hello, world; with \\ backslash\nand new line\r\nand more."
        escaped = escape_ics_text(raw)
        self.assertIn(r"\,", escaped)
        self.assertIn(r"\;", escaped)
        self.assertIn(r"\\", escaped)
        self.assertIn(r"\n", escaped)
        self.assertNotIn("\r", escaped)

    def test_fold_line(self):
        long_line = "DESCRIPTION:" + "A" * 120
        folded = fold_line(long_line)
        self.assertIn("\r\n ", folded)
        for line in folded.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)

    def test_generate_ics_calendar(self):
        now = timezone.now()
        req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.ngo,
            code="REQ-ICS-001",
            status=DonationRequest.Status.SCHEDULED,
            quantity_requested=Decimal("25.000"),
            quantity_approved=Decimal("25.000"),
            proposed_pickup_start=now + timedelta(hours=5),
            proposed_pickup_end=now + timedelta(hours=7),
            confirmed_pickup_start=now + timedelta(hours=5),
            confirmed_pickup_end=now + timedelta(hours=7),
            contact_name="Driver Suresh",
            contact_phone="+91 99999 88888",
            note="Please bring refrigeration bags",
        )

        ics_str = generate_ics_calendar([req], calendar_name="Test Calendar")
        self.assertTrue(ics_str.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(ics_str.endswith("END:VCALENDAR\r\n"))
        self.assertIn("VERSION:2.0\r\n", ics_str)
        self.assertIn("PRODID:-//SurplusSync//Redistribution Logistics//EN\r\n", ics_str)
        self.assertIn("BEGIN:VEVENT\r\n", ics_str)
        self.assertIn(f"UID:pickup-{req.id}-{req.code}@surplussync.org", ics_str)
        self.assertIn("SUMMARY:Surplus Food Pickup: Fresh Crisp Apples (25.000 kg)", ics_str)
        self.assertIn("STATUS:CONFIRMED", ics_str)
        self.assertIn("LOCATION:100 Organic Way\\, Loading Bay 3", ics_str)
        self.assertIn("END:VEVENT\r\n", ics_str)

    # -------------------------------------------------------------------------
    # 2. Pickup Schedule ICS Export Endpoints & Tenant Isolation
    # -------------------------------------------------------------------------
    def test_export_ics_all_schedule_for_business(self):
        now = timezone.now()
        req1 = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.ngo,
            code="REQ-BIZ-01",
            status=DonationRequest.Status.SCHEDULED,
            quantity_requested=Decimal("15.000"),
            quantity_approved=Decimal("15.000"),
            proposed_pickup_start=now + timedelta(hours=3),
            proposed_pickup_end=now + timedelta(hours=5),
            confirmed_pickup_start=now + timedelta(hours=3),
            confirmed_pickup_end=now + timedelta(hours=5),
        )

        self.client.force_authenticate(user=self.donor_user)
        response = self.client.get("/api/v1/marketplace/schedule/export-ics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/calendar; charset=utf-8")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("BEGIN:VCALENDAR", content)
        self.assertIn(req1.code, content)

    def test_export_ics_all_schedule_for_ngo(self):
        now = timezone.now()
        req1 = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.ngo,
            code="REQ-NGO-01",
            status=DonationRequest.Status.APPROVED,
            quantity_requested=Decimal("20.000"),
            quantity_approved=Decimal("20.000"),
            proposed_pickup_start=now + timedelta(hours=4),
            proposed_pickup_end=now + timedelta(hours=6),
            confirmed_pickup_start=now + timedelta(hours=4),
            confirmed_pickup_end=now + timedelta(hours=6),
        )

        self.client.force_authenticate(user=self.ngo_user)
        response = self.client.get("/api/v1/marketplace/schedule/export-ics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode("utf-8")
        self.assertIn(req1.code, content)

    def test_export_ics_single_event_success_and_isolation(self):
        now = timezone.now()
        req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.ngo,
            code="REQ-SNG-01",
            status=DonationRequest.Status.SCHEDULED,
            quantity_requested=Decimal("10.000"),
            quantity_approved=Decimal("10.000"),
            proposed_pickup_start=now + timedelta(hours=6),
            proposed_pickup_end=now + timedelta(hours=8),
            confirmed_pickup_start=now + timedelta(hours=6),
            confirmed_pickup_end=now + timedelta(hours=8),
        )

        # 1. Donor business can export
        self.client.force_authenticate(user=self.donor_user)
        res_donor = self.client.get(f"/api/v1/marketplace/schedule/{req.id}/export-ics/")
        self.assertEqual(res_donor.status_code, status.HTTP_200_OK)
        self.assertIn("BEGIN:VCALENDAR", res_donor.content.decode("utf-8"))

        # 2. Recipient NGO can export by code
        self.client.force_authenticate(user=self.ngo_user)
        res_ngo = self.client.get(f"/api/v1/marketplace/requests/{req.code}/export-ics/")
        self.assertEqual(res_ngo.status_code, status.HTTP_200_OK)
        self.assertIn("BEGIN:VCALENDAR", res_ngo.content.decode("utf-8"))

        # 3. Third-party NGO is denied access (Tenant isolation)
        self.client.force_authenticate(user=self.other_ngo_user)
        res_denied = self.client.get(f"/api/v1/marketplace/schedule/{req.id}/export-ics/")
        self.assertEqual(res_denied.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Unauthenticated user denied
        self.client.force_authenticate(user=None)
        res_unauth = self.client.get(f"/api/v1/marketplace/schedule/{req.id}/export-ics/")
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

    # -------------------------------------------------------------------------
    # 3. Pickup Schedule Agenda API Overdue Tracking & Filtering
    # -------------------------------------------------------------------------
    def test_pickup_schedule_overdue_attributes_and_filter(self):
        now = timezone.now()
        # Overdue request: end time passed 2 hours ago
        req_overdue = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.ngo,
            code="REQ-OVERDUE-01",
            status=DonationRequest.Status.SCHEDULED,
            quantity_requested=Decimal("12.000"),
            quantity_approved=Decimal("12.000"),
            proposed_pickup_start=now - timedelta(hours=4),
            proposed_pickup_end=now - timedelta(hours=2),
            confirmed_pickup_start=now - timedelta(hours=4),
            confirmed_pickup_end=now - timedelta(hours=2),
        )
        # Future scheduled request (different NGO to satisfy uniq_active_req_per_ngo_listing)
        req_future = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.other_ngo,
            code="REQ-FUTURE-01",
            status=DonationRequest.Status.SCHEDULED,
            quantity_requested=Decimal("8.000"),
            quantity_approved=Decimal("8.000"),
            proposed_pickup_start=now + timedelta(hours=3),
            proposed_pickup_end=now + timedelta(hours=5),
            confirmed_pickup_start=now + timedelta(hours=3),
            confirmed_pickup_end=now + timedelta(hours=5),
        )

        self.client.force_authenticate(user=self.donor_user)
        res = self.client.get("/api/v1/marketplace/schedule/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data["results"]
        overdue_item = next(i for i in results if i["request_code"] == req_overdue.code)
        self.assertTrue(overdue_item["is_overdue"])
        self.assertGreaterEqual(overdue_item["overdue_minutes"], 115)

        future_item = next(i for i in results if i["request_code"] == req_future.code)
        self.assertFalse(future_item["is_overdue"])
        self.assertIsNone(future_item["overdue_minutes"])

        # Filter by status=OVERDUE
        res_overdue_only = self.client.get("/api/v1/marketplace/schedule/?status=OVERDUE")
        self.assertEqual(res_overdue_only.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_overdue_only.data["results"]), 1)
        self.assertEqual(res_overdue_only.data["results"][0]["request_code"], req_overdue.code)

    # -------------------------------------------------------------------------
    # 4. Automated Reminders Task (24h and 2h) & Idempotency
    # -------------------------------------------------------------------------
    def test_send_pickup_reminders_task_and_command(self):
        now = timezone.now()
        listing2 = SurplusListing.objects.create(
            donor=self.donor_biz,
            category=self.category,
            title="Fresh Oranges",
            quantity_offered=Decimal("30.000"),
            unit="kg",
            available_from=now - timedelta(days=1),
            available_until=now + timedelta(days=2),
            status=SurplusListing.Status.OPEN,
        )
        listing3 = SurplusListing.objects.create(
            donor=self.donor_biz,
            category=self.category,
            title="Fresh Bananas",
            quantity_offered=Decimal("20.000"),
            unit="kg",
            available_from=now - timedelta(days=1),
            available_until=now + timedelta(days=5),
            status=SurplusListing.Status.OPEN,
        )

        # Request 1: In 18 hours (eligible for 24h reminder)
        DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.ngo,
            code="REQ-REMIND-24H",
            status=DonationRequest.Status.SCHEDULED,
            quantity_requested=Decimal("10.000"),
            quantity_approved=Decimal("10.000"),
            proposed_pickup_start=now + timedelta(hours=18),
            proposed_pickup_end=now + timedelta(hours=20),
            confirmed_pickup_start=now + timedelta(hours=18),
            confirmed_pickup_end=now + timedelta(hours=20),
        )
        # Request 2: In 1 hour (eligible for both 24h and 2h reminders)
        DonationRequest.objects.create(
            listing=listing2,
            ngo=self.ngo,
            code="REQ-REMIND-2H",
            status=DonationRequest.Status.SCHEDULED,
            quantity_requested=Decimal("15.000"),
            quantity_approved=Decimal("15.000"),
            proposed_pickup_start=now + timedelta(hours=1),
            proposed_pickup_end=now + timedelta(hours=2),
            confirmed_pickup_start=now + timedelta(hours=1),
            confirmed_pickup_end=now + timedelta(hours=2),
        )
        # Request 3: In 48 hours (not eligible)
        DonationRequest.objects.create(
            listing=listing3,
            ngo=self.ngo,
            code="REQ-REMIND-FAR",
            status=DonationRequest.Status.SCHEDULED,
            quantity_requested=Decimal("5.000"),
            quantity_approved=Decimal("5.000"),
            proposed_pickup_start=now + timedelta(hours=48),
            proposed_pickup_end=now + timedelta(hours=50),
            confirmed_pickup_start=now + timedelta(hours=48),
            confirmed_pickup_end=now + timedelta(hours=50),
        )

        # First run: should dispatch reminders
        res1 = send_pickup_reminders_task()
        # req_24h gives 2 notifications (donor + ngo for 24h)
        # req_2h gives 4 notifications (donor + ngo for 24h, donor + ngo for 2h)
        self.assertEqual(res1["reminders_24h_sent"], 4)
        self.assertEqual(res1["reminders_2h_sent"], 2)
        self.assertEqual(res1["total_sent"], 6)

        # Verify notification records in DB
        donor_notifs = Notification.objects.filter(organization=self.donor_biz)
        ngo_notifs = Notification.objects.filter(organization=self.ngo)
        self.assertEqual(donor_notifs.count(), 3)
        self.assertEqual(ngo_notifs.count(), 3)

        # Idempotency check: Running again must dispatch 0 duplicate notifications
        res2 = send_pickup_reminders_task()
        self.assertEqual(res2["total_sent"], 0)

        # Test management command execution
        out = StringIO()
        call_command("send_pickup_reminders", stdout=out)
        self.assertIn("Pickup reminders processed", out.getvalue())

    # -------------------------------------------------------------------------
    # 5. Overdue Tracking Task & Idempotency
    # -------------------------------------------------------------------------
    def test_track_overdue_pickups_task_and_command(self):
        now = timezone.now()
        # Active overdue request (pickup ended 90 mins ago)
        req_overdue = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.ngo,
            code="REQ-TRACK-OVERDUE",
            status=DonationRequest.Status.IN_TRANSIT,
            quantity_requested=Decimal("30.000"),
            quantity_approved=Decimal("30.000"),
            proposed_pickup_start=now - timedelta(hours=3),
            proposed_pickup_end=now - timedelta(minutes=90),
            confirmed_pickup_start=now - timedelta(hours=3),
            confirmed_pickup_end=now - timedelta(minutes=90),
        )
        # Completed request whose pickup window is in the past (must not trigger overdue)
        DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.ngo,
            code="REQ-TRACK-COMPLETED",
            status=DonationRequest.Status.COMPLETED,
            quantity_requested=Decimal("20.000"),
            quantity_approved=Decimal("20.000"),
            proposed_pickup_start=now - timedelta(hours=5),
            proposed_pickup_end=now - timedelta(hours=3),
            confirmed_pickup_start=now - timedelta(hours=5),
            confirmed_pickup_end=now - timedelta(hours=3),
        )

        res1 = track_overdue_pickups_task()
        self.assertEqual(res1["overdue_count"], 1)
        self.assertEqual(res1["notifications_sent"], 2)  # 1 to donor, 1 to NGO
        self.assertEqual(res1["overdue_requests"][0]["code"], req_overdue.code)
        self.assertGreaterEqual(res1["overdue_requests"][0]["overdue_minutes"], 85)

        # Notifications created
        overdue_notifs = Notification.objects.filter(type="PICKUP_OVERDUE", link__contains=req_overdue.code)
        self.assertEqual(overdue_notifs.count(), 2)

        # Idempotency check: Running again must dispatch 0 duplicate notifications
        res2 = track_overdue_pickups_task()
        self.assertEqual(res2["overdue_count"], 1)
        self.assertEqual(res2["notifications_sent"], 0)

        # Test management command execution
        out = StringIO()
        call_command("track_overdue_pickups", stdout=out)
        self.assertIn("Overdue pickups processed", out.getvalue())
