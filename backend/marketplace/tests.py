from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.admin.sites import site
from rest_framework.test import APITestCase
from rest_framework import status



from accounts.models import Organization, User
from inventory.models import Batch, Category, Product
from marketplace.models import (
    Claim,
    DonationRequest,
    DonationStatusHistory,
    Listing,
    NGORequirement,
    Notification,
    Rating,
    SurplusListing,
)
from marketplace.admin import RatingAdmin





class MarketplaceEndpointsTestCase(APITestCase):
    def setUp(self):
        # 1. Organizations
        self.donor_biz = Organization.objects.create(
            name="Fresh Bakery",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
        )
        self.other_biz = Organization.objects.create(
            name="City Grocers",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
        )
        self.verified_ngo = Organization.objects.create(
            name="Food For All NGO",
            org_type=Organization.Type.NGO,
            is_verified=True,
        )
        self.other_verified_ngo = Organization.objects.create(
            name="Hope Shelter",
            org_type=Organization.Type.NGO,
            is_verified=True,
        )
        self.unverified_ngo = Organization.objects.create(
            name="Unverified Aid",
            org_type=Organization.Type.NGO,
            is_verified=False,
        )

        # 2. Users
        self.ngo_user = User.objects.create_user(
            username="ngo_user",
            email="ngo@test.org",
            password="password123",
            organization=self.verified_ngo,
            role=User.Role.STAFF,
        )
        self.other_ngo_user = User.objects.create_user(
            username="other_ngo_user",
            email="other_ngo@test.org",
            password="password123",
            organization=self.other_verified_ngo,
            role=User.Role.STAFF,
        )
        self.unverified_ngo_user = User.objects.create_user(
            username="unverified_ngo_user",
            email="unverified@test.org",
            password="password123",
            organization=self.unverified_ngo,
            role=User.Role.STAFF,
        )
        self.biz_user = User.objects.create_user(
            username="biz_user",
            email="biz@test.org",
            password="password123",
            organization=self.donor_biz,
            role=User.Role.OWNER,
        )

        # 3. Listings
        now = timezone.now()
        self.listing1 = Listing.objects.create(
            donor=self.donor_biz,
            title="Sourdough Loaves 10kg",
            quantity=10.0,
            pickup_window_start=now - timedelta(days=1),
            pickup_window_end=now + timedelta(days=1),
            status=Listing.Status.COMPLETED,
        )
        self.listing2 = Listing.objects.create(
            donor=self.donor_biz,
            title="Whole Wheat Bagels 5kg",
            quantity=5.0,
            pickup_window_start=now,
            pickup_window_end=now + timedelta(days=2),
            status=Listing.Status.OPEN,
        )

        # 4. Claims
        # Picked-up claim ready to be rated by verified_ngo
        self.claim_picked_up = Claim.objects.create(
            listing=self.listing1,
            ngo=self.verified_ngo,
            status=Claim.Status.PICKED_UP,
            pickup_eta=now - timedelta(hours=2),
        )
        # Pending claim (not picked up yet)
        self.claim_pending = Claim.objects.create(
            listing=self.listing2,
            ngo=self.verified_ngo,
            status=Claim.Status.PENDING,
        )
        # Picked-up claim belonging to other NGO
        self.other_ngo_claim = Claim.objects.create(
            listing=self.listing1,
            ngo=self.other_verified_ngo,
            status=Claim.Status.PICKED_UP,
            pickup_eta=now - timedelta(hours=1),
        )

    # -----------------------------------------------------------------------
    # GET /api/v1/marketplace/ratings/pending/
    # -----------------------------------------------------------------------

    def test_pending_ratings_verified_ngo(self):
        self.client.force_authenticate(user=self.ngo_user)
        response = self.client.get("/api/v1/marketplace/ratings/pending/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only self.claim_picked_up should appear (not claim_pending, not other NGO's claim)
        data = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        self.assertEqual(len(data), 1)
        item = data[0]
        self.assertEqual(item["id"], self.claim_picked_up.id)
        self.assertEqual(item["donor_name"], "Fresh Bakery")
        self.assertEqual(item["item"], "Sourdough Loaves 10kg")
        self.assertEqual(float(item["quantity"]), 10.0)
        self.assertIsNotNone(item["pickup_date"])

    def test_pending_ratings_blocked_for_unverified_ngo(self):
        self.client.force_authenticate(user=self.unverified_ngo_user)
        response = self.client.get("/api/v1/marketplace/ratings/pending/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pending_ratings_blocked_for_business_user(self):
        self.client.force_authenticate(user=self.biz_user)
        response = self.client.get("/api/v1/marketplace/ratings/pending/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -----------------------------------------------------------------------
    # POST /api/v1/marketplace/claims/<id>/rate/
    # -----------------------------------------------------------------------

    def test_rate_claim_success(self):
        self.client.force_authenticate(user=self.ngo_user)
        payload = {
            "stars": 5,
            "comment": "Outstanding food quality and easy pickup!",
            # Malicious client-sent ids to verify they are ignored
            "ngo_id": 9999,
            "business_id": 9999,
        }
        response = self.client.post(
            f"/api/v1/marketplace/claims/{self.claim_picked_up.id}/rate/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["stars"], 5)
        self.assertEqual(response.data["comment"], "Outstanding food quality and easy pickup!")
        # Verify DB record ignores malicious client values
        rating = Rating.objects.get(claim=self.claim_picked_up)
        self.assertEqual(rating.ngo, self.verified_ngo)
        self.assertEqual(rating.business, self.donor_biz)
        self.assertEqual(rating.stars, 5)

    def test_rate_claim_unpicked_up_rejected(self):
        self.client.force_authenticate(user=self.ngo_user)
        response = self.client.post(
            f"/api/v1/marketplace/claims/{self.claim_pending.id}/rate/",
            {"stars": 4, "comment": "Premature rating"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("picked up", response.data["detail"])

    def test_rate_claim_other_ngo_claim_returns_404(self):
        # 404 (not 403) when claim belongs to another organization
        self.client.force_authenticate(user=self.ngo_user)
        response = self.client.post(
            f"/api/v1/marketplace/claims/{self.other_ngo_claim.id}/rate/",
            {"stars": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_rate_claim_unverified_ngo_blocked_403(self):
        self.client.force_authenticate(user=self.unverified_ngo_user)
        response = self.client.post(
            f"/api/v1/marketplace/claims/{self.claim_picked_up.id}/rate/",
            {"stars": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rate_claim_business_user_blocked_403(self):
        self.client.force_authenticate(user=self.biz_user)
        response = self.client.post(
            f"/api/v1/marketplace/claims/{self.claim_picked_up.id}/rate/",
            {"stars": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rate_claim_cannot_rate_twice(self):
        self.client.force_authenticate(user=self.ngo_user)
        self.client.post(
            f"/api/v1/marketplace/claims/{self.claim_picked_up.id}/rate/",
            {"stars": 5},
            format="json",
        )
        response = self.client.post(
            f"/api/v1/marketplace/claims/{self.claim_picked_up.id}/rate/",
            {"stars": 4},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already exists", response.data["detail"])

    def test_rate_claim_invalid_stars_rejected(self):
        self.client.force_authenticate(user=self.ngo_user)
        # Below 1
        res1 = self.client.post(
            f"/api/v1/marketplace/claims/{self.claim_picked_up.id}/rate/",
            {"stars": 0},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)
        # Above 5
        res2 = self.client.post(
            f"/api/v1/marketplace/claims/{self.claim_picked_up.id}/rate/",
            {"stars": 6},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    # -----------------------------------------------------------------------
    # PATCH /api/v1/marketplace/ratings/<id>/
    # -----------------------------------------------------------------------

    def test_patch_rating_within_7_days_allowed(self):
        self.client.force_authenticate(user=self.ngo_user)
        rating = Rating.objects.create(
            claim=self.claim_picked_up,
            stars=3,
            comment="Initial ok review",
        )
        response = self.client.patch(
            f"/api/v1/marketplace/ratings/{rating.id}/",
            {"stars": 4, "comment": "Updated review"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["stars"], 4)
        self.assertEqual(response.data["comment"], "Updated review")
        rating.refresh_from_db()
        self.assertEqual(rating.stars, 4)

    def test_patch_rating_after_7_days_locked(self):
        self.client.force_authenticate(user=self.ngo_user)
        rating = Rating.objects.create(
            claim=self.claim_picked_up,
            stars=3,
            comment="Old review",
        )
        # Backdate created_at to 8 days ago
        Rating.objects.filter(id=rating.id).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        rating.refresh_from_db()

        response = self.client.patch(
            f"/api/v1/marketplace/ratings/{rating.id}/",
            {"stars": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("locked", response.data["detail"])

    def test_patch_rating_other_ngo_returns_404(self):
        self.client.force_authenticate(user=self.ngo_user)
        other_rating = Rating.objects.create(
            claim=self.other_ngo_claim,
            stars=5,
        )
        response = self.client.patch(
            f"/api/v1/marketplace/ratings/{other_rating.id}/",
            {"stars": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -----------------------------------------------------------------------
    # GET /api/v1/marketplace/ratings/mine/
    # -----------------------------------------------------------------------

    def test_get_my_ratings(self):
        self.client.force_authenticate(user=self.ngo_user)
        Rating.objects.create(
            claim=self.claim_picked_up,
            stars=5,
            comment="Great donor!",
        )
        response = self.client.get("/api/v1/marketplace/ratings/mine/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Paginated response
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["stars"], 5)

    # -----------------------------------------------------------------------
    # GET /api/v1/marketplace/businesses/<id>/ratings/
    # -----------------------------------------------------------------------

    def test_business_ratings_aggregation_and_hidden_excluded(self):
        # Create ratings for donor_biz:
        # 1. 5 stars from verified_ngo
        Rating.objects.create(
            claim=self.claim_picked_up,
            stars=5,
            comment="Review 1",
        )
        # 2. 4 stars from other_verified_ngo
        Rating.objects.create(
            claim=self.other_ngo_claim,
            stars=4,
            comment="Review 2",
        )
        # 3. 1 star hidden rating (moderated) on listing2
        claim3 = Claim.objects.create(
            listing=self.listing2,
            ngo=self.verified_ngo,
            status=Claim.Status.PICKED_UP,
        )
        Rating.objects.create(
            claim=claim3,
            stars=1,
            comment="Hidden spam review",
            is_hidden=True,
        )

        response = self.client.get(f"/api/v1/marketplace/businesses/{self.donor_biz.id}/ratings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        # Average: (5 + 4) / 2 = 4.5
        self.assertEqual(data["rating_avg"], 4.5)
        # Count excludes hidden: exactly 2
        self.assertEqual(data["rating_count"], 2)
        # Breakdown check
        self.assertEqual(data["breakdown"]["5"], 1)
        self.assertEqual(data["breakdown"]["4"], 1)
        self.assertEqual(data["breakdown"]["1"], 0)  # Hidden review excluded!
        # Recent reviews check
        self.assertEqual(len(data["recent_reviews"]), 2)
        comments = [r["comment"] for r in data["recent_reviews"]]
        self.assertNotIn("Hidden spam review", comments)

    # -----------------------------------------------------------------------
    # Listing and Feed annotated donor rating_avg and rating_count
    # -----------------------------------------------------------------------

    def test_listings_and_feed_annotated_with_donor_ratings(self):
        Rating.objects.create(
            claim=self.claim_picked_up,
            stars=4,
        )
        response = self.client.get("/api/v1/marketplace/listings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        item = [d for d in data if d["id"] == self.listing1.id][0]
        self.assertEqual(item["donor_rating_avg"], 4.0)
        self.assertEqual(item["donor_rating_count"], 1)

    # -----------------------------------------------------------------------
    # Database-level CheckConstraint tests
    # -----------------------------------------------------------------------

    def test_database_check_constraint_rejects_stars_outside_1_to_5(self):
        from django.db import IntegrityError, transaction
        # Stars = 0 should trigger DB CheckConstraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Rating.objects.create(
                    claim=self.claim_picked_up,
                    stars=0,
                )

        # Stars = 6 should trigger DB CheckConstraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Rating.objects.create(
                    claim=self.claim_picked_up,
                    stars=6,
                )

    # -----------------------------------------------------------------------
    # Client-sent business or ngo ids are ignored
    # -----------------------------------------------------------------------

    def test_client_sent_business_or_ngo_ids_are_ignored(self):
        self.client.force_authenticate(user=self.ngo_user)
        # Attempt to spoof business to other_biz and ngo to other_verified_ngo
        payload = {
            "stars": 4,
            "comment": "Nice work",
            "business": self.other_biz.id,
            "business_id": self.other_biz.id,
            "ngo": self.other_verified_ngo.id,
            "ngo_id": self.other_verified_ngo.id,
        }
        response = self.client.post(
            f"/api/v1/marketplace/claims/{self.claim_picked_up.id}/rate/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        rating = Rating.objects.get(claim=self.claim_picked_up)
        # Must be tied to the authentic claim's donor and ngo
        self.assertEqual(rating.business_id, self.donor_biz.id)
        self.assertEqual(rating.ngo_id, self.verified_ngo.id)
        self.assertNotEqual(rating.business_id, self.other_biz.id)
        self.assertNotEqual(rating.ngo_id, self.other_verified_ngo.id)

    # -----------------------------------------------------------------------
    # Business cannot call NGO rating endpoints (all of them)
    # -----------------------------------------------------------------------

    def test_business_cannot_call_my_ratings(self):
        self.client.force_authenticate(user=self.biz_user)
        response = self.client.get("/api/v1/marketplace/ratings/mine/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_business_cannot_patch_rating(self):
        rating = Rating.objects.create(
            claim=self.claim_picked_up,
            stars=4,
        )
        self.client.force_authenticate(user=self.biz_user)
        response = self.client.patch(
            f"/api/v1/marketplace/ratings/{rating.id}/",
            {"stars": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -----------------------------------------------------------------------
    # Unverified NGO blocked across all NGO rating endpoints
    # -----------------------------------------------------------------------

    def test_unverified_ngo_cannot_call_my_ratings(self):
        self.client.force_authenticate(user=self.unverified_ngo_user)
        response = self.client.get("/api/v1/marketplace/ratings/mine/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unverified_ngo_cannot_patch_rating(self):
        rating = Rating.objects.create(
            claim=self.claim_picked_up,
            stars=4,
        )
        self.client.force_authenticate(user=self.unverified_ngo_user)
        response = self.client.patch(
            f"/api/v1/marketplace/ratings/{rating.id}/",
            {"stars": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -----------------------------------------------------------------------
    # Hidden reviews excluded from lists
    # -----------------------------------------------------------------------

    def test_hidden_reviews_excluded_from_my_ratings_list(self):
        self.client.force_authenticate(user=self.ngo_user)
        # Visible rating
        Rating.objects.create(
            claim=self.claim_picked_up,
            stars=5,
            comment="Visible review",
            is_hidden=False,
        )
        # Hidden rating on another claim
        claim2 = Claim.objects.create(
            listing=self.listing2,
            ngo=self.verified_ngo,
            status=Claim.Status.PICKED_UP,
        )
        Rating.objects.create(
            claim=claim2,
            stars=1,
            comment="Hidden by moderation",
            is_hidden=True,
        )
        response = self.client.get("/api/v1/marketplace/ratings/mine/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["comment"], "Visible review")

    # -----------------------------------------------------------------------
    # Admin hide action registered
    # -----------------------------------------------------------------------

    def test_rating_admin_hide_action(self):
        rating_admin = RatingAdmin(Rating, site)
        self.assertIn("hide_ratings", rating_admin.actions)

    def test_expire_stale_listings_cancels_past_listings(self):
        from marketplace.tasks import expire_stale_listings
        now = timezone.now()
        past_listing = Listing.objects.create(
            donor=self.donor_biz,
            title="Past Bread",
            quantity=5,
            pickup_window_start=now - timedelta(hours=3),
            pickup_window_end=now - timedelta(hours=1),
            status=Listing.Status.OPEN,
        )
        future_listing = Listing.objects.create(
            donor=self.donor_biz,
            title="Fresh Croissants",
            quantity=10,
            pickup_window_start=now,
            pickup_window_end=now + timedelta(hours=2),
            status=Listing.Status.OPEN,
        )

        expired_count = expire_stale_listings()
        self.assertEqual(expired_count, 1)

        past_listing.refresh_from_db()
        future_listing.refresh_from_db()
        self.assertEqual(past_listing.status, Listing.Status.CANCELLED)
        self.assertEqual(future_listing.status, Listing.Status.OPEN)


class MarketplaceRedistributionModelTests(TestCase):
    def setUp(self):
        self.donor = Organization.objects.create(
            name="Donor Bakery",
            org_type=Organization.Type.BUSINESS,
            address="10 Baker St",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
        )
        self.ngo = Organization.objects.create(
            name="Relief NGO",
            org_type=Organization.Type.NGO,
            address="20 Community Rd",
            latitude=Decimal("12.966700"),
            longitude=Decimal("77.601200"),
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        from inventory.models import Category
        self.cat = Category.objects.create(name="Bakery Cat", perishability_risk=Category.Risk.MEDIUM)
        self.now = timezone.now()

    def test_surplus_listing_check_constraints_and_properties(self):
        from django.db import IntegrityError, transaction
        from marketplace.models import SurplusListing
        # 1. quantity_offered must be > 0
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SurplusListing.objects.create(
                    donor=self.donor,
                    title="Invalid Qty",
                    quantity_offered=Decimal("0.000"),
                    available_from=self.now,
                    available_until=self.now + timedelta(hours=2),
                )

        # 2. available_until must be > available_from
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SurplusListing.objects.create(
                    donor=self.donor,
                    title="Invalid Time",
                    quantity_offered=Decimal("10.000"),
                    available_from=self.now + timedelta(hours=2),
                    available_until=self.now,
                )

        # 3. available_until may not exceed safe_until
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SurplusListing.objects.create(
                    donor=self.donor,
                    title="Exceeds Safe",
                    quantity_offered=Decimal("10.000"),
                    available_from=self.now,
                    available_until=self.now + timedelta(hours=6),
                    safe_until=self.now + timedelta(hours=3),
                )

        # 4. Valid listing auto-fills location defaults
        listing = SurplusListing.objects.create(
            donor=self.donor,
            title="Valid Buns",
            quantity_offered=Decimal("20.000"),
            available_from=self.now,
            available_until=self.now + timedelta(hours=4),
        )
        self.assertEqual(listing.pickup_address, "10 Baker St")
        self.assertEqual(listing.latitude, Decimal("12.971600"))
        self.assertEqual(listing.remaining_quantity, Decimal("20.000"))

    def test_ngo_requirement_check_constraints(self):
        from django.db import IntegrityError, transaction
        from marketplace.models import NGORequirement
        # 1. max_quantity must be >= min_quantity
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NGORequirement.objects.create(
                    ngo=self.ngo,
                    title="Bad Qty Req",
                    min_quantity=Decimal("50.000"),
                    max_quantity=Decimal("10.000"),
                )

        # 2. radius_km must be > 0
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NGORequirement.objects.create(
                    ngo=self.ngo,
                    title="Bad Radius Req",
                    min_quantity=Decimal("5.000"),
                    max_quantity=Decimal("20.000"),
                    radius_km=Decimal("0.00"),
                )

    def test_donation_request_code_generation_and_constraints(self):
        from django.db import IntegrityError, transaction
        from marketplace.models import SurplusListing, DonationRequest
        listing = SurplusListing.objects.create(
            donor=self.donor,
            title="Sourdough Loaves",
            quantity_offered=Decimal("30.000"),
            available_from=self.now,
            available_until=self.now + timedelta(hours=6),
        )

        # 1. proposed_pickup_end must be > proposed_pickup_start
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DonationRequest.objects.create(
                    listing=listing,
                    ngo=self.ngo,
                    quantity_requested=Decimal("10.000"),
                    proposed_pickup_start=self.now + timedelta(hours=3),
                    proposed_pickup_end=self.now + timedelta(hours=1),
                )

        # 2. Valid request auto-generates REQ-#### code
        req = DonationRequest.objects.create(
            listing=listing,
            ngo=self.ngo,
            quantity_requested=Decimal("10.000"),
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
        )
        self.assertTrue(req.code.startswith("REQ-"))
        self.assertEqual(req.status, DonationRequest.Status.REQUESTED)

    def test_partial_unique_constraint_blocks_concurrent_active_requests(self):
        from django.db import IntegrityError, transaction
        from marketplace.models import SurplusListing, DonationRequest
        listing = SurplusListing.objects.create(
            donor=self.donor,
            title="Pastry Crates",
            quantity_offered=Decimal("25.000"),
            available_from=self.now,
            available_until=self.now + timedelta(hours=6),
        )

        # Request 1: Active (REQUESTED)
        DonationRequest.objects.create(
            listing=listing,
            ngo=self.ngo,
            quantity_requested=Decimal("10.000"),
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
            status=DonationRequest.Status.REQUESTED,
        )

        # Request 2: Second active request by same NGO for same listing must fail
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DonationRequest.objects.create(
                    listing=listing,
                    ngo=self.ngo,
                    quantity_requested=Decimal("5.000"),
                    proposed_pickup_start=self.now + timedelta(hours=1),
                    proposed_pickup_end=self.now + timedelta(hours=3),
                    status=DonationRequest.Status.REQUESTED,
                )

    def test_terminal_status_allows_new_request(self):
        from marketplace.models import SurplusListing, DonationRequest
        listing = SurplusListing.objects.create(
            donor=self.donor,
            title="Apple Pies",
            quantity_offered=Decimal("15.000"),
            available_from=self.now,
            available_until=self.now + timedelta(hours=6),
        )

        # Request 1: REJECTED (terminal)
        DonationRequest.objects.create(
            listing=listing,
            ngo=self.ngo,
            quantity_requested=Decimal("10.000"),
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
            status=DonationRequest.Status.REJECTED,
        )

        # Request 2: Creating a new request is now allowed
        req2 = DonationRequest.objects.create(
            listing=listing,
            ngo=self.ngo,
            quantity_requested=Decimal("5.000"),
            proposed_pickup_start=self.now + timedelta(hours=2),
            proposed_pickup_end=self.now + timedelta(hours=4),
            status=DonationRequest.Status.REQUESTED,
        )
        self.assertIsNotNone(req2.id)

    def test_donation_status_history_and_notification(self):
        from marketplace.models import SurplusListing, DonationRequest, DonationStatusHistory, Notification
        listing = SurplusListing.objects.create(
            donor=self.donor,
            title="Cookies",
            quantity_offered=Decimal("10.000"),
            available_from=self.now,
            available_until=self.now + timedelta(hours=4),
        )
        req = DonationRequest.objects.create(
            listing=listing,
            ngo=self.ngo,
            quantity_requested=Decimal("5.000"),
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=2),
        )

        hist = DonationStatusHistory.objects.create(
            request=req,
            from_status="",
            to_status="REQUESTED",
            note="Initial request",
        )
        self.assertEqual(hist.to_status, "REQUESTED")

        notif = Notification.objects.create(
            organization=self.donor,
            type="NEW_REQUEST",
            title="New Donation Request",
            body="You have a new request.",
            is_read=False,
        )
        self.assertEqual(notif.type, "NEW_REQUEST")
        self.assertFalse(notif.is_read)


# ===========================================================================
# TASK 2: DONATION LIFECYCLE SERVICE & STATE MACHINE TESTS
# ===========================================================================

class DonationLifecycleServicesTestCase(APITestCase):
    def setUp(self):
        self.now = timezone.now()

        # Organizations
        self.donor_biz = Organization.objects.create(
            name="Green Valley Foods",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.other_biz = Organization.objects.create(
            name="Sunrise Bakers",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.verified_ngo = Organization.objects.create(
            name="Daily Bread NGO",
            org_type=Organization.Type.NGO,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.other_ngo = Organization.objects.create(
            name="City Relief NGO",
            org_type=Organization.Type.NGO,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.unverified_ngo = Organization.objects.create(
            name="Unverified Foundation",
            org_type=Organization.Type.NGO,
            is_verified=False,
            verification_status=Organization.VerificationStatus.PENDING,
        )
        self.suspended_ngo = Organization.objects.create(
            name="Suspended Aid",
            org_type=Organization.Type.NGO,
            is_verified=True,
            verification_status=Organization.VerificationStatus.SUSPENDED,
        )

        # Users
        self.donor_user = User.objects.create_user(
            username="green_donor",
            email="donor@greenvalley.com",
            password="password123",
            organization=self.donor_biz,
            role=User.Role.OWNER,
        )
        self.other_biz_user = User.objects.create_user(
            username="sunrise_user",
            email="user@sunrise.com",
            password="password123",
            organization=self.other_biz,
            role=User.Role.STAFF,
        )
        self.ngo_user = User.objects.create_user(
            username="daily_ngo_user",
            email="user@dailybread.org",
            password="password123",
            organization=self.verified_ngo,
            role=User.Role.STAFF,
        )
        self.other_ngo_user = User.objects.create_user(
            username="city_ngo_user",
            email="user@cityrelief.org",
            password="password123",
            organization=self.other_ngo,
            role=User.Role.STAFF,
        )
        self.unverified_ngo_user = User.objects.create_user(
            username="unverified_user",
            email="user@unverified.org",
            password="password123",
            organization=self.unverified_ngo,
            role=User.Role.STAFF,
        )
        self.suspended_ngo_user = User.objects.create_user(
            username="suspended_user",
            email="user@suspended.org",
            password="password123",
            organization=self.suspended_ngo,
            role=User.Role.STAFF,
        )

        # Inventory Setup
        from inventory.models import Category, Product, Batch
        self.cat, _ = Category.objects.get_or_create(name="Dairy")

        self.product = Product.objects.create(
            organization=self.donor_biz,
            name="Fresh Milk 1L",
            sku="MILK-001",
            unit="L",
            category=self.cat,
        )
        self.batch = Batch.objects.create(
            organization=self.donor_biz,
            product=self.product,
            batch_code="B-MILK-100",
            quantity=Decimal("20.000"),
            reserved_quantity=Decimal("0.000"),
            received_date=self.now.date(),
            expiry_date=(self.now + timedelta(days=5)).date(),
            status=Batch.Status.ACTIVE,
        )

        # Marketplace Surplus Listing
        self.listing = SurplusListing.objects.create(
            donor=self.donor_biz,
            batch=self.batch,
            title="Fresh Milk Surplus",
            quantity_offered=Decimal("20.000"),
            quantity_reserved=Decimal("0.000"),
            unit="L",
            available_from=self.now - timedelta(hours=1),
            available_until=self.now + timedelta(hours=24),
            safe_until=self.now + timedelta(hours=36),
            status=SurplusListing.Status.OPEN,
        )

    def test_full_happy_path_lifecycle(self):
        from marketplace.services import (
            create_donation_request,
            approve_donation_request,
            mark_in_transit,
            mark_collected,
            confirm_receipt,
        )
        from inventory.models import StockTransaction

        # 1. NGO creates request for 20 units
        pickup_start = self.now + timedelta(hours=1)
        pickup_end = self.now + timedelta(hours=3)
        req = create_donation_request(
            user=self.ngo_user,
            listing_id=self.listing.id,
            quantity_requested="20.000",
            proposed_pickup_start=pickup_start,
            proposed_pickup_end=pickup_end,
            note="For evening shelter dinner",
        )
        self.assertEqual(req.status, DonationRequest.Status.REQUESTED)
        self.assertEqual(req.quantity_requested, Decimal("20.000"))
        # Verify creating a request does NOT reserve anything
        self.listing.refresh_from_db()
        self.batch.refresh_from_db()
        self.assertEqual(self.listing.quantity_reserved, Decimal("0.000"))
        self.assertEqual(self.batch.reserved_quantity, Decimal("0.000"))

        # 2. Donor approves the request with same proposed window
        app_req = approve_donation_request(
            user=self.donor_user,
            request_id_or_code=req.id,
            quantity_approved="20.000",
            pickup_start=pickup_start,
            pickup_end=pickup_end,
        )
        # Directly goes to SCHEDULED when proposed window is accepted
        self.assertEqual(app_req.status, DonationRequest.Status.SCHEDULED)
        self.assertEqual(app_req.quantity_approved, Decimal("20.000"))

        # Accounting: Check reservations
        self.listing.refresh_from_db()
        self.batch.refresh_from_db()
        self.assertEqual(self.listing.quantity_reserved, Decimal("20.000"))
        self.assertEqual(self.listing.status, SurplusListing.Status.FULLY_RESERVED)
        self.assertEqual(self.batch.reserved_quantity, Decimal("20.000"))
        self.assertEqual(self.batch.sellable_quantity, Decimal("0.000"))

        # 3. NGO marks IN_TRANSIT (within 2h of pickup_start)
        trans_req = mark_in_transit(user=self.ngo_user, request_id_or_code=req.code)
        self.assertEqual(trans_req.status, DonationRequest.Status.IN_TRANSIT)
        self.assertIsNotNone(trans_req.in_transit_at)

        # 4. Donor marks COLLECTED (20 units handed over)
        col_req = mark_collected(user=self.donor_user, request_id_or_code=req.id, quantity_collected="20.000")
        self.assertEqual(col_req.status, DonationRequest.Status.COLLECTED)
        self.assertEqual(col_req.quantity_collected, Decimal("20.000"))

        # Accounting: Reservation converted into real deduction
        self.batch.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(self.batch.quantity, Decimal("0.000"))
        self.assertEqual(self.batch.reserved_quantity, Decimal("0.000"))
        self.assertEqual(self.batch.status, Batch.Status.DONATED)
        self.assertEqual(self.listing.quantity_reserved, Decimal("0.000"))
        self.assertEqual(self.listing.status, SurplusListing.Status.COMPLETED)

        # Ledger: StockTransaction created
        txn = StockTransaction.objects.filter(batch=self.batch, external_id=req.code).first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.txn_type, StockTransaction.Type.DONATED)
        self.assertEqual(txn.quantity, Decimal("20.000"))
        self.assertEqual(txn.source, "DONATION")

        # 5. NGO confirms receipt
        comp_req = confirm_receipt(user=self.ngo_user, request_id_or_code=req.code)
        self.assertEqual(comp_req.status, DonationRequest.Status.COMPLETED)
        self.assertIsNotNone(comp_req.completed_at)

        # Check status history
        histories = list(comp_req.status_history.order_by("created_at"))
        to_statuses = [h.to_status for h in histories]
        self.assertIn(DonationRequest.Status.REQUESTED, to_statuses)
        self.assertIn(DonationRequest.Status.APPROVED, to_statuses)
        self.assertIn(DonationRequest.Status.SCHEDULED, to_statuses)
        self.assertIn(DonationRequest.Status.IN_TRANSIT, to_statuses)
        self.assertIn(DonationRequest.Status.COLLECTED, to_statuses)
        self.assertIn(DonationRequest.Status.COMPLETED, to_statuses)

    def test_modified_pickup_window_flow(self):
        from marketplace.services import (
            create_donation_request,
            approve_donation_request,
            confirm_schedule_by_ngo,
        )

        pickup_start = self.now + timedelta(hours=1)
        pickup_end = self.now + timedelta(hours=3)
        req = create_donation_request(
            user=self.ngo_user,
            listing_id=self.listing.id,
            quantity_requested="10.000",
            proposed_pickup_start=pickup_start,
            proposed_pickup_end=pickup_end,
        )

        # Donor changes pickup window
        new_start = self.now + timedelta(hours=4)
        new_end = self.now + timedelta(hours=6)
        app_req = approve_donation_request(
            user=self.donor_user,
            request_id_or_code=req.id,
            quantity_approved="10.000",
            pickup_start=new_start,
            pickup_end=new_end,
        )
        # Because pickup window was modified, request stays APPROVED until NGO confirms
        self.assertEqual(app_req.status, DonationRequest.Status.APPROVED)
        self.assertEqual(app_req.confirmed_pickup_start, new_start)
        self.assertEqual(app_req.confirmed_pickup_end, new_end)

        # Stock is still reserved
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.reserved_quantity, Decimal("10.000"))

        # NGO confirms new window
        sched_req = confirm_schedule_by_ngo(user=self.ngo_user, request_id_or_code=req.code)
        self.assertEqual(sched_req.status, DonationRequest.Status.SCHEDULED)
        self.assertIsNotNone(sched_req.scheduled_at)

    def test_partial_quantity_approval_and_collection(self):
        from marketplace.services import (
            create_donation_request,
            approve_donation_request,
            mark_collected,
        )

        # NGO asks for 15
        pickup_start = self.now + timedelta(hours=1)
        pickup_end = self.now + timedelta(hours=3)
        req = create_donation_request(
            user=self.ngo_user,
            listing_id=self.listing.id,
            quantity_requested="15.000",
            proposed_pickup_start=pickup_start,
            proposed_pickup_end=pickup_end,
        )

        # Donor approves only 10
        app_req = approve_donation_request(
            user=self.donor_user,
            request_id_or_code=req.id,
            quantity_approved="10.000",
            pickup_start=pickup_start,
            pickup_end=pickup_end,
        )
        self.assertEqual(app_req.quantity_approved, Decimal("10.000"))

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity_reserved, Decimal("10.000"))
        # 10 reserved out of 20 offered -> 10 remains, still OPEN
        self.assertEqual(self.listing.remaining_quantity, Decimal("10.000"))
        self.assertEqual(self.listing.status, SurplusListing.Status.OPEN)

        # At pickup, NGO can only carry 8
        col_req = mark_collected(
            user=self.donor_user,
            request_id_or_code=req.id,
            quantity_collected="8.000",
        )
        self.assertEqual(col_req.quantity_collected, Decimal("8.000"))

        self.batch.refresh_from_db()
        self.listing.refresh_from_db()
        # Batch: 20 - 8 = 12 remaining; all 10 reserved was freed
        self.assertEqual(self.batch.quantity, Decimal("12.000"))
        self.assertEqual(self.batch.reserved_quantity, Decimal("0.000"))
        self.assertEqual(self.listing.quantity_reserved, Decimal("0.000"))
        self.assertEqual(self.listing.status, SurplusListing.Status.OPEN)

    def test_reject_donation_request(self):
        from marketplace.services import (
            create_donation_request,
            reject_donation_request,
            ValidationLifecycleError,
            TransitionConflictError,
        )

        req = create_donation_request(
            user=self.ngo_user,
            listing_id=self.listing.id,
            quantity_requested="10.000",
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
        )

        # Reject without reason fails
        with self.assertRaises(ValidationLifecycleError):
            reject_donation_request(user=self.donor_user, request_id_or_code=req.id, rejection_reason="")

        # Reject with reason succeeds
        rej_req = reject_donation_request(
            user=self.donor_user,
            request_id_or_code=req.id,
            rejection_reason="Item promised to recurring hospital soup kitchen.",
        )
        self.assertEqual(rej_req.status, DonationRequest.Status.REJECTED)
        self.assertEqual(rej_req.rejection_reason, "Item promised to recurring hospital soup kitchen.")
        self.assertIsNotNone(rej_req.rejected_at)

        # Rejecting a non-REQUESTED request raises TransitionConflictError
        with self.assertRaises(TransitionConflictError):
            reject_donation_request(
                user=self.donor_user,
                request_id_or_code=req.id,
                rejection_reason="Already rejected",
            )

    def test_cancel_donation_request_releases_reservation(self):
        from marketplace.services import (
            create_donation_request,
            approve_donation_request,
            cancel_donation_request,
            TransitionConflictError,
        )

        req = create_donation_request(
            user=self.ngo_user,
            listing_id=self.listing.id,
            quantity_requested="20.000",
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
        )
        approve_donation_request(
            user=self.donor_user,
            request_id_or_code=req.id,
            quantity_approved="20.000",
        )
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, SurplusListing.Status.FULLY_RESERVED)
        self.assertEqual(self.listing.quantity_reserved, Decimal("20.000"))

        # NGO cancels request
        canc_req = cancel_donation_request(
            user=self.ngo_user,
            request_id_or_code=req.code,
            reason="Transport vehicle breakdown",
        )
        self.assertEqual(canc_req.status, DonationRequest.Status.CANCELLED)

        # Reservation is released and listing returns to OPEN
        self.listing.refresh_from_db()
        self.batch.refresh_from_db()
        self.assertEqual(self.listing.quantity_reserved, Decimal("0.000"))
        self.assertEqual(self.listing.status, SurplusListing.Status.OPEN)
        self.assertEqual(self.batch.reserved_quantity, Decimal("0.000"))

        # Cancelling an already cancelled request raises TransitionConflictError
        with self.assertRaises(TransitionConflictError):
            cancel_donation_request(user=self.ngo_user, request_id_or_code=req.code)

    def test_mark_in_transit_restrictions(self):
        from marketplace.services import (
            create_donation_request,
            approve_donation_request,
            mark_in_transit,
            TransitionConflictError,
        )

        # Pickup starts 5 hours in future
        pickup_start = self.now + timedelta(hours=5)
        pickup_end = self.now + timedelta(hours=7)
        req = create_donation_request(
            user=self.ngo_user,
            listing_id=self.listing.id,
            quantity_requested="10.000",
            proposed_pickup_start=pickup_start,
            proposed_pickup_end=pickup_end,
        )
        approve_donation_request(
            user=self.donor_user,
            request_id_or_code=req.id,
            pickup_start=pickup_start,
            pickup_end=pickup_end,
        )

        # Cannot mark in transit >2h before pickup start
        with self.assertRaises(TransitionConflictError):
            mark_in_transit(user=self.ngo_user, request_id_or_code=req.id)

    def test_no_show_rules(self):
        from marketplace.services import (
            create_donation_request,
            approve_donation_request,
            mark_no_show,
            TransitionConflictError,
        )

        # Window in future
        pickup_start = self.now + timedelta(hours=1)
        pickup_end = self.now + timedelta(hours=3)
        req = create_donation_request(
            user=self.ngo_user,
            listing_id=self.listing.id,
            quantity_requested="10.000",
            proposed_pickup_start=pickup_start,
            proposed_pickup_end=pickup_end,
        )
        approve_donation_request(
            user=self.donor_user,
            request_id_or_code=req.id,
            pickup_start=pickup_start,
            pickup_end=pickup_end,
        )

        # Cannot mark no-show before window end
        with self.assertRaises(TransitionConflictError):
            mark_no_show(user=self.donor_user, request_id_or_code=req.id)

        # Move confirmed_pickup_start and confirmed_pickup_end to the past
        req.confirmed_pickup_start = self.now - timedelta(hours=2)
        req.confirmed_pickup_end = self.now - timedelta(minutes=10)
        req.save(update_fields=["confirmed_pickup_start", "confirmed_pickup_end"])


        # Now mark no-show succeeds
        ns_req = mark_no_show(user=self.donor_user, request_id_or_code=req.id)
        self.assertEqual(ns_req.status, DonationRequest.Status.NO_SHOW)
        self.assertIsNotNone(ns_req.no_show_at)

        # Reservations released
        self.listing.refresh_from_db()
        self.batch.refresh_from_db()
        self.assertEqual(self.listing.quantity_reserved, Decimal("0.000"))
        self.assertEqual(self.batch.reserved_quantity, Decimal("0.000"))

    def test_concurrency_race_condition_prevents_overreservation(self):
        from marketplace.services import (
            create_donation_request,
            approve_donation_request,
            TransitionConflictError,
        )

        # Listing has 20 units.
        # NGO 1 requests 15 units.
        req1 = create_donation_request(
            user=self.ngo_user,
            listing_id=self.listing.id,
            quantity_requested="15.000",
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
        )
        # NGO 2 requests 15 units.
        req2 = create_donation_request(
            user=self.other_ngo_user,
            listing_id=self.listing.id,
            quantity_requested="15.000",
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
        )

        # Donor approves req1 for 15 units -> remaining is 5
        approve_donation_request(user=self.donor_user, request_id_or_code=req1.id, quantity_approved="15.000")

        # Donor tries to approve req2 for 15 units -> fails because only 5 remain
        with self.assertRaises(TransitionConflictError):
            approve_donation_request(user=self.donor_user, request_id_or_code=req2.id, quantity_approved="15.000")

    def test_tenant_and_permission_isolation(self):
        from marketplace.services import (
            create_donation_request,
            approve_donation_request,
            cancel_donation_request,
            PermissionDeniedLifecycleError,
            NotFoundLifecycleError,
        )

        # 1. Unverified NGO cannot create request
        with self.assertRaises(PermissionDeniedLifecycleError):
            create_donation_request(
                user=self.unverified_ngo_user,
                listing_id=self.listing.id,
                quantity_requested="5.000",
                proposed_pickup_start=self.now + timedelta(hours=1),
                proposed_pickup_end=self.now + timedelta(hours=3),
            )

        # 2. Suspended NGO cannot create request
        with self.assertRaises(PermissionDeniedLifecycleError):
            create_donation_request(
                user=self.suspended_ngo_user,
                listing_id=self.listing.id,
                quantity_requested="5.000",
                proposed_pickup_start=self.now + timedelta(hours=1),
                proposed_pickup_end=self.now + timedelta(hours=3),
            )

        # 3. Business cannot create request
        with self.assertRaises(PermissionDeniedLifecycleError):
            create_donation_request(
                user=self.donor_user,
                listing_id=self.listing.id,
                quantity_requested="5.000",
                proposed_pickup_start=self.now + timedelta(hours=1),
                proposed_pickup_end=self.now + timedelta(hours=3),
            )

        # 4. Valid request created
        req = create_donation_request(
            user=self.ngo_user,
            listing_id=self.listing.id,
            quantity_requested="5.000",
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
        )

        # 5. NGO user cannot approve request (only business can)
        with self.assertRaises(PermissionDeniedLifecycleError):
            approve_donation_request(user=self.ngo_user, request_id_or_code=req.id)

        # 6. Another business cannot approve request (404 tenant isolation)
        with self.assertRaises(NotFoundLifecycleError):
            approve_donation_request(user=self.other_biz_user, request_id_or_code=req.id)

        # 7. Another NGO cannot cancel request (404 tenant isolation)
        with self.assertRaises(NotFoundLifecycleError):
            cancel_donation_request(user=self.other_ngo_user, request_id_or_code=req.id)

    def test_process_donations_background_job(self):
        from marketplace.services import process_donations

        # 1. Stale REQUESTED request where listing expired
        stale_listing = SurplusListing.objects.create(
            donor=self.donor_biz,
            title="Expired Bread",
            quantity_offered=Decimal("10.000"),
            available_from=self.now - timedelta(hours=10),
            available_until=self.now - timedelta(hours=2),
            status=SurplusListing.Status.OPEN,
        )
        stale_req = DonationRequest.objects.create(
            listing=stale_listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("5.000"),
            status=DonationRequest.Status.REQUESTED,
            proposed_pickup_start=self.now - timedelta(hours=5),
            proposed_pickup_end=self.now - timedelta(hours=3),
        )

        # 2. Stale COLLECTED request older than 24 hours
        stale_collected_req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("2.000"),
            quantity_approved=Decimal("2.000"),
            quantity_collected=Decimal("2.000"),
            status=DonationRequest.Status.COLLECTED,
            collected_at=self.now - timedelta(hours=25),
            proposed_pickup_start=self.now - timedelta(hours=28),
            proposed_pickup_end=self.now - timedelta(hours=26),
        )

        # Run process_donations
        summary = process_donations()
        self.assertGreaterEqual(summary["expired_requests"], 1)
        self.assertGreaterEqual(summary["auto_completed_requests"], 1)
        self.assertGreaterEqual(summary["expired_listings"], 1)

        stale_req.refresh_from_db()
        self.assertEqual(stale_req.status, DonationRequest.Status.EXPIRED)

        stale_collected_req.refresh_from_db()
        self.assertEqual(stale_collected_req.status, DonationRequest.Status.COMPLETED)

        stale_listing.refresh_from_db()
        self.assertEqual(stale_listing.status, SurplusListing.Status.EXPIRED)

        # Idempotency check: running again changes 0 items
        summary2 = process_donations()
        self.assertEqual(summary2["expired_requests"], 0)
        self.assertEqual(summary2["auto_completed_requests"], 0)
        self.assertEqual(summary2["expired_listings"], 0)


# ===========================================================================
# TASK 2: API ENDPOINTS TEST SUITE
# ===========================================================================

class DonationLifecycleAPITestCase(APITestCase):
    def setUp(self):
        self.now = timezone.now()

        # Organizations
        self.donor_biz = Organization.objects.create(
            name="Green Valley Foods",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.other_biz = Organization.objects.create(
            name="Sunrise Bakers",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.verified_ngo = Organization.objects.create(
            name="Daily Bread NGO",
            org_type=Organization.Type.NGO,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.other_ngo = Organization.objects.create(
            name="City Relief NGO",
            org_type=Organization.Type.NGO,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.unverified_ngo = Organization.objects.create(
            name="Unverified Aid",
            org_type=Organization.Type.NGO,
            is_verified=False,
            verification_status=Organization.VerificationStatus.PENDING,
        )

        # Users
        self.donor_user = User.objects.create_user(
            username="donor_api_user",
            email="donor@greenvalley.com",
            password="password123",
            organization=self.donor_biz,
            role=User.Role.OWNER,
        )
        self.other_biz_user = User.objects.create_user(
            username="other_donor_api_user",
            email="donor@sunrise.com",
            password="password123",
            organization=self.other_biz,
            role=User.Role.OWNER,
        )
        self.ngo_user = User.objects.create_user(
            username="ngo_api_user",
            email="ngo@dailybread.org",
            password="password123",
            organization=self.verified_ngo,
            role=User.Role.STAFF,
        )
        self.other_ngo_user = User.objects.create_user(
            username="other_ngo_api_user",
            email="ngo@cityrelief.org",
            password="password123",
            organization=self.other_ngo,
            role=User.Role.STAFF,
        )
        self.unverified_ngo_user = User.objects.create_user(
            username="unverified_api_user",
            email="unverified@aid.org",
            password="password123",
            organization=self.unverified_ngo,
            role=User.Role.STAFF,
        )

        # Inventory & Listing
        from inventory.models import Category, Product, Batch
        self.cat, _ = Category.objects.get_or_create(name="Bakery")

        self.product = Product.objects.create(
            organization=self.donor_biz,
            name="Artisan Bread",
            sku="BREAD-01",
            unit="kg",
            category=self.cat,
        )
        self.batch = Batch.objects.create(
            organization=self.donor_biz,
            product=self.product,
            batch_code="B-BREAD-01",
            quantity=Decimal("30.000"),
            reserved_quantity=Decimal("0.000"),
            received_date=self.now.date(),
            expiry_date=(self.now + timedelta(days=3)).date(),
            status=Batch.Status.ACTIVE,
        )
        self.listing = SurplusListing.objects.create(
            donor=self.donor_biz,
            batch=self.batch,
            title="Fresh Artisan Bread 30kg",
            quantity_offered=Decimal("30.000"),
            quantity_reserved=Decimal("0.000"),
            unit="kg",
            available_from=self.now - timedelta(hours=1),
            available_until=self.now + timedelta(hours=24),
            safe_until=self.now + timedelta(hours=36),
            status=SurplusListing.Status.OPEN,
        )

    def test_api_create_donation_request(self):
        self.client.force_authenticate(user=self.ngo_user)
        payload = {
            "listing": self.listing.id,
            "quantity_requested": "10.000",
            "proposed_pickup_start": (self.now + timedelta(hours=1)).isoformat(),
            "proposed_pickup_end": (self.now + timedelta(hours=3)).isoformat(),
            "note": "For shelter breakfast",
        }
        res = self.client.post("/api/v1/marketplace/requests/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], "REQUESTED")
        self.assertTrue(res.data["code"].startswith("REQ-"))

        # Unverified NGO gets 403 Forbidden
        self.client.force_authenticate(user=self.unverified_ngo_user)
        res_unv = self.client.post("/api/v1/marketplace/requests/", payload, format="json")
        self.assertEqual(res_unv.status_code, status.HTTP_403_FORBIDDEN)

        # Business user gets 403 Forbidden
        self.client.force_authenticate(user=self.donor_user)
        res_biz = self.client.post("/api/v1/marketplace/requests/", payload, format="json")
        self.assertEqual(res_biz.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_list_and_filter_requests(self):
        # Create 2 requests
        req1 = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("5.000"),
            status=DonationRequest.Status.REQUESTED,
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
        )
        req2 = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.other_ngo,
            quantity_requested=Decimal("8.000"),
            status=DonationRequest.Status.SCHEDULED,
            proposed_pickup_start=self.now + timedelta(hours=2),
            proposed_pickup_end=self.now + timedelta(hours=4),
        )

        # Donor sees both requests for its listing
        self.client.force_authenticate(user=self.donor_user)
        res_donor = self.client.get("/api/v1/marketplace/requests/?include_counts=true")
        self.assertEqual(res_donor.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_donor.data["results"]), 2)
        self.assertEqual(res_donor.data["counts"]["all"], 2)
        self.assertEqual(res_donor.data["counts"]["pending"], 1)
        self.assertEqual(res_donor.data["counts"]["scheduled"], 1)

        # NGO user only sees its own request
        self.client.force_authenticate(user=self.ngo_user)
        res_ngo = self.client.get("/api/v1/marketplace/requests/")
        self.assertEqual(res_ngo.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_ngo.data), 1)
        self.assertEqual(res_ngo.data[0]["id"], req1.id)

    def test_api_detail_view_and_tenant_privacy(self):
        req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("5.000"),
            status=DonationRequest.Status.REQUESTED,
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
        )

        # Donor can access
        self.client.force_authenticate(user=self.donor_user)
        res = self.client.get(f"/api/v1/marketplace/requests/{req.code}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["code"], req.code)

        # Other NGO cannot access (404 Not Found)
        self.client.force_authenticate(user=self.other_ngo_user)
        res_404 = self.client.get(f"/api/v1/marketplace/requests/{req.code}/")
        self.assertEqual(res_404.status_code, status.HTTP_404_NOT_FOUND)

        # Other Business cannot access (404 Not Found)
        self.client.force_authenticate(user=self.other_biz_user)
        res_biz_404 = self.client.get(f"/api/v1/marketplace/requests/{req.code}/")
        self.assertEqual(res_biz_404.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_approve_flow(self):
        pickup_start = self.now + timedelta(hours=1)
        pickup_end = self.now + timedelta(hours=3)
        req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("10.000"),
            status=DonationRequest.Status.REQUESTED,
            proposed_pickup_start=pickup_start,
            proposed_pickup_end=pickup_end,
        )

        self.client.force_authenticate(user=self.donor_user)
        res = self.client.post(
            f"/api/v1/marketplace/requests/{req.id}/approve/",
            {"quantity_approved": "10.000"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "SCHEDULED")

        # Double-approval attempts return 409 Conflict
        res_dup = self.client.post(f"/api/v1/marketplace/requests/{req.id}/approve/", format="json")
        self.assertEqual(res_dup.status_code, status.HTTP_409_CONFLICT)

    def test_api_confirm_schedule_by_ngo(self):
        pickup_start = self.now + timedelta(hours=1)
        pickup_end = self.now + timedelta(hours=3)
        req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("10.000"),
            status=DonationRequest.Status.REQUESTED,
            proposed_pickup_start=pickup_start,
            proposed_pickup_end=pickup_end,
        )

        # Donor approves with modified window -> status APPROVED
        self.client.force_authenticate(user=self.donor_user)
        new_start = self.now + timedelta(hours=4)
        new_end = self.now + timedelta(hours=6)
        res_app = self.client.post(
            f"/api/v1/marketplace/requests/{req.id}/approve/",
            {
                "quantity_approved": "10.000",
                "pickup_start": new_start.isoformat(),
                "pickup_end": new_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(res_app.status_code, status.HTTP_200_OK)
        self.assertEqual(res_app.data["status"], "APPROVED")

        # NGO confirms schedule
        self.client.force_authenticate(user=self.ngo_user)
        res_conf = self.client.post(f"/api/v1/marketplace/requests/{req.id}/confirm-schedule/", format="json")
        self.assertEqual(res_conf.status_code, status.HTTP_200_OK)
        self.assertEqual(res_conf.data["status"], "SCHEDULED")

    def test_api_reject_flow(self):
        req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("5.000"),
            status=DonationRequest.Status.REQUESTED,
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
        )

        self.client.force_authenticate(user=self.donor_user)
        # Missing reason -> 400 Bad Request
        res_bad = self.client.post(f"/api/v1/marketplace/requests/{req.id}/reject/", {}, format="json")
        self.assertEqual(res_bad.status_code, status.HTTP_400_BAD_REQUEST)

        # With reason -> 200 OK
        res = self.client.post(
            f"/api/v1/marketplace/requests/{req.id}/reject/",
            {"rejection_reason": "Stock damaged during morning transit."},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "REJECTED")

    def test_api_cancel_flow(self):
        req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("5.000"),
            status=DonationRequest.Status.REQUESTED,
            proposed_pickup_start=self.now + timedelta(hours=1),
            proposed_pickup_end=self.now + timedelta(hours=3),
        )

        self.client.force_authenticate(user=self.ngo_user)
        res = self.client.post(
            f"/api/v1/marketplace/requests/{req.id}/cancel/",
            {"reason": "Event cancelled."},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "CANCELLED")

    def test_api_in_transit_and_collect_and_confirm_receipt(self):
        # 1. Start with SCHEDULED request within 1 hour of pickup
        req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("10.000"),
            quantity_approved=Decimal("10.000"),
            status=DonationRequest.Status.SCHEDULED,
            proposed_pickup_start=self.now + timedelta(minutes=45),
            proposed_pickup_end=self.now + timedelta(hours=2),
            confirmed_pickup_start=self.now + timedelta(minutes=45),
            confirmed_pickup_end=self.now + timedelta(hours=2),
        )
        self.listing.quantity_reserved = Decimal("10.000")
        self.listing.save()
        self.batch.reserved_quantity = Decimal("10.000")
        self.batch.save()

        # 2. NGO marks in-transit
        self.client.force_authenticate(user=self.ngo_user)
        res_trans = self.client.post(f"/api/v1/marketplace/requests/{req.id}/in-transit/", format="json")
        self.assertEqual(res_trans.status_code, status.HTTP_200_OK)
        self.assertEqual(res_trans.data["status"], "IN_TRANSIT")

        # 3. Donor marks collect
        self.client.force_authenticate(user=self.donor_user)
        res_col = self.client.post(
            f"/api/v1/marketplace/requests/{req.id}/collect/",
            {"quantity_collected": "10.000"},
            format="json",
        )
        self.assertEqual(res_col.status_code, status.HTTP_200_OK)
        self.assertEqual(res_col.data["status"], "COLLECTED")

        # 4. NGO confirms receipt
        self.client.force_authenticate(user=self.ngo_user)
        res_comp = self.client.post(f"/api/v1/marketplace/requests/{req.id}/confirm-receipt/", format="json")
        self.assertEqual(res_comp.status_code, status.HTTP_200_OK)
        self.assertEqual(res_comp.data["status"], "COMPLETED")

    def test_api_no_show_flow(self):
        req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("10.000"),
            quantity_approved=Decimal("10.000"),
            status=DonationRequest.Status.SCHEDULED,
            proposed_pickup_start=self.now - timedelta(hours=3),
            proposed_pickup_end=self.now + timedelta(hours=1),
            confirmed_pickup_start=self.now - timedelta(hours=3),
            confirmed_pickup_end=self.now + timedelta(hours=1),
        )

        self.listing.quantity_reserved = Decimal("10.000")
        self.listing.save()
        self.batch.reserved_quantity = Decimal("10.000")
        self.batch.save()

        self.client.force_authenticate(user=self.donor_user)
        # While pickup window hasn't ended -> 409 Conflict
        res_early = self.client.post(f"/api/v1/marketplace/requests/{req.id}/no-show/", format="json")
        self.assertEqual(res_early.status_code, status.HTTP_409_CONFLICT)

        # After pickup window ends -> 200 OK
        req.confirmed_pickup_end = self.now - timedelta(minutes=15)
        req.save(update_fields=["confirmed_pickup_end"])

        res_ns = self.client.post(f"/api/v1/marketplace/requests/{req.id}/no-show/", format="json")
        self.assertEqual(res_ns.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ns.data["status"], "NO_SHOW")

    def test_management_command_process_donations(self):
        from django.core.management import call_command
        import io

        out = io.StringIO()
        call_command("process_donations", stdout=out)
        output = out.getvalue()
        self.assertIn("Successfully processed donations", output)


# ===========================================================================
# TASK 3: MATCHING ENGINE TEST SUITES
# ===========================================================================

class MatchingEngineServicesTestCase(TestCase):
    """
    Unit and integration tests for the SurplusSync matching engine:
    Haversine distance, compatibility matrix, multi-factor scoring,
    and batch notification generation.
    """

    def setUp(self):
        self.now = timezone.now()

        # Donor organization in Central Bangalore (12.9716, 77.5946)
        self.donor_org = Organization.objects.create(
            name="Bangalore Fresh Mart",
            org_type=Organization.Type.BUSINESS,
            address="MG Road, Bangalore",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )

        # NGO 1: Nearby in Indiranagar (~3.5 km away), verified, radius 10 km
        self.nearby_ngo = Organization.objects.create(
            name="Indiranagar Food Relief",
            org_type=Organization.Type.NGO,
            address="100ft Road, Indiranagar",
            latitude=Decimal("12.978400"),
            longitude=Decimal("77.640800"),
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )

        # NGO 2: Far in Whitefield (~16.8 km away), verified, radius 10 km
        self.far_ngo = Organization.objects.create(
            name="Whitefield Hope Foundation",
            org_type=Organization.Type.NGO,
            address="ITPL Road, Whitefield",
            latitude=Decimal("12.969800"),
            longitude=Decimal("77.749900"),
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )

        # NGO 3: Unverified NGO
        self.unverified_ngo = Organization.objects.create(
            name="Unverified Shelter",
            org_type=Organization.Type.NGO,
            address="Koramangala",
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
            is_verified=False,
            verification_status=Organization.VerificationStatus.PENDING,
        )

        self.category_bakery, _ = Category.objects.get_or_create(name="Bakery & Pastries")
        self.category_dairy, _ = Category.objects.get_or_create(name="Dairy Products")

        # Open Listing from Donor: 50 kg Bread, Bakery, not cooked, expires in 12 hours
        self.listing = SurplusListing.objects.create(
            donor=self.donor_org,
            title="Surplus Sourdough Bread",
            category=self.category_bakery,
            quantity_offered=Decimal("50.000"),
            quantity_reserved=Decimal("0.000"),
            unit="kg",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            available_from=self.now,
            available_until=self.now + timedelta(hours=12),
            safe_until=self.now + timedelta(hours=14),
            is_cooked=False,
            status=SurplusListing.Status.OPEN,
        )

    def test_haversine_distance_exactness(self):
        from marketplace.matching import haversine_distance

        # Same coordinates -> 0.0 km
        d0 = haversine_distance(12.9716, 77.5946, 12.9716, 77.5946)
        self.assertEqual(d0, 0.0)

        # None or invalid coordinates -> infinity
        self.assertEqual(haversine_distance(None, 77.5946, 12.9716, 77.5946), float("inf"))
        self.assertEqual(haversine_distance("bad", 77.5946, 12.9716, 77.5946), float("inf"))

        # Bangalore Center to Whitefield: ~16.8 km
        dist = haversine_distance(12.9716, 77.5946, 12.9698, 77.7499)
        self.assertTrue(16.0 <= dist <= 17.5, f"Expected ~16.8km, got {dist}")

        # London to Paris: ~343 km
        london_paris = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)
        self.assertTrue(335.0 <= london_paris <= 350.0, f"Expected ~343km, got {london_paris}")

    def test_geographic_radius_filtering(self):
        from marketplace.matching import find_matching_requirements_for_listing

        # Requirement 1: Nearby NGO (~5 km away, radius 10 km) -> matches
        req_nearby = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Bread for Breakfast",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("60.000"),
            radius_km=Decimal("10.00"),
            is_active=True,
        )

        # Requirement 2: Far NGO (~16.8 km away, radius 10 km) -> out of radius
        req_far = NGORequirement.objects.create(
            ngo=self.far_ngo,
            title="Whitefield Bread Program",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("60.000"),
            radius_km=Decimal("10.00"),
            is_active=True,
        )

        matches = find_matching_requirements_for_listing(self.listing, compatible_only=True)
        match_req_ids = [m["requirement_id"] for m in matches]
        self.assertIn(req_nearby.id, match_req_ids)
        self.assertNotIn(req_far.id, match_req_ids)

    def test_category_compatibility_filtering(self):
        from marketplace.matching import find_matching_requirements_for_listing

        # Req Dairy only: listing is Bakery -> Incompatible
        req_dairy = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Milk & Yogurt Needed",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("60.000"),
            radius_km=Decimal("15.00"),
            is_active=True,
        )
        req_dairy.categories.add(self.category_dairy)

        # Req Bakery: matches listing
        req_bakery = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Bakery Items Needed",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("60.000"),
            radius_km=Decimal("15.00"),
            is_active=True,
        )
        req_bakery.categories.add(self.category_bakery)

        # Req Any category: matches listing
        req_any = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Any Staple Food",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("60.000"),
            radius_km=Decimal("15.00"),
            is_active=True,
        )

        matches = find_matching_requirements_for_listing(self.listing, compatible_only=True)
        match_req_ids = [m["requirement_id"] for m in matches]
        self.assertIn(req_bakery.id, match_req_ids)
        self.assertIn(req_any.id, match_req_ids)
        self.assertNotIn(req_dairy.id, match_req_ids)

    def test_cooked_food_compatibility(self):
        from marketplace.matching import evaluate_compatibility

        cooked_listing = SurplusListing.objects.create(
            donor=self.donor_org,
            title="Hot Rice & Curry",
            quantity_offered=Decimal("20.000"),
            unit="kg",
            available_from=self.now,
            available_until=self.now + timedelta(hours=4),
            is_cooked=True,
            status=SurplusListing.Status.OPEN,
        )

        req_no_cooked = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Packaged Items Only",
            min_quantity=Decimal("5.000"),
            max_quantity=Decimal("30.000"),
            accepts_cooked_food=False,
            is_active=True,
        )

        req_accepts_cooked = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Community Kitchen",
            min_quantity=Decimal("5.000"),
            max_quantity=Decimal("30.000"),
            accepts_cooked_food=True,
            is_active=True,
        )

        compat1, reasons1 = evaluate_compatibility(cooked_listing, req_no_cooked, 3.5)
        self.assertFalse(compat1)
        self.assertTrue(any("cooked food" in r for r in reasons1))

        compat2, _ = evaluate_compatibility(cooked_listing, req_accepts_cooked, 3.5)
        self.assertTrue(compat2)

    def test_quantity_threshold_compatibility(self):
        from marketplace.matching import evaluate_compatibility

        # Listing has 10 kg remaining
        small_listing = SurplusListing.objects.create(
            donor=self.donor_org,
            title="Small Bread Pack",
            quantity_offered=Decimal("10.000"),
            unit="kg",
            available_from=self.now,
            available_until=self.now + timedelta(hours=10),
            status=SurplusListing.Status.OPEN,
        )

        # Requirement expects minimum 25 kg
        large_req = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Large Shelter Banquet",
            min_quantity=Decimal("25.000"),
            max_quantity=Decimal("100.000"),
            is_active=True,
        )

        compat, reasons = evaluate_compatibility(small_listing, large_req, 3.5)
        self.assertFalse(compat)
        self.assertTrue(any("below requirement minimum" in r for r in reasons))

    def test_urgency_scoring(self):
        from marketplace.matching import compute_match_score

        req = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Breakfast Daily",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("60.000"),
            radius_km=Decimal("10.00"),
            is_active=True,
        )

        # Urgent listing: expires in 3 hours
        urgent_listing = SurplusListing.objects.create(
            donor=self.donor_org,
            title="Urgent Sandwiches",
            quantity_offered=Decimal("20.000"),
            unit="kg",
            available_from=self.now,
            available_until=self.now + timedelta(hours=3),
            safe_until=self.now + timedelta(hours=3),
            status=SurplusListing.Status.OPEN,
        )

        # Relaxed listing: expires in 40 hours
        relaxed_listing = SurplusListing.objects.create(
            donor=self.donor_org,
            title="Long Shelf Bread",
            quantity_offered=Decimal("20.000"),
            unit="kg",
            available_from=self.now,
            available_until=self.now + timedelta(hours=40),
            safe_until=self.now + timedelta(hours=48),
            status=SurplusListing.Status.OPEN,
        )

        score_urgent = compute_match_score(urgent_listing, req, 3.5)
        score_relaxed = compute_match_score(relaxed_listing, req, 3.5)

        self.assertEqual(score_urgent["breakdown"]["urgency_score"], 100.0)
        self.assertEqual(score_relaxed["breakdown"]["urgency_score"], 30.0)
        self.assertGreater(score_urgent["score"], score_relaxed["score"])

    def test_ngo_reliability_scoring(self):
        from marketplace.matching import compute_match_score

        req_nearby = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Reliable Food Program",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("50.000"),
            is_active=True,
        )

        # Create past history for nearby_ngo: 4 completed, 0 no-show
        for i in range(4):
            DonationRequest.objects.create(
                listing=self.listing,
                ngo=self.nearby_ngo,
                quantity_requested=Decimal("5.000"),
                status=DonationRequest.Status.COMPLETED,
                proposed_pickup_start=self.now - timedelta(days=2),
                proposed_pickup_end=self.now - timedelta(days=2, hours=-2),
            )

        score_info = compute_match_score(self.listing, req_nearby, 3.5)
        self.assertEqual(score_info["breakdown"]["reliability_score"], 100.0)

        # Add 4 no-shows -> completion rate drops to 50%
        for i in range(4):
            DonationRequest.objects.create(
                listing=self.listing,
                ngo=self.nearby_ngo,
                quantity_requested=Decimal("5.000"),
                status=DonationRequest.Status.NO_SHOW,
                proposed_pickup_start=self.now - timedelta(days=1),
                proposed_pickup_end=self.now - timedelta(days=1, hours=-2),
            )

        score_info_after = compute_match_score(self.listing, req_nearby, 3.5)
        self.assertEqual(score_info_after["breakdown"]["reliability_score"], 50.0)

    def test_fairness_distribution_boost(self):
        from marketplace.matching import compute_match_score

        req = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Daily Food Need",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("50.000"),
            is_active=True,
        )

        # First-time NGO has 0 past donations -> fairness score 100.0
        score1 = compute_match_score(self.listing, req, 3.5)
        self.assertEqual(score1["breakdown"]["fairness_score"], 100.0)

        # Completed donation 2 hours ago -> fairness drops to 25.0
        dr = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.nearby_ngo,
            quantity_requested=Decimal("10.000"),
            status=DonationRequest.Status.COMPLETED,
            proposed_pickup_start=self.now - timedelta(hours=2),
            proposed_pickup_end=self.now - timedelta(hours=1),
        )
        dr.updated_at = self.now - timedelta(hours=2)
        dr.save(update_fields=["updated_at"])

        score2 = compute_match_score(self.listing, req, 3.5)
        self.assertEqual(score2["breakdown"]["fairness_score"], 25.0)

    def test_composite_prioritization_ordering(self):
        from marketplace.matching import find_matching_requirements_for_listing

        # Close NGO (distance score high)
        req_close = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Close Requirement",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("60.000"),
            radius_km=Decimal("10.00"),
            is_active=True,
        )

        # Far NGO with large radius (distance score lower)
        req_far = NGORequirement.objects.create(
            ngo=self.far_ngo,
            title="Far Requirement",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("60.000"),
            radius_km=Decimal("30.00"),
            is_active=True,
        )

        matches = find_matching_requirements_for_listing(self.listing)
        self.assertGreaterEqual(len(matches), 2)
        # Ordered descending by composite score
        self.assertGreaterEqual(matches[0]["score"], matches[1]["score"])
        self.assertEqual(matches[0]["requirement_id"], req_close.id)

    def test_generate_match_notifications_idempotency(self):
        from marketplace.matching import generate_match_notifications_for_listing

        req = NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Bread Program",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("60.000"),
            radius_km=Decimal("10.00"),
            is_active=True,
        )

        # First run creates notification
        notifs = generate_match_notifications_for_listing(self.listing, top_n=5, min_score=20.0)
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0].organization, self.nearby_ngo)
        self.assertEqual(notifs[0].type, "SURPLUS_MATCH")
        self.assertIn(self.listing.title, notifs[0].title)

        # Second run is idempotent (no duplicate notification dispatched)
        notifs_dup = generate_match_notifications_for_listing(self.listing, top_n=5, min_score=20.0)
        self.assertEqual(len(notifs_dup), 0)

    def test_batch_run_matching_engine(self):
        from marketplace.matching import batch_run_matching_engine

        NGORequirement.objects.create(
            ngo=self.nearby_ngo,
            title="Morning Bread",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("60.000"),
            radius_km=Decimal("10.00"),
            is_active=True,
        )

        stats = batch_run_matching_engine(min_score=20.0, top_n=5)
        self.assertGreaterEqual(stats["listings_evaluated"], 1)
        self.assertGreaterEqual(stats["matches_found"], 1)
        self.assertGreaterEqual(stats["notifications_created"], 1)


class MatchingEngineAPITestCase(APITestCase):
    """
    REST API tests for NGO requirements and Matching Engine endpoints:
    - /api/v1/marketplace/requirements/
    - /api/v1/marketplace/requirements/<id>/
    - /api/v1/marketplace/requirements/<id>/matches/
    - /api/v1/marketplace/listings/<id>/matches/
    - /api/v1/marketplace/listings/<id>/notify-matches/
    """

    def setUp(self):
        self.now = timezone.now()

        # Donor organization
        self.donor_org = Organization.objects.create(
            name="Apex Supermarket",
            org_type=Organization.Type.BUSINESS,
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.donor_user = User.objects.create_user(
            username="donor_mgr",
            organization=self.donor_org,
            role=User.Role.OWNER,
        )

        # Other business (cross-tenant)
        self.other_biz = Organization.objects.create(
            name="Other Grocery",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.other_biz_user = User.objects.create_user(
            username="other_biz_mgr",
            organization=self.other_biz,
            role=User.Role.OWNER,
        )

        # Verified NGO A
        self.ngo_a = Organization.objects.create(
            name="Bangalore Food Bank",
            org_type=Organization.Type.NGO,
            latitude=Decimal("12.975000"),
            longitude=Decimal("77.600000"),
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.ngo_a_user = User.objects.create_user(
            username="ngo_a_dir",
            organization=self.ngo_a,
            role=User.Role.OWNER,
        )

        # Verified NGO B
        self.ngo_b = Organization.objects.create(
            name="Seva Shelter",
            org_type=Organization.Type.NGO,
            latitude=Decimal("12.960000"),
            longitude=Decimal("77.610000"),
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.ngo_b_user = User.objects.create_user(
            username="ngo_b_dir",
            organization=self.ngo_b,
            role=User.Role.OWNER,
        )

        # Platform Admin
        self.admin_user = User.objects.create_user(
            username="platform_admin",
            is_staff=True,
            organization=None,
        )

        self.category, _ = Category.objects.get_or_create(name="Staples & Grains")

        # Open surplus listing
        self.listing = SurplusListing.objects.create(
            donor=self.donor_org,
            title="Rice & Wheat Bags",
            category=self.category,
            quantity_offered=Decimal("100.000"),
            quantity_reserved=Decimal("0.000"),
            unit="kg",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            available_from=self.now,
            available_until=self.now + timedelta(hours=24),
            safe_until=self.now + timedelta(hours=30),
            is_cooked=False,
            status=SurplusListing.Status.OPEN,
        )

    def test_api_ngo_creates_requirement(self):
        self.client.force_authenticate(user=self.ngo_a_user)
        payload = {
            "title": "Daily Grain Need",
            "categories": [self.category.id],
            "min_quantity": "20.000",
            "max_quantity": "80.000",
            "unit": "kg",
            "radius_km": "12.00",
            "frequency": "DAILY",
            "accepts_cooked_food": False,
        }
        res = self.client.post("/api/v1/marketplace/requirements/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["ngo"], self.ngo_a.id)
        self.assertEqual(res.data["title"], "Daily Grain Need")

    def test_api_business_cannot_create_requirement(self):
        self.client.force_authenticate(user=self.donor_user)
        payload = {
            "title": "Invalid Business Req",
            "max_quantity": "50.000",
        }
        res = self.client.post("/api/v1/marketplace/requirements/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_requirement_tenant_isolation(self):
        req_a = NGORequirement.objects.create(
            ngo=self.ngo_a,
            title="NGO A Exclusive Needs",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("50.000"),
            is_active=True,
        )

        # NGO B cannot view or modify NGO A's requirement -> 404
        self.client.force_authenticate(user=self.ngo_b_user)
        res_get = self.client.get(f"/api/v1/marketplace/requirements/{req_a.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        res_patch = self.client.patch(
            f"/api/v1/marketplace/requirements/{req_a.id}/",
            {"title": "Hacked Title"},
            format="json",
        )
        self.assertEqual(res_patch.status_code, status.HTTP_404_NOT_FOUND)

        res_del = self.client.delete(f"/api/v1/marketplace/requirements/{req_a.id}/")
        self.assertEqual(res_del.status_code, status.HTTP_404_NOT_FOUND)

        # Owner NGO A can update
        self.client.force_authenticate(user=self.ngo_a_user)
        res_ok = self.client.patch(
            f"/api/v1/marketplace/requirements/{req_a.id}/",
            {"title": "Updated Title"},
            format="json",
        )
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ok.data["title"], "Updated Title")

    def test_api_listing_matches_donor_only(self):
        # Create requirement for NGO A that matches the listing
        NGORequirement.objects.create(
            ngo=self.ngo_a,
            title="Rice Need",
            min_quantity=Decimal("20.000"),
            max_quantity=Decimal("100.000"),
            radius_km=Decimal("10.00"),
            is_active=True,
        )

        # Donor organization views listing matches -> 200 OK
        self.client.force_authenticate(user=self.donor_user)
        res_donor = self.client.get(f"/api/v1/marketplace/listings/{self.listing.id}/matches/")
        self.assertEqual(res_donor.status_code, status.HTTP_200_OK)
        self.assertEqual(res_donor.data["listing_id"], self.listing.id)
        self.assertGreaterEqual(res_donor.data["matches_count"], 1)

        # Cross-tenant business user tries to view listing matches -> 404 Not Found
        self.client.force_authenticate(user=self.other_biz_user)
        res_other = self.client.get(f"/api/v1/marketplace/listings/{self.listing.id}/matches/")
        self.assertEqual(res_other.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_listing_notify_matches(self):
        NGORequirement.objects.create(
            ngo=self.ngo_a,
            title="Emergency Food",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("100.000"),
            radius_km=Decimal("10.00"),
            is_active=True,
        )

        self.client.force_authenticate(user=self.donor_user)
        res = self.client.post(
            f"/api/v1/marketplace/listings/{self.listing.id}/notify-matches/",
            {"top_n": 3, "min_score": 20.0},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "success")
        self.assertGreaterEqual(res.data["notifications_dispatched"], 1)

        # Verify in-app notification arrived for NGO A
        notif = Notification.objects.filter(
            organization=self.ngo_a,
            type="SURPLUS_MATCH",
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("Rice & Wheat", notif.title)

    def test_api_requirement_matches_ngo_only(self):
        req = NGORequirement.objects.create(
            ngo=self.ngo_a,
            title="Daily Rice Supply",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("100.000"),
            radius_km=Decimal("10.00"),
            is_active=True,
        )

        # Owner NGO A views available surplus listings -> 200 OK
        self.client.force_authenticate(user=self.ngo_a_user)
        res_owner = self.client.get(f"/api/v1/marketplace/requirements/{req.id}/matches/")
        self.assertEqual(res_owner.status_code, status.HTTP_200_OK)
        self.assertEqual(res_owner.data["requirement_id"], req.id)
        self.assertGreaterEqual(res_owner.data["matches_count"], 1)

        # Cross-tenant NGO B tries to view matches for NGO A's requirement -> 404 Not Found
        self.client.force_authenticate(user=self.ngo_b_user)
        res_cross = self.client.get(f"/api/v1/marketplace/requirements/{req.id}/matches/")
        self.assertEqual(res_cross.status_code, status.HTTP_404_NOT_FOUND)

    def test_management_command_match_surplus(self):
        from django.core.management import call_command
        import io

        out = io.StringIO()
        call_command("match_surplus", listing_id=self.listing.id, notify=True, stdout=out)
        output = out.getvalue()
        self.assertIn("Evaluating matches for Listing", output)


# ===========================================================================
# TASK 4: REDISTRIBUTION API SUITE (Schedule, Impact, Notifs)
# ===========================================================================

class RedistributionAPIEndpointsTestCase(APITestCase):
    """
    Test suite for Task 4 API endpoints:
    - Listings detail, filters, patch, cancel
    - Pickup Schedule calendar / agenda
    - Impact Analytics metrics & breakdowns
    - Tenant Notifications and read tracking
    """

    def setUp(self):
        self.now = timezone.now()

        # Business Donor
        self.donor_biz = Organization.objects.create(
            name="Green Valley Organics",
            org_type=Organization.Type.BUSINESS,
            address="123 Farm Rd, North Bangalore",
            latitude=Decimal("13.035000"),
            longitude=Decimal("77.597000"),
            phone="+91-9876543210",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.donor_user = User.objects.create_user(
            username="gv_owner",
            organization=self.donor_biz,
            role=User.Role.OWNER,
        )

        # Other Business (Cross-Tenant)
        self.other_biz = Organization.objects.create(
            name="Corner Mart",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.other_biz_user = User.objects.create_user(
            username="cm_owner",
            organization=self.other_biz,
            role=User.Role.OWNER,
        )

        # NGO Partner
        self.ngo = Organization.objects.create(
            name="Hope Harvest NGO",
            org_type=Organization.Type.NGO,
            address="77 Care Lane, Bangalore",
            latitude=Decimal("13.020000"),
            longitude=Decimal("77.600000"),
            phone="+91-9123456780",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.ngo_user = User.objects.create_user(
            username="hope_coordinator",
            organization=self.ngo,
            role=User.Role.OWNER,
        )

        # Other NGO (Cross-Tenant)
        self.other_ngo = Organization.objects.create(
            name="City Food Bank",
            org_type=Organization.Type.NGO,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.other_ngo_user = User.objects.create_user(
            username="cfb_coordinator",
            organization=self.other_ngo,
            role=User.Role.OWNER,
        )

        self.cat_produce, _ = Category.objects.get_or_create(name="Fresh Produce")
        self.cat_dairy, _ = Category.objects.get_or_create(name="Dairy Products")

        # Open Listing
        self.listing = SurplusListing.objects.create(
            donor=self.donor_biz,
            title="Fresh Organic Spinach & Kale",
            description="Crisp leafy greens harvested this morning.",
            category=self.cat_produce,
            quantity_offered=Decimal("40.000"),
            quantity_reserved=Decimal("10.000"),
            unit="kg",
            available_from=self.now,
            available_until=self.now + timedelta(hours=18),
            safe_until=self.now + timedelta(hours=24),
            is_cooked=False,
            status=SurplusListing.Status.OPEN,
        )

        # Scheduled Donation Request
        self.scheduled_req = DonationRequest.objects.create(
            listing=self.listing,
            ngo=self.ngo,
            quantity_requested=Decimal("10.000"),
            quantity_approved=Decimal("10.000"),
            status=DonationRequest.Status.SCHEDULED,
            proposed_pickup_start=self.now,
            proposed_pickup_end=self.now + timedelta(hours=1),
            confirmed_pickup_start=self.now,
            confirmed_pickup_end=self.now + timedelta(hours=1),
            contact_name="Ramesh Kumar",
            contact_phone="+91-9888877777",
            note="Will bring insulated crates.",
        )

    # 1. Surplus Marketplace Endpoints
    def test_api_listings_filters_and_mine(self):
        # Create a second listing from other_biz
        SurplusListing.objects.create(
            donor=self.other_biz,
            title="Whole Milk Gallons",
            category=self.cat_dairy,
            quantity_offered=Decimal("20.000"),
            unit="liters",
            available_from=self.now,
            available_until=self.now + timedelta(hours=12),
            status=SurplusListing.Status.OPEN,
        )

        # Anonymous / unauthenticated lists all open listings
        res_all = self.client.get("/api/v1/marketplace/listings/")
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res_all.data), 2)

        # Donor uses ?mine=true -> only sees donor's listing
        self.client.force_authenticate(user=self.donor_user)
        res_mine = self.client.get("/api/v1/marketplace/listings/?mine=true")
        self.assertEqual(res_mine.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_mine.data), 1)
        self.assertEqual(res_mine.data[0]["id"], self.listing.id)

        # Filter by category
        res_cat = self.client.get(f"/api/v1/marketplace/listings/?category={self.cat_produce.id}")
        self.assertEqual(res_cat.status_code, status.HTTP_200_OK)
        self.assertTrue(all(item["category"] == self.cat_produce.id for item in res_cat.data))

        # Filter by search
        res_search = self.client.get("/api/v1/marketplace/listings/?search=Spinach")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_search.data), 1)
        self.assertEqual(res_search.data[0]["id"], self.listing.id)

    def test_api_listing_detail_and_patch(self):
        # Anyone can view listing detail
        res = self.client.get(f"/api/v1/marketplace/listings/{self.listing.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["title"], self.listing.title)

        # Non-owner cannot patch listing -> 404
        self.client.force_authenticate(user=self.other_biz_user)
        res_cross = self.client.patch(
            f"/api/v1/marketplace/listings/{self.listing.id}/",
            {"title": "Hacked Title"},
            format="json",
        )
        self.assertEqual(res_cross.status_code, status.HTTP_404_NOT_FOUND)

        # Owner donor patches title
        self.client.force_authenticate(user=self.donor_user)
        res_ok = self.client.patch(
            f"/api/v1/marketplace/listings/{self.listing.id}/",
            {"title": "Fresh Organic Spinach & Baby Kale"},
            format="json",
        )
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ok.data["title"], "Fresh Organic Spinach & Baby Kale")

        # Business rule: cannot reduce offered quantity below currently reserved quantity (10 kg)
        res_err = self.client.patch(
            f"/api/v1/marketplace/listings/{self.listing.id}/",
            {"quantity_offered": "5.000"},
            format="json",
        )
        self.assertEqual(res_err.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_listing_cancel_delete(self):
        self.client.force_authenticate(user=self.donor_user)
        res = self.client.delete(f"/api/v1/marketplace/listings/{self.listing.id}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, SurplusListing.Status.CANCELLED)

    # 2. Pickup Schedule Endpoints
    def test_api_pickup_schedule_business_and_ngo(self):
        # Business perspective: sees pickups scheduled at their store
        self.client.force_authenticate(user=self.donor_user)
        res_biz = self.client.get("/api/v1/marketplace/schedule/")
        self.assertEqual(res_biz.status_code, status.HTTP_200_OK)
        self.assertEqual(res_biz.data["total_count"], 1)
        item = res_biz.data["results"][0]
        self.assertEqual(item["request_id"], self.scheduled_req.id)
        self.assertEqual(item["item_title"], self.listing.title)
        self.assertEqual(item["ngo_name"], self.ngo.name)
        self.assertEqual(item["contact_name"], "Ramesh Kumar")
        self.assertEqual(item["is_today"], True)

        # NGO perspective: sees their own scheduled pickups
        self.client.force_authenticate(user=self.ngo_user)
        res_ngo = self.client.get("/api/v1/marketplace/schedule/")
        self.assertEqual(res_ngo.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ngo.data["total_count"], 1)
        self.assertEqual(res_ngo.data["results"][0]["donor_name"], self.donor_biz.name)

        # Other NGO perspective: 0 scheduled pickups
        self.client.force_authenticate(user=self.other_ngo_user)
        res_other = self.client.get("/api/v1/marketplace/schedule/")
        self.assertEqual(res_other.status_code, status.HTTP_200_OK)
        self.assertEqual(res_other.data["total_count"], 0)

    # 3. Impact Analytics Endpoints
    def test_api_impact_analytics(self):
        # Mark scheduled_req as completed with 25 kg
        self.scheduled_req.status = DonationRequest.Status.COMPLETED
        self.scheduled_req.quantity_approved = Decimal("25.000")
        self.scheduled_req.save()

        # Business checks impact metrics
        self.client.force_authenticate(user=self.donor_user)
        res_biz = self.client.get("/api/v1/marketplace/impact/")
        self.assertEqual(res_biz.status_code, status.HTTP_200_OK)
        self.assertEqual(res_biz.data["total_donations_completed"], 1)
        self.assertEqual(res_biz.data["total_quantity_donated_kg"], 25.0)
        # 25 kg * 2.4 meals/kg = 60 meals
        self.assertEqual(res_biz.data["meals_provided"], 60)
        # 25 kg * 2.5 kg CO2 = 62.5 kg CO2
        self.assertEqual(res_biz.data["co2_diverted_kg"], 62.5)
        self.assertEqual(res_biz.data["water_saved_liters"], 25000)
        self.assertGreaterEqual(len(res_biz.data["category_breakdown"]), 1)
        self.assertGreaterEqual(len(res_biz.data["monthly_trend"]), 1)

        # NGO checks impact metrics
        self.client.force_authenticate(user=self.ngo_user)
        res_ngo = self.client.get("/api/v1/marketplace/impact/")
        self.assertEqual(res_ngo.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ngo.data["total_donations_completed"], 1)
        self.assertEqual(res_ngo.data["meals_provided"], 60)

        # Unauthenticated public impact endpoint
        self.client.force_authenticate(user=None)
        res_public = self.client.get("/api/v1/marketplace/impact/public/")
        self.assertEqual(res_public.status_code, status.HTTP_200_OK)
        self.assertEqual(res_public.data["total_quantity_donated_kg"], 25.0)
        self.assertIn("meals_provided", res_public.data)
        self.assertIn("co2_diverted_kg", res_public.data)
        self.assertIn("total_donors", res_public.data)
        self.assertIn("total_ngos", res_public.data)

    # 4. In-App Notifications Endpoints
    def test_api_notifications_and_read_tracking(self):
        # Create unread notification for donor_biz
        n1 = Notification.objects.create(
            organization=self.donor_biz,
            type="NEW_REQUEST",
            title="New Donation Request for Bread",
            body="Hope Harvest requested 10 kg.",
            is_read=False,
        )
        # Create read notification for donor_biz
        Notification.objects.create(
            organization=self.donor_biz,
            type="STATUS_UPDATE",
            title="Donation Completed",
            body="Pickup successfully finalized.",
            is_read=True,
        )
        # Notification for another organization
        n_other = Notification.objects.create(
            organization=self.ngo,
            type="SURPLUS_MATCH",
            title="Match Alert",
            body="New surplus food near you.",
            is_read=False,
        )

        self.client.force_authenticate(user=self.donor_user)

        # 1. List notifications
        res_list = self.client.get("/api/v1/marketplace/notifications/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data["results"]), 2)
        self.assertEqual(res_list.data["unread_count"], 1)

        # Filter unread_only=true
        res_unread = self.client.get("/api/v1/marketplace/notifications/?unread_only=true")
        self.assertEqual(res_unread.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_unread.data["results"]), 1)
        self.assertEqual(res_unread.data["results"][0]["id"], n1.id)

        # 2. Cross-tenant mark read returns 404
        res_cross = self.client.patch(f"/api/v1/marketplace/notifications/{n_other.id}/read/")
        self.assertEqual(res_cross.status_code, status.HTTP_404_NOT_FOUND)

        # 3. Mark single notification as read
        res_read = self.client.patch(f"/api/v1/marketplace/notifications/{n1.id}/read/")
        self.assertEqual(res_read.status_code, status.HTTP_200_OK)
        self.assertEqual(res_read.data["is_read"], True)

        n1.refresh_from_db()
        self.assertTrue(n1.is_read)

        # 4. Mark all as read
        Notification.objects.create(
            organization=self.donor_biz,
            type="REMINDER",
            title="Pickup Reminder",
            body="Driver arriving in 30 minutes.",
            is_read=False,
        )
        res_all_read = self.client.post("/api/v1/marketplace/notifications/mark-all-read/")
        self.assertEqual(res_all_read.status_code, status.HTTP_200_OK)
        self.assertEqual(res_all_read.data["status"], "success")
        self.assertEqual(res_all_read.data["updated_count"], 1)

        unread_count_after = Notification.objects.filter(organization=self.donor_biz, is_read=False).count()
        self.assertEqual(unread_count_after, 0)





