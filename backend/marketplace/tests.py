from datetime import timedelta
from django.utils import timezone
from django.contrib.admin.sites import site
from rest_framework.test import APITestCase
from rest_framework import status

from accounts.models import Organization, User
from marketplace.models import Listing, Claim, Rating
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

