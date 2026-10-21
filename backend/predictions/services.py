"""Integration services and category mapping for ML service communication."""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

# Category mapping from SurplusSync database taxonomy to benchmark categories
# Supported benchmark categories: Bakery, Dairy, Fruits, Meat, Prepared Food, Vegetables
CATEGORY_BENCHMARK_MAPPING: Dict[str, str] = {
    "bakery": "Bakery",
    "dairy": "Dairy",
    "fruits": "Fruits",
    "fruit": "Fruits",
    "vegetables": "Vegetables",
    "vegetable": "Vegetables",
    "produce": "Vegetables",
    "produce & fresh greens": "Vegetables",
    "meat": "Meat",
    "meat & poultry": "Meat",
    "prepared food": "Prepared Food",
    "prepared & cooked meals": "Prepared Food",
}

SUPPORTED_SURPLUSSYNC_CATEGORIES: List[str] = [
    "Bakery",
    "Dairy",
    "Fruits",
    "Meat",
    "Meat & Poultry",
    "Prepared Food",
    "Prepared & Cooked Meals",
    "Produce",
    "Vegetables",
]

UNSUPPORTED_CATEGORIES: List[str] = [
    "Frozen Foods",
    "Dry Goods & Grains",
    "Canned Goods",
    "Beverages",
]


def map_category_to_benchmark(category_name: str) -> Optional[str]:
    """Resolve a SurplusSync category name or alias to a benchmark model category.

    Returns None if the category is not covered by the predictive waste model.
    """
    if not category_name or not category_name.strip():
        return None
    normalized = category_name.strip().lower()
    return CATEGORY_BENCHMARK_MAPPING.get(normalized)


def call_ml_service(
    endpoint: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
    """Send an HTTP request to the internal ML microservice using standard library urllib.

    Args:
        endpoint: API path (e.g. "/v1/plan" or "/v1/insights/dataset")
        method: HTTP method ("GET" or "POST")
        payload: JSON body dictionary for POST requests
        timeout: Socket timeout in seconds (defaults to settings.ML_SERVICE_TIMEOUT)

    Returns:
        (data_dict, status_code, error_message)
        On network/connection error, returns (None, 503, "ML service unreachable").
    """
    base_url = getattr(settings, "ML_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
    url = f"{base_url}{endpoint}"
    service_token = getattr(settings, "ML_SERVICE_TOKEN", "surplussync-service-token-dev")
    req_timeout = timeout or getattr(settings, "ML_SERVICE_TIMEOUT", 3.0)

    headers = {
        "Accept": "application/json",
        "X-Service-Token": service_token,
    }

    req_data: Optional[bytes] = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        req_data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=req_timeout) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else {}
            return data, status_code, None
    except urllib.error.HTTPError as err:
        status_code = err.code
        try:
            err_body = err.read().decode("utf-8")
            err_json = json.loads(err_body)
            detail = err_json.get("detail", str(err))
        except Exception:
            detail = str(err)
        logger.warning("ML service returned HTTP %s for %s: %s", status_code, endpoint, detail)
        return None, status_code, detail
    except (urllib.error.URLError, socket.timeout, ConnectionRefusedError) as err:
        logger.error("Failed to connect to ML service at %s: %s", url, err)
        return None, 503, "ML service unreachable or offline"
    except Exception as err:
        logger.exception("Unexpected error communicating with ML service: %s", err)
        return None, 503, f"Communication error: {err}"


# Fallback precomputed facts if ML service is unreachable and cache is unpopulated
FALLBACK_DATASET_FACTS: Dict[str, Any] = {
    "waste_rate_by_category": {
        "Prepared Food": {"waste_pct_of_remaining": 38.75, "waste_pct_of_purchase": 7.61},
        "Bakery": {"waste_pct_of_remaining": 28.17, "waste_pct_of_purchase": 4.83},
        "Meat": {"waste_pct_of_remaining": 25.33, "waste_pct_of_purchase": 4.49},
        "Fruits": {"waste_pct_of_remaining": 23.98, "waste_pct_of_purchase": 4.21},
        "Vegetables": {"waste_pct_of_remaining": 22.23, "waste_pct_of_purchase": 3.96},
        "Dairy": {"waste_pct_of_remaining": 21.14, "waste_pct_of_purchase": 3.82},
    },
    "waste_reasons_by_category": {
        "Prepared Food": {"Expired": 40.57, "No Waste": 38.07, "Overproduction": 10.82, "Storage Issue": 5.34, "Low Demand": 5.21},
        "Bakery": {"No Waste": 41.62, "Expired": 19.97, "Overproduction": 18.52, "Low Demand": 14.11, "Storage Issue": 5.77},
        "Meat": {"No Waste": 44.25, "Overproduction": 20.21, "Low Demand": 16.93, "Expired": 16.85, "Storage Issue": 1.76},
        "Fruits": {"No Waste": 43.47, "Overproduction": 21.94, "Low Demand": 20.48, "Expired": 10.06, "Storage Issue": 4.05},
        "Vegetables": {"No Waste": 44.30, "Overproduction": 21.83, "Low Demand": 20.64, "Expired": 8.12, "Storage Issue": 5.11},
        "Dairy": {"No Waste": 45.09, "Overproduction": 24.10, "Low Demand": 20.83, "Expired": 7.83, "Storage Issue": 2.15},
    },
    "demand_lift_promotion": {
        "percentage_lift": 33.06,
        "mean_demand_with_promo": 131.42,
        "mean_demand_without_promo": 98.77,
    },
    "demand_lift_weather": {
        "Sunny": {"multiplier": 1.0000, "relative_effect": "Baseline", "mean_demand": 114.83},
        "Hot": {"multiplier": 1.0385, "relative_effect": "+3.85%", "mean_demand": 119.25},
        "Cloudy": {"multiplier": 0.8921, "relative_effect": "-10.79%", "mean_demand": 102.44},
        "Rainy": {"multiplier": 0.6683, "relative_effect": "-33.17%", "mean_demand": 76.74},
    },
    "over_purchase_share": {
        "share_of_orders_over_purchased_pct": 64.08,
        "total_purchased_units": 946310,
        "total_sold_units": 775677,
        "total_excess_units": 170633,
    },
    "data_card": {
        "title": "Benchmark Commercial Food Waste Dataset",
        "records": 8000,
        "period": "2025-01-01 to 2025-12-31",
        "scope": "8,000 daily observations across 4 business segments and 6 perishable food categories.",
        "provenance_placeholder": "Synthetically calibrated microdata benchmark simulating commercial food service and retail inventory operations.",
        "limitations": "Deterministic sales-accounting constraints; population-level ratio binning creates minor label noise; single-day snapshots without persistent store IDs. This data serves as an empirical cross-sectional benchmark and does not represent live individual tenant operations.",
        "accounting_invariants": "All 5 accounting invariants verified with 0 discrepancies across 8,000 records.",
    },
}
