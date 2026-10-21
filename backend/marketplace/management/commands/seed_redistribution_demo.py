"""
Management command to seed demo redistribution data:
Listings in every status (DRAFT, OPEN, FULLY_RESERVED, COMPLETED, CANCELLED, EXPIRED),
NGO Requirements, and Donation Requests in every status
(REQUESTED, APPROVED, SCHEDULED, IN_TRANSIT, COLLECTED, COMPLETED, REJECTED, CANCELLED, NO_SHOW, EXPIRED),
along with status history and notifications.
"""
from datetime import date, time, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Organization, User
from inventory.models import Category, Product, Batch, StorageLocation
from marketplace.models import (
    DonationRequest,
    DonationStatusHistory,
    NGORequirement,
    Notification,
    Rating,
    SurplusListing,
)


class Command(BaseCommand):
    help = "Seed demo redistribution data across listings, requirements, requests, and notifications."

    def handle(self, *args, **options):
        self.stdout.write("Seeding redistribution demo data...")
        with transaction.atomic():
            # 1. Organizations
            biz1, _ = Organization.objects.get_or_create(
                name="Fresh Harvest Supermarket",
                defaults={
                    "org_type": Organization.Type.BUSINESS,
                    "address": "100 MG Road, Indiranagar, Bengaluru",
                    "latitude": Decimal("12.971600"),
                    "longitude": Decimal("77.594600"),
                    "phone": "+91 98765 43210",
                    "verification_status": Organization.VerificationStatus.VERIFIED,
                    "is_verified": True,
                    "timezone": "Asia/Kolkata",
                    "max_concurrent_pickups": 3,
                },
            )

            biz2, _ = Organization.objects.get_or_create(
                name="Sunrise Artisan Bakery",
                defaults={
                    "org_type": Organization.Type.BUSINESS,
                    "address": "45 Brigade Road, Ashok Nagar, Bengaluru",
                    "latitude": Decimal("12.972400"),
                    "longitude": Decimal("77.608000"),
                    "phone": "+91 98765 12345",
                    "verification_status": Organization.VerificationStatus.VERIFIED,
                    "is_verified": True,
                    "timezone": "Asia/Kolkata",
                    "max_concurrent_pickups": 2,
                },
            )

            ngo1, _ = Organization.objects.get_or_create(
                name="City Food Bank Trust",
                defaults={
                    "org_type": Organization.Type.NGO,
                    "address": "12 Residency Road, Richmond Town, Bengaluru",
                    "latitude": Decimal("12.966700"),
                    "longitude": Decimal("77.601200"),
                    "phone": "+91 91234 56789",
                    "verification_status": Organization.VerificationStatus.VERIFIED,
                    "is_verified": True,
                    "timezone": "Asia/Kolkata",
                },
            )

            ngo2, _ = Organization.objects.get_or_create(
                name="Hope Community Kitchen",
                defaults={
                    "org_type": Organization.Type.NGO,
                    "address": "88 Koramangala 4th Block, Bengaluru",
                    "latitude": Decimal("12.935200"),
                    "longitude": Decimal("77.624500"),
                    "phone": "+91 93456 78901",
                    "verification_status": Organization.VerificationStatus.VERIFIED,
                    "is_verified": True,
                    "timezone": "Asia/Kolkata",
                },
            )

            # 2. Categories & Products & Batches
            cat_dairy, _ = Category.objects.get_or_create(name="Dairy", defaults={"perishability_risk": Category.Risk.HIGH})
            cat_bakery, _ = Category.objects.get_or_create(name="Bakery", defaults={"perishability_risk": Category.Risk.MEDIUM})
            cat_produce, _ = Category.objects.get_or_create(name="Produce", defaults={"perishability_risk": Category.Risk.HIGH})
            cat_meals, _ = Category.objects.get_or_create(name="Prepared Meals", defaults={"perishability_risk": Category.Risk.CRITICAL})

            prod_milk, _ = Product.objects.get_or_create(
                organization=biz1,
                name="Pasteurized Whole Milk 1L",
                defaults={"category": cat_dairy, "unit": "L", "sku": "MILK-1L", "unit_cost": Decimal("45.00")},
            )
            prod_bread, _ = Product.objects.get_or_create(
                organization=biz2,
                name="Whole Wheat Sandwich Bread",
                defaults={"category": cat_bakery, "unit": "kg", "sku": "BREAD-WW", "unit_cost": Decimal("40.00")},
            )

            today = date.today()
            batch_milk, _ = Batch.objects.get_or_create(
                organization=biz1,
                product=prod_milk,
                batch_code="DEMO-B-MILK",
                defaults={
                    "quantity": Decimal("100.000"),
                    "reserved_quantity": Decimal("25.000"),
                    "received_date": today - timedelta(days=2),
                    "expiry_date": today + timedelta(days=4),
                    "status": Batch.Status.ACTIVE,
                },
            )
            batch_bread, _ = Batch.objects.get_or_create(
                organization=biz2,
                product=prod_bread,
                batch_code="DEMO-B-BREAD",
                defaults={
                    "quantity": Decimal("60.000"),
                    "reserved_quantity": Decimal("0.000"),
                    "received_date": today - timedelta(days=1),
                    "expiry_date": today + timedelta(days=2),
                    "status": Batch.Status.ACTIVE,
                },
            )

            now = timezone.now()

            # 3. Surplus Listings in Every Status
            listings = {}
            # DRAFT
            listings["DRAFT"], _ = SurplusListing.objects.get_or_create(
                title="Excess Organic Apples (Draft)",
                defaults={
                    "donor": biz1,
                    "category": cat_produce,
                    "quantity_offered": Decimal("30.000"),
                    "unit": "kg",
                    "available_from": now + timedelta(days=1),
                    "available_until": now + timedelta(days=2),
                    "status": SurplusListing.Status.DRAFT,
                },
            )

            # OPEN 1
            listings["OPEN"], _ = SurplusListing.objects.get_or_create(
                title="Fresh Whole Milk Crates",
                defaults={
                    "donor": biz1,
                    "batch": batch_milk,
                    "category": cat_dairy,
                    "quantity_offered": Decimal("50.000"),
                    "quantity_reserved": Decimal("20.000"),
                    "unit": "L",
                    "available_from": now,
                    "available_until": now + timedelta(hours=8),
                    "safe_until": now + timedelta(hours=10),
                    "status": SurplusListing.Status.OPEN,
                },
            )

            # OPEN 2
            listings["OPEN_2"], _ = SurplusListing.objects.get_or_create(
                title="Assorted Organic Vegetable Crates",
                defaults={
                    "donor": biz1,
                    "category": cat_produce,
                    "quantity_offered": Decimal("35.000"),
                    "quantity_reserved": Decimal("10.000"),
                    "unit": "kg",
                    "available_from": now,
                    "available_until": now + timedelta(hours=12),
                    "status": SurplusListing.Status.OPEN,
                },
            )

            # FULLY_RESERVED
            listings["FULLY_RESERVED"], _ = SurplusListing.objects.get_or_create(
                title="Artisan Sourdough Loaves",
                defaults={
                    "donor": biz2,
                    "batch": batch_bread,
                    "category": cat_bakery,
                    "quantity_offered": Decimal("25.000"),
                    "quantity_reserved": Decimal("25.000"),
                    "unit": "kg",
                    "available_from": now - timedelta(hours=1),
                    "available_until": now + timedelta(hours=4),
                    "status": SurplusListing.Status.FULLY_RESERVED,
                },
            )

            # COMPLETED
            listings["COMPLETED"], _ = SurplusListing.objects.get_or_create(
                title="Surplus Sandwiches from Catering",
                defaults={
                    "donor": biz1,
                    "category": cat_meals,
                    "quantity_offered": Decimal("40.000"),
                    "quantity_reserved": Decimal("0.000"),
                    "unit": "kg",
                    "is_cooked": True,
                    "available_from": now - timedelta(days=2),
                    "available_until": now - timedelta(days=1, hours=18),
                    "safe_until": now - timedelta(days=1, hours=16),
                    "status": SurplusListing.Status.COMPLETED,
                },
            )

            # CANCELLED
            listings["CANCELLED"], _ = SurplusListing.objects.get_or_create(
                title="Damaged Packaging Muffins",
                defaults={
                    "donor": biz2,
                    "category": cat_bakery,
                    "quantity_offered": Decimal("15.000"),
                    "unit": "kg",
                    "available_from": now - timedelta(days=3),
                    "available_until": now - timedelta(days=2),
                    "status": SurplusListing.Status.CANCELLED,
                },
            )

            # EXPIRED
            listings["EXPIRED"], _ = SurplusListing.objects.get_or_create(
                title="Unclaimed Fresh Baguettes",
                defaults={
                    "donor": biz2,
                    "category": cat_bakery,
                    "quantity_offered": Decimal("20.000"),
                    "unit": "kg",
                    "available_from": now - timedelta(days=1, hours=6),
                    "available_until": now - timedelta(hours=2),
                    "status": SurplusListing.Status.EXPIRED,
                },
            )

            # 4. NGO Requirements
            req1, _ = NGORequirement.objects.get_or_create(
                title="Daily Bread & Grains",
                defaults={
                    "ngo": ngo1,
                    "min_quantity": Decimal("10.000"),
                    "max_quantity": Decimal("50.000"),
                    "unit": "kg",
                    "radius_km": Decimal("10.00"),
                    "frequency": NGORequirement.Frequency.DAILY,
                    "accepts_cooked_food": True,
                    "preferred_pickup_start": time(9, 0),
                    "preferred_pickup_end": time(12, 0),
                    "is_active": True,
                },
            )
            req1.categories.add(cat_bakery, cat_meals)

            req2, _ = NGORequirement.objects.get_or_create(
                title="Weekly Dairy Requirement",
                defaults={
                    "ngo": ngo2,
                    "min_quantity": Decimal("15.000"),
                    "max_quantity": Decimal("40.000"),
                    "unit": "L",
                    "radius_km": Decimal("15.00"),
                    "frequency": NGORequirement.Frequency.WEEKLY,
                    "accepts_cooked_food": False,
                    "preferred_pickup_start": time(14, 0),
                    "preferred_pickup_end": time(18, 0),
                    "is_active": True,
                },
            )
            req2.categories.add(cat_dairy)

            # 5. Donation Requests in EVERY Status
            def _create_request(code, listing_key, ngo, qty_req, qty_app, qty_col, status, **kwargs):
                req, created = DonationRequest.objects.get_or_create(
                    code=code,
                    defaults={
                        "listing": listings[listing_key],
                        "ngo": ngo,
                        "quantity_requested": Decimal(str(qty_req)),
                        "quantity_approved": Decimal(str(qty_app)) if qty_app is not None else None,
                        "quantity_collected": Decimal(str(qty_col)) if qty_col is not None else None,
                        "status": status,
                        "proposed_pickup_start": kwargs.get("proposed_pickup_start", now + timedelta(hours=2)),
                        "proposed_pickup_end": kwargs.get("proposed_pickup_end", now + timedelta(hours=4)),
                        "confirmed_pickup_start": kwargs.get("confirmed_pickup_start"),
                        "confirmed_pickup_end": kwargs.get("confirmed_pickup_end"),
                        "note": kwargs.get("note", "Demo donation request"),
                        "rejection_reason": kwargs.get("rejection_reason", ""),
                        "contact_name": "Ravi Kumar",
                        "contact_phone": "+91 98765 00000",
                        "requested_at": kwargs.get("requested_at", now - timedelta(hours=5)),
                        "approved_at": kwargs.get("approved_at"),
                        "scheduled_at": kwargs.get("scheduled_at"),
                        "in_transit_at": kwargs.get("in_transit_at"),
                        "collected_at": kwargs.get("collected_at"),
                        "completed_at": kwargs.get("completed_at"),
                        "rejected_at": kwargs.get("rejected_at"),
                        "cancelled_at": kwargs.get("cancelled_at"),
                        "no_show_at": kwargs.get("no_show_at"),
                        "expired_at": kwargs.get("expired_at"),
                    },
                )
                return req

            # 1. REQUESTED
            r_requested = _create_request("REQ-1001", "OPEN", ngo1, 15, None, None, DonationRequest.Status.REQUESTED)
            DonationStatusHistory.objects.get_or_create(request=r_requested, from_status="", to_status="REQUESTED", defaults={"note": "Request submitted by NGO"})

            # 2. APPROVED
            r_approved = _create_request("REQ-1002", "OPEN", ngo2, 20, 20, None, DonationRequest.Status.APPROVED, approved_at=now - timedelta(hours=3))
            DonationStatusHistory.objects.get_or_create(request=r_approved, from_status="", to_status="REQUESTED")
            DonationStatusHistory.objects.get_or_create(request=r_approved, from_status="REQUESTED", to_status="APPROVED", defaults={"note": "Approved full requested quantity"})

            # 3. SCHEDULED
            r_scheduled = _create_request(
                "REQ-1003", "FULLY_RESERVED", ngo1, 25, 25, None, DonationRequest.Status.SCHEDULED,
                approved_at=now - timedelta(hours=4),
                scheduled_at=now - timedelta(hours=3),
                confirmed_pickup_start=now + timedelta(hours=2),
                confirmed_pickup_end=now + timedelta(hours=3),
            )
            DonationStatusHistory.objects.get_or_create(request=r_scheduled, from_status="REQUESTED", to_status="APPROVED")
            DonationStatusHistory.objects.get_or_create(request=r_scheduled, from_status="APPROVED", to_status="SCHEDULED", defaults={"note": "Pickup slot agreed"})

            # 4. IN_TRANSIT
            r_transit = _create_request(
                "REQ-1004", "OPEN_2", ngo2, 10, 10, None, DonationRequest.Status.IN_TRANSIT,
                approved_at=now - timedelta(hours=2),
                scheduled_at=now - timedelta(hours=1),
                in_transit_at=now - timedelta(minutes=15),
                confirmed_pickup_start=now + timedelta(minutes=30),
                confirmed_pickup_end=now + timedelta(hours=1, minutes=30),
            )
            DonationStatusHistory.objects.get_or_create(request=r_transit, from_status="SCHEDULED", to_status="IN_TRANSIT", defaults={"note": "NGO volunteer marked On my way"})

            # 5. COLLECTED
            r_collected = _create_request(
                "REQ-1005", "COMPLETED", ngo1, 30, 30, 30, DonationRequest.Status.COLLECTED,
                approved_at=now - timedelta(days=1),
                scheduled_at=now - timedelta(days=1, hours=2),
                collected_at=now - timedelta(hours=6),
                confirmed_pickup_start=now - timedelta(hours=7),
                confirmed_pickup_end=now - timedelta(hours=6),
            )
            DonationStatusHistory.objects.get_or_create(request=r_collected, from_status="IN_TRANSIT", to_status="COLLECTED", defaults={"note": "Handover verified by business"})

            # 6. COMPLETED
            r_completed = _create_request(
                "REQ-1006", "COMPLETED", ngo2, 40, 40, 40, DonationRequest.Status.COMPLETED,
                approved_at=now - timedelta(days=2),
                scheduled_at=now - timedelta(days=2, hours=1),
                collected_at=now - timedelta(days=1),
                completed_at=now - timedelta(days=1, hours=2),
                confirmed_pickup_start=now - timedelta(days=1, hours=4),
                confirmed_pickup_end=now - timedelta(days=1, hours=2),
            )
            DonationStatusHistory.objects.get_or_create(request=r_completed, from_status="COLLECTED", to_status="COMPLETED", defaults={"note": "NGO confirmed receipt of items"})

            # Rating for completed donation
            Rating.objects.get_or_create(
                request=r_completed,
                defaults={
                    "ngo": ngo2,
                    "business": biz1,
                    "stars": 5,
                    "comment": "Fresh, well packed, and very smooth pickup experience!",
                },
            )

            # 7. REJECTED
            r_rejected = _create_request(
                "REQ-1007", "OPEN", ngo1, 50, None, None, DonationRequest.Status.REJECTED,
                rejection_reason="Requested quantity exceeds available stock batch capacity.",
                rejected_at=now - timedelta(hours=2),
            )
            DonationStatusHistory.objects.get_or_create(request=r_rejected, from_status="REQUESTED", to_status="REJECTED", defaults={"note": "Rejected: stock capacity"})

            # 8. CANCELLED
            r_cancelled = _create_request(
                "REQ-1008", "OPEN", ngo2, 10, None, None, DonationRequest.Status.CANCELLED,
                cancelled_at=now - timedelta(hours=1),
            )
            DonationStatusHistory.objects.get_or_create(request=r_cancelled, from_status="REQUESTED", to_status="CANCELLED", defaults={"note": "NGO cancelled request"})

            # 9. NO_SHOW
            r_noshow = _create_request(
                "REQ-1009", "EXPIRED", ngo1, 15, 15, None, DonationRequest.Status.NO_SHOW,
                approved_at=now - timedelta(days=1),
                scheduled_at=now - timedelta(days=1),
                no_show_at=now - timedelta(hours=5),
                confirmed_pickup_start=now - timedelta(hours=8),
                confirmed_pickup_end=now - timedelta(hours=6),
            )
            DonationStatusHistory.objects.get_or_create(request=r_noshow, from_status="SCHEDULED", to_status="NO_SHOW", defaults={"note": "NGO did not arrive during pickup window"})

            # 10. EXPIRED
            r_expired = _create_request(
                "REQ-1010", "EXPIRED", ngo2, 10, None, None, DonationRequest.Status.EXPIRED,
                expired_at=now - timedelta(hours=2),
            )
            DonationStatusHistory.objects.get_or_create(request=r_expired, from_status="REQUESTED", to_status="EXPIRED", defaults={"note": "Listing expired before approval"})

            # 6. Notifications
            Notification.objects.get_or_create(
                organization=biz1,
                title="New Donation Request REQ-1001",
                defaults={
                    "type": "NEW_REQUEST",
                    "body": "City Food Bank Trust requested 15 L of Fresh Whole Milk Crates.",
                    "link": "/business/donations?request=REQ-1001",
                    "is_read": False,
                },
            )
            Notification.objects.get_or_create(
                organization=ngo2,
                title="Donation Request REQ-1002 Approved",
                defaults={
                    "type": "APPROVED",
                    "body": "Fresh Harvest Supermarket approved your request for 20 L of Whole Milk.",
                    "link": "/ngo/claims?request=REQ-1002",
                    "is_read": False,
                },
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded redistribution demo data in all statuses."))
