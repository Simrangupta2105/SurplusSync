"""API views for predictions, AI purchase planner, and benchmark dataset insights."""

from __future__ import annotations

import logging
from typing import Any, Dict

from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from predictions.permissions import IsBusinessOrganizationUser
from predictions.serializers import PlanInputSerializer
from predictions.services import (
    FALLBACK_DATASET_FACTS,
    SUPPORTED_SURPLUSSYNC_CATEGORIES,
    call_ml_service,
    map_category_to_benchmark,
)

logger = logging.getLogger(__name__)

INSIGHTS_CACHE_KEY = "predictions_insights_dataset"
INSIGHTS_CACHE_TTL = 3600  # 1 hour


class PlanPredictionView(APIView):
    """Evaluates a tentative purchase plan against the ML service.

    Access: Authenticated users belonging to a BUSINESS organization only.
    Throttling: Scoped to 'predictions' (default 60/minute).
    Tenant Isolation: Organization ID and business segment are strictly extracted
    from request.user.organization, preventing client-side spoofing.
    """
    permission_classes = [IsAuthenticated, IsBusinessOrganizationUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "predictions"

    def post(self, request, *args, **kwargs) -> Response:
        serializer = PlanInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        raw_category = validated_data["category"]
        mapped_category = map_category_to_benchmark(raw_category)

        # 1. Category taxonomy coverage check
        if not mapped_category:
            return Response(
                {
                    "status": "not_covered",
                    "detail": (
                        f"Category '{raw_category}' is not covered by the predictive waste model. "
                        "The model currently supports fresh perishable categories: Bakery, Dairy, "
                        "Fruits, Meat, Prepared Food, and Vegetables / Produce."
                    ),
                    "supported_categories": SUPPORTED_SURPLUSSYNC_CATEGORIES,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Strict tenant isolation: Extract organization parameters from session only
        org = request.user.organization
        org_id = org.id
        business_type = getattr(org, "business_segment", None) or "Restaurant"

        # Resolve promotion: explicit client flag or organization default
        client_promo = validated_data.get("promotion")
        promo_active = (
            client_promo
            if client_promo is not None
            else getattr(org, "promotion_active", False)
        )

        date_val = validated_data.get("date")
        date_str = date_val.isoformat() if date_val else None

        ml_payload: Dict[str, Any] = {
            "org_id": org_id,
            "category": mapped_category,
            "planned_quantity": validated_data["planned_quantity"],
            "promotion": bool(promo_active),
            "weather": validated_data.get("weather", "Sunny"),
            "date": date_str,
            "business_type": business_type,
        }

        # 3. Call ML microservice with resilient timeout handling
        data, status_code, error_msg = call_ml_service(
            "/v1/plan",
            method="POST",
            payload=ml_payload,
        )

        if status_code == 200 and data is not None:
            # Annotate with the original requested category if mapped
            if raw_category.lower() != mapped_category.lower():
                data["original_category"] = raw_category
                data["mapped_category"] = mapped_category
            return Response(data, status=status.HTTP_200_OK)

        # Handle service unavailable or connection failure gracefully (never return 500)
        logger.warning(
            "ML service unavailable for plan prediction (code %s): %s",
            status_code,
            error_msg,
        )
        return Response(
            {
                "status": "unavailable",
                "detail": (
                    "Predictions temporarily unavailable. The machine learning service "
                    "is offline or starting up. Please try again shortly."
                ),
                "retry_after_seconds": 15,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class DatasetInsightsView(APIView):
    """Returns precomputed empirical benchmark facts and dataset documentation card.

    Access: Authenticated users belonging to a BUSINESS organization only.
    Caching: Cached in Django cache for 1 hour.
    Disclosures: Always embeds data_disclosure and source markers.
    """
    permission_classes = [IsAuthenticated, IsBusinessOrganizationUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "predictions"

    def get(self, request, *args, **kwargs) -> Response:
        cached_data = cache.get(INSIGHTS_CACHE_KEY)
        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Attempt to retrieve from ML service
        data, status_code, _ = call_ml_service("/v1/insights/dataset", method="GET")
        if status_code != 200 or not data:
            # Fall back to statically calibrated benchmark facts
            data = dict(FALLBACK_DATASET_FACTS)

        # Enforce mandatory disclosures
        data["source"] = "benchmark dataset"
        data["data_disclosure"] = (
            "Based on a benchmark dataset that appears synthetic. "
            "These are general patterns, not this business's data."
        )

        # Cache for 1 hour
        cache.set(INSIGHTS_CACHE_KEY, data, INSIGHTS_CACHE_TTL)

        return Response(data, status=status.HTTP_200_OK)
