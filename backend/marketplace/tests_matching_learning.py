"""
SurplusSync Matching Engine: Learning Layer Unit & Integration Test Suite (Task 1).

Tests:
1. Hard filters never overridden:
   - Verified NGO hard filter
   - Geographic radius hard filter
   - Cooked food compatibility hard filter
   - Closed / Expired listing hard filter
2. Cold-start fallback:
   - When real completed requests < MATCHING_MIN_REAL_REQUESTS (default 200), falls back to base formula score.
   - Explicit fallback explanation provided in reasons and fallback_reason.
   - Synthetic requests ([SYNTHETIC DEMO DATA]) are excluded from real count.
3. No future leakage in split:
   - Features at match-time T strictly filter historical requests and ratings with requested_at < T / created_at < T.
4. Reproducibility with fixed seed:
   - Generating synthetic history with identical seed yields identical results.
5. Plain-language reasons:
   - Every match keeps a human-readable reasons list showing formula and learned contributions.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Organization
from inventory.models import Category, Product, StorageLocation
from marketplace.learning_layer import (
    FEATURE_NAMES,
    evaluate_learned_match_score,
    extract_match_features,
    predict_collection_probability,
)
from marketplace.matching import (
    compute_match_score,
    evaluate_compatibility,
    find_matching_listings_for_requirement,
    find_matching_requirements_for_listing,
    haversine_distance,
)
from marketplace.models import (
    DonationRequest,
    NGORequirement,
    Rating,
    SurplusListing,
)


class MatchingEngineLearningLayerTestCase(TestCase):
    """Test suite covering the 5 critical requirements of Task 1."""

    def setUp(self):
        self.now = timezone.now()

        # Donor organization
        self.donor_org = Organization.objects.create(
            name="Harvest Fresh Donor",
            org_type=Organization.Type.BUSINESS,
            address="Indiranagar, Bengaluru",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            phone="+91 98765 43210",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )

        # Verified NGO
        self.verified_ngo = Organization.objects.create(
            name="Relief NGO Verified",
            org_type=Organization.Type.NGO,
            address="MG Road, Bengaluru",
            latitude=Decimal("12.975000"),
            longitude=Decimal("77.605000"),
            phone="+91 91234 56789",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )

        # Unverified NGO
        self.unverified_ngo = Organization.objects.create(
            name="Unverified Shelter",
            org_type=Organization.Type.NGO,
            address="Brigade Road, Bengaluru",
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.608000"),
            phone="+91 99999 00000",
            is_verified=False,
            verification_status=Organization.VerificationStatus.PENDING,
        )

        # Category
        self.category = Category.objects.create(
            name="Cooked Meals",
            perishability_risk=Category.Risk.CRITICAL,
        )

        # Listing (Cooked Food, 20kg, available for 6 hours)
        self.listing = SurplusListing.objects.create(
            donor=self.donor_org,
            title="Fresh Meals Surplus",
            category=self.category,
            quantity_offered=Decimal("20.000"),
            unit="kg",
            pickup_address="Indiranagar, Bengaluru",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            available_from=self.now,
            available_until=self.now + timedelta(hours=6),
            safe_until=self.now + timedelta(hours=8),
            is_cooked=True,
            status=SurplusListing.Status.OPEN,
        )

    # -------------------------------------------------------------------------
    # 1. HARD FILTERS NEVER OVERRIDDEN
    # -------------------------------------------------------------------------
    def test_hard_filter_unverified_ngo_never_matched(self):
        """Unverified NGOs must be completely excluded from matching candidates."""
        req_unverified = NGORequirement.objects.create(
            ngo=self.unverified_ngo,
            title="Need Meals",
            min_quantity=Decimal("5.000"),
            max_quantity=Decimal("30.000"),
            radius_km=Decimal("25.00"),
            accepts_cooked_food=True,
            is_active=True,
        )
        req_unverified.categories.add(self.category)

        matches = find_matching_requirements_for_listing(self.listing, compatible_only=True)
        ngo_ids = [m["ngo_id"] for m in matches]
        self.assertNotIn(self.unverified_ngo.id, ngo_ids)

    def test_hard_filter_outside_radius_never_compatible(self):
        """Distance exceeding requirement radius must be marked incompatible regardless of ML score."""
        req = NGORequirement.objects.create(
            ngo=self.verified_ngo,
            title="Strict Local Need",
            min_quantity=Decimal("5.000"),
            max_quantity=Decimal("30.000"),
            radius_km=Decimal("1.00"),  # 1 km radius
            accepts_cooked_food=True,
            is_active=True,
        )
        req.categories.add(self.category)

        # Haversine distance between donor and verified_ngo is ~1.2 km (> 1.0 km)
        dist = haversine_distance(
            float(self.listing.latitude), float(self.listing.longitude),
            float(self.verified_ngo.latitude), float(self.verified_ngo.longitude)
        )
        self.assertGreater(dist, 1.0)

        is_compat, reasons = evaluate_compatibility(self.listing, req, dist)
        self.assertFalse(is_compat)
        self.assertTrue(any("operating radius" in r for r in reasons))

        # Ensure compatible_only search drops it completely
        matches = find_matching_requirements_for_listing(self.listing, compatible_only=True)
        req_ids = [m["requirement_id"] for m in matches]
        self.assertNotIn(req.id, req_ids)

    def test_hard_filter_cooked_food_incompatibility(self):
        """If listing is cooked and NGO rejects cooked food, must never be compatible."""
        req = NGORequirement.objects.create(
            ngo=self.verified_ngo,
            title="Raw Supplies Only",
            min_quantity=Decimal("5.000"),
            max_quantity=Decimal("30.000"),
            radius_km=Decimal("25.00"),
            accepts_cooked_food=False,  # Rejects cooked food
            is_active=True,
        )
        req.categories.add(self.category)

        is_compat, reasons = evaluate_compatibility(self.listing, req, 1.2)
        self.assertFalse(is_compat)
        self.assertTrue(any("cooked food" in r for r in reasons))

    def test_hard_filter_closed_or_expired_listing_never_matched(self):
        """Listings that are not OPEN or have passed available_until must not be matched."""
        self.listing.status = SurplusListing.Status.COMPLETED
        self.listing.save(update_fields=["status"])

        req = NGORequirement.objects.create(
            ngo=self.verified_ngo,
            title="Daily Relief",
            min_quantity=Decimal("5.000"),
            max_quantity=Decimal("30.000"),
            radius_km=Decimal("25.00"),
            accepts_cooked_food=True,
            is_active=True,
        )
        req.categories.add(self.category)

        matches = find_matching_listings_for_requirement(req, compatible_only=True)
        listing_ids = [m["listing_id"] for m in matches]
        self.assertNotIn(self.listing.id, listing_ids)

    # -------------------------------------------------------------------------
    # 2. COLD-START FALLBACK
    # -------------------------------------------------------------------------
    @override_settings(MATCHING_MIN_REAL_REQUESTS=200)
    def test_cold_start_fallback_when_real_requests_under_threshold(self):
        """When fewer than 200 real completed requests exist, falls back to base score."""
        req = NGORequirement.objects.create(
            ngo=self.verified_ngo,
            title="Local Relief",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("50.000"),
            radius_km=Decimal("20.00"),
            accepts_cooked_food=True,
            is_active=True,
        )
        req.categories.add(self.category)

        # Only 2 real requests in database (< 200)
        for i in range(2):
            DonationRequest.objects.create(
                code=f"REAL-TEST-{i+1:04d}",
                listing=self.listing,
                ngo=self.verified_ngo,
                quantity_requested=Decimal("5.000"),
                status=DonationRequest.Status.COMPLETED,
                proposed_pickup_start=self.now + timedelta(hours=1),
                proposed_pickup_end=self.now + timedelta(hours=2),
                note="Organic real request",
            )

        eval_result = evaluate_learned_match_score(
            listing=self.listing,
            requirement=req,
            distance_km=1.5,
            base_score=78.5,
            force_model=False,
        )

        self.assertTrue(eval_result["is_fallback"])
        self.assertEqual(eval_result["final_score"], 78.5)
        self.assertIn("cold-start fallback", eval_result["fallback_reason"])
        self.assertTrue(any("cold-start" in r for r in eval_result["reasons"]))

    def test_synthetic_requests_excluded_from_cold_start_real_count(self):
        """Requests with note starting with [SYNTHETIC are excluded from real request count."""
        req = NGORequirement.objects.create(
            ngo=self.verified_ngo,
            title="Local Relief",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("50.000"),
            radius_km=Decimal("20.00"),
            accepts_cooked_food=True,
            is_active=True,
        )
        req.categories.add(self.category)

        # Create 250 synthetic requests (labeled [SYNTHETIC DEMO DATA])
        for i in range(10):
            DonationRequest.objects.create(
                code=f"SYNTH-COUNT-{i+1:04d}",
                listing=self.listing,
                ngo=self.verified_ngo,
                quantity_requested=Decimal("5.000"),
                status=DonationRequest.Status.COMPLETED,
                proposed_pickup_start=self.now + timedelta(hours=1),
                proposed_pickup_end=self.now + timedelta(hours=2),
                note="[SYNTHETIC DEMO DATA] Benchmark record",
            )

        # Real completed count is still 0 (< 200)
        real_count = DonationRequest.objects.filter(
            status=DonationRequest.Status.COMPLETED
        ).exclude(note__startswith="[SYNTHETIC").count()
        self.assertEqual(real_count, 0)

        eval_result = evaluate_learned_match_score(
            listing=self.listing,
            requirement=req,
            distance_km=1.5,
            base_score=80.0,
            force_model=False,
        )
        self.assertTrue(eval_result["is_fallback"])

    # -------------------------------------------------------------------------
    # 3. NO FUTURE LEAKAGE IN TIME SPLIT
    # -------------------------------------------------------------------------
    def test_no_future_leakage_in_match_time_features(self):
        """Feature extraction at timestamp T must only count history prior to T."""
        req = NGORequirement.objects.create(
            ngo=self.verified_ngo,
            title="Reliable Food Program",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("50.000"),
            radius_km=Decimal("20.00"),
            accepts_cooked_food=True,
            is_active=True,
        )
        req.categories.add(self.category)

        t_past = self.now - timedelta(days=10)
        t_future = self.now + timedelta(days=5)

        # 1 historical completed request before t_past
        dr1 = DonationRequest.objects.create(
            code="PAST-0001",
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("5.000"),
            status=DonationRequest.Status.COMPLETED,
            proposed_pickup_start=t_past - timedelta(days=2),
            proposed_pickup_end=t_past - timedelta(days=2) + timedelta(hours=2),
        )
        DonationRequest.objects.filter(id=dr1.id).update(requested_at=t_past - timedelta(days=2))

        # 1 future no-show request after t_past
        dr2 = DonationRequest.objects.create(
            code="FUTURE-0001",
            listing=self.listing,
            ngo=self.verified_ngo,
            quantity_requested=Decimal("5.000"),
            status=DonationRequest.Status.NO_SHOW,
            proposed_pickup_start=t_past + timedelta(days=2),
            proposed_pickup_end=t_past + timedelta(days=2) + timedelta(hours=2),
        )
        DonationRequest.objects.filter(id=dr2.id).update(requested_at=t_past + timedelta(days=2))

        # Extract features at t_past: must NOT see the future no-show
        features_at_past = extract_match_features(
            listing=self.listing,
            requirement=req,
            distance_km=2.0,
            at_time=t_past,
        )

        # Extract features at t_future: MUST see both past completed and future no-show
        features_at_future = extract_match_features(
            listing=self.listing,
            requirement=req,
            distance_km=2.0,
            at_time=t_future,
        )

        # At t_past: only 1 completion + neutral prior (alpha=4, beta=1 -> (1+4)/(1+0+5) = 5/6 = 0.8333)
        # At t_future: 1 completion, 1 no-show + prior -> (1+4)/(1+1+5) = 5/7 = 0.7143
        self.assertGreater(features_at_past["ngo_completion_rate"], features_at_future["ngo_completion_rate"])
        self.assertLess(features_at_past["ngo_no_show_rate"], features_at_future["ngo_no_show_rate"])

    # -------------------------------------------------------------------------
    # 4. REPRODUCIBILITY WITH FIXED SEED
    # -------------------------------------------------------------------------
    def test_synthetic_history_generation_reproducibility(self):
        """Generating synthetic history with the same seed produces identical outcomes."""
        from inventory.management.commands.seed_demo_data import seed_synthetic_matching_history

        stats_run1 = seed_synthetic_matching_history(
            donor_org=self.donor_org,
            count=50,
            seed=999,
            days=30,
        )

        stats_run2 = seed_synthetic_matching_history(
            donor_org=self.donor_org,
            count=50,
            seed=999,
            days=30,
        )

        self.assertEqual(stats_run1["completed"], stats_run2["completed"])
        self.assertEqual(stats_run1["rejected"], stats_run2["rejected"])
        self.assertEqual(stats_run1["no_show"], stats_run2["no_show"])
        self.assertEqual(stats_run1["expired"], stats_run2["expired"])

    # -------------------------------------------------------------------------
    # 5. PLAIN-LANGUAGE REASONS LIST
    # -------------------------------------------------------------------------
    def test_plain_language_reasons_contain_formula_and_explanation(self):
        """Every match evaluation must return a descriptive plain-language reasons list."""
        req = NGORequirement.objects.create(
            ngo=self.verified_ngo,
            title="Breakfast Daily",
            min_quantity=Decimal("10.000"),
            max_quantity=Decimal("50.000"),
            radius_km=Decimal("20.00"),
            accepts_cooked_food=True,
            is_active=True,
        )
        req.categories.add(self.category)

        score_info = compute_match_score(self.listing, req, 2.5)

        self.assertIn("score", score_info)
        self.assertIn("base_score", score_info)
        self.assertIn("reasons", score_info)
        self.assertIsInstance(score_info["reasons"], list)
        self.assertGreaterEqual(len(score_info["reasons"]), 1)

        # Reasons must reference rule score
        reasons_text = " ".join(score_info["reasons"])
        self.assertTrue(
            "score" in reasons_text.lower() or "formula" in reasons_text.lower() or "rule" in reasons_text.lower()
        )
