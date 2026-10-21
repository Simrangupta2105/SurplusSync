"""Comprehensive tests for predictions endpoints: tenant isolation, role checks, service-down fallback, input validation, and disclosures."""

from unittest.mock import patch
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Organization, User
from predictions.services import map_category_to_benchmark


class PredictionsAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # 1. Commercial business organization & user
        self.business_org = Organization.objects.create(
            name="Green Delight Supermarket",
            org_type=Organization.Type.BUSINESS,
            business_segment=Organization.BusinessSegment.SUPERMARKET,
            promotion_active=True,
            is_verified=True,
        )
        self.business_user = User.objects.create_user(
            username="business_owner",
            email="owner@greendelight.test",
            password="StrongPassword123!",
            organization=self.business_org,
            role=User.Role.OWNER,
        )

        # 2. Other business organization (for tenant isolation test)
        self.other_business_org = Organization.objects.create(
            name="Rival Bistro",
            org_type=Organization.Type.BUSINESS,
            business_segment=Organization.BusinessSegment.RESTAURANT,
            promotion_active=False,
            is_verified=True,
        )

        # 3. NGO organization & user
        self.ngo_org = Organization.objects.create(
            name="Community Food Relief",
            org_type=Organization.Type.NGO,
            is_verified=True,
        )
        self.ngo_user = User.objects.create_user(
            username="ngo_director",
            email="director@relief.test",
            password="StrongPassword123!",
            organization=self.ngo_org,
            role=User.Role.OWNER,
        )

    # --- Role & Permission Checks ---

    def test_unauthenticated_requests_receive_401(self):
        """Unauthenticated requests are rejected with 401."""
        res_plan = self.client.post("/api/v1/predictions/plan/", {"category": "Bakery", "planned_quantity": 50})
        self.assertEqual(res_plan.status_code, status.HTTP_401_UNAUTHORIZED)

        res_insights = self.client.get("/api/v1/predictions/insights/")
        self.assertEqual(res_insights.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ngo_users_receive_403_forbidden(self):
        """NGO users cannot access predictive planning or commercial insights (403 Forbidden)."""
        self.client.force_authenticate(user=self.ngo_user)

        res_plan = self.client.post("/api/v1/predictions/plan/", {"category": "Bakery", "planned_quantity": 50})
        self.assertEqual(res_plan.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("commercial business", str(res_plan.data))

        res_insights = self.client.get("/api/v1/predictions/insights/")
        self.assertEqual(res_insights.status_code, status.HTTP_403_FORBIDDEN)

    def test_business_users_allowed(self):
        """BUSINESS users are permitted to access predictions endpoints."""
        self.client.force_authenticate(user=self.business_user)

        # Mock ML service response
        mock_response = {
            "forecast_demand": 142.5,
            "forecast_range": {"min": 113.5, "max": 171.5},
            "over_order_ratio": 1.05,
            "predicted_waste_level": "Low",
            "waste_probabilities": {"Low": 0.75, "Medium": 0.20, "High": 0.05},
            "recommended_quantity": 150,
            "explanation": "Expected demand is 142.5 units.",
            "model_version": "1.0.0-poisson-lightgbm",
            "confidence_note": "All operational inputs supplied.",
        }

        with patch("predictions.views.call_ml_service", return_value=(mock_response, 200, None)):
            res = self.client.post(
                "/api/v1/predictions/plan/",
                {"category": "Bakery", "planned_quantity": 150.0},
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data["forecast_demand"], 142.5)

    # --- Tenant Isolation ---

    def test_tenant_isolation_client_cannot_choose_another_organization(self):
        """Client cannot spoof or override the organization using an org_id payload."""
        self.client.force_authenticate(user=self.business_user)

        captured_payload = {}

        def mock_call(endpoint, method="GET", payload=None):
            nonlocal captured_payload
            captured_payload = payload
            return ({"forecast_demand": 100.0, "recommended_quantity": 100, "over_order_ratio": 1.0, "predicted_waste_level": "Low", "waste_probabilities": {"Low": 0.9, "Medium": 0.1, "High": 0.0}, "explanation": "ok", "model_version": "1.0", "confidence_note": "ok", "forecast_range": {"min": 80, "max": 120}}, 200, None)

        with patch("predictions.views.call_ml_service", side_effect=mock_call):
            # Client attempts to pass rival org_id in request body
            res = self.client.post(
                "/api/v1/predictions/plan/",
                {
                    "org_id": self.other_business_org.id,
                    "category": "Dairy",
                    "planned_quantity": 120.0,
                },
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            # The forwarded payload must strictly have the user's authentic organization ID
            self.assertEqual(captured_payload["org_id"], self.business_org.id)
            self.assertNotEqual(captured_payload["org_id"], self.other_business_org.id)
            self.assertEqual(captured_payload["business_type"], "Supermarket")

    # --- Input Validation & Category Mapping ---

    def test_planned_quantity_must_be_greater_than_zero(self):
        """Planned quantity <= 0 is rejected with 400 Bad Request."""
        self.client.force_authenticate(user=self.business_user)

        for invalid_qty in [0, -10, -0.5]:
            res = self.client.post(
                "/api/v1/predictions/plan/",
                {"category": "Bakery", "planned_quantity": invalid_qty},
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("planned_quantity", res.data)

    def test_missing_or_blank_category_is_rejected(self):
        """Missing or blank category returns 400 Bad Request."""
        self.client.force_authenticate(user=self.business_user)

        res = self.client.post("/api/v1/predictions/plan/", {"planned_quantity": 100.0})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category", res.data)

        res_blank = self.client.post("/api/v1/predictions/plan/", {"category": "   ", "planned_quantity": 100.0})
        self.assertEqual(res_blank.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_category_returns_not_covered_answer(self):
        """Unmapped categories like 'Frozen Foods' return a clear 'not covered' answer."""
        self.client.force_authenticate(user=self.business_user)

        unsupported = ["Frozen Foods", "Dry Goods & Grains", "Canned Goods", "Beverages", "OfficeSupplies"]
        for cat in unsupported:
            res = self.client.post(
                "/api/v1/predictions/plan/",
                {"category": cat, "planned_quantity": 50.0},
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(res.data.get("status"), "not_covered")
            self.assertIn("not covered", res.data.get("detail", ""))
            self.assertIn("supported_categories", res.data)

    def test_category_mapping_resolves_aliases(self):
        """Verified that map_category_to_benchmark resolves SurplusSync categories to benchmark taxonomy."""
        self.assertEqual(map_category_to_benchmark("Bakery"), "Bakery")
        self.assertEqual(map_category_to_benchmark("Dairy"), "Dairy")
        self.assertEqual(map_category_to_benchmark("Produce"), "Vegetables")
        self.assertEqual(map_category_to_benchmark("Produce & Fresh Greens"), "Vegetables")
        self.assertEqual(map_category_to_benchmark("Meat & Poultry"), "Meat")
        self.assertEqual(map_category_to_benchmark("Prepared & Cooked Meals"), "Prepared Food")
        self.assertEqual(map_category_to_benchmark("Fruits"), "Fruits")
        self.assertIsNone(map_category_to_benchmark("Frozen Foods"))

    # --- Resilient Service-Down Fallback ---

    def test_service_down_fallback_returns_503_not_500(self):
        """When ML service is unreachable, returns 503 Service Unavailable, NEVER 500."""
        self.client.force_authenticate(user=self.business_user)

        # Simulate ML service connection refusal or timeout
        with patch("predictions.views.call_ml_service", return_value=(None, 503, "Connection refused")):
            res = self.client.post(
                "/api/v1/predictions/plan/",
                {"category": "Produce", "planned_quantity": 100.0},
            )
            self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
            self.assertEqual(res.data.get("status"), "unavailable")
            self.assertIn("temporarily unavailable", res.data.get("detail", ""))
            self.assertIn("retry_after_seconds", res.data)

    # --- Dataset Insights & Mandatory Disclosure ---

    def test_insights_endpoint_always_includes_mandatory_disclosure(self):
        """GET /api/v1/predictions/insights/ returns benchmark facts with mandatory disclosure and source."""
        self.client.force_authenticate(user=self.business_user)

        res = self.client.get("/api/v1/predictions/insights/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        # Verify mandatory markers
        self.assertEqual(data.get("source"), "benchmark dataset")
        disclosure = data.get("data_disclosure", "")
        self.assertIn("benchmark dataset", disclosure)
        self.assertIn("synthetic", disclosure.lower())
        self.assertIn("not this business's data", disclosure)

        # Verify precomputed facts structure
        self.assertIn("waste_rate_by_category", data)
        self.assertIn("waste_reasons_by_category", data)
        self.assertIn("demand_lift_promotion", data)
        self.assertIn("demand_lift_weather", data)
        self.assertIn("over_purchase_share", data)
        self.assertIn("data_card", data)

    def test_insights_endpoint_is_cached(self):
        """Insights response is cached in Django cache for subsequent calls."""
        self.client.force_authenticate(user=self.business_user)

        # First request populates cache
        res1 = self.client.get("/api/v1/predictions/insights/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # Second request must hit cache without calling ML service
        with patch("predictions.views.call_ml_service") as mock_call:
            res2 = self.client.get("/api/v1/predictions/insights/")
            self.assertEqual(res2.status_code, status.HTTP_200_OK)
            mock_call.assert_not_called()
            self.assertEqual(res2.data["source"], "benchmark dataset")
