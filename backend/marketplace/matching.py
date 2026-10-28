"""
SurplusSync Redistribution Matching Engine (Task 3).

Provides:
- Haversine geographic distance calculation between donor businesses and NGOs.
- Compatibility evaluations (active status, verification, category, cooked food, quantity, timing).
- Multi-factor deterministic prioritization scoring (distance, urgency, quantity, reliability, fairness).
- Single-listing and requirement match discovery.
- Batch notification generation and scheduled execution.
"""
from datetime import timedelta
from decimal import Decimal
import logging
import math
from typing import Any, Dict, List, Optional

from django.db.models import Count, Max, Q
from django.utils import timezone

from accounts.models import Organization
from .models import DonationRequest, NGORequirement, Notification, SurplusListing

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0


def haversine_distance(
    lat1: Optional[Any],
    lon1: Optional[Any],
    lat2: Optional[Any],
    lon2: Optional[Any],
) -> float:
    """
    Computes the great-circle distance between two latitude/longitude points in kilometers.
    Handles Decimal, float, int, string, or None safely.
    Returns float('inf') if coordinates are missing or invalid.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float("inf")

    try:
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        delta_phi = math.radians(float(lat2) - float(lat1))
        delta_lambda = math.radians(float(lon2) - float(lon1))
    except (TypeError, ValueError):
        return float("inf")

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_KM * c, 2)


def get_listing_coordinates(listing: SurplusListing) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Returns (latitude, longitude) for a listing, falling back to donor org if empty."""
    lat = listing.latitude if listing.latitude is not None else (listing.donor.latitude if listing.donor else None)
    lon = listing.longitude if listing.longitude is not None else (listing.donor.longitude if listing.donor else None)
    return lat, lon


def get_ngo_coordinates(org: Organization) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Returns (latitude, longitude) for an NGO organization."""
    return org.latitude, org.longitude


def evaluate_compatibility(
    listing: SurplusListing,
    requirement: NGORequirement,
    distance_km: float,
) -> tuple[bool, List[str]]:
    """
    Evaluates strict compatibility rules between a SurplusListing and an NGORequirement.
    Returns (is_compatible, list_of_incompatibility_reasons).
    """
    reasons: List[str] = []
    ngo = requirement.ngo

    # 1. Verification & Active Status
    if not (ngo.is_verified or ngo.verification_status == Organization.VerificationStatus.VERIFIED):
        reasons.append("NGO organization is not verified.")

    if not requirement.is_active:
        reasons.append("NGO requirement is inactive.")

    if listing.status != SurplusListing.Status.OPEN:
        reasons.append(f"Surplus listing is not OPEN (status is {listing.status}).")

    if listing.remaining_quantity <= Decimal("0.000"):
        reasons.append("Surplus listing has no remaining quantity available.")

    # 2. Geographic Radius
    max_radius = float(requirement.radius_km or 15.0)
    if distance_km == float("inf"):
        reasons.append("Geographic distance could not be determined due to missing GPS coordinates.")
    elif distance_km > max_radius:
        reasons.append(f"Distance ({distance_km:.1f} km) exceeds requirement operating radius ({max_radius:.1f} km).")

    # 3. Category Match
    req_categories = list(requirement.categories.values_list("id", flat=True))
    if req_categories:
        if not listing.category_id or listing.category_id not in req_categories:
            reasons.append("Listing category does not match requirement requested categories.")

    # 4. Cooked Food Compatibility
    if listing.is_cooked and not requirement.accepts_cooked_food:
        reasons.append("Listing is cooked food, but requirement does not accept cooked food.")

    # 5. Quantity Compatibility (listing remaining must meet minimum requested threshold)
    if listing.remaining_quantity < requirement.min_quantity:
        reasons.append(
            f"Listing remaining quantity ({listing.remaining_quantity} {listing.unit}) is below requirement "
            f"minimum ({requirement.min_quantity} {requirement.unit})."
        )

    # 6. Timing & Expiry Compatibility
    now = timezone.now()
    if listing.available_until <= now:
        reasons.append("Listing available pickup window has already expired.")

    if listing.safe_until and listing.safe_until <= now:
        reasons.append("Listing safe_until food safety threshold has passed.")

    if requirement.needed_by and listing.available_from.date() > requirement.needed_by:
        reasons.append(f"Listing available date ({listing.available_from.date()}) is after requirement needed_by date ({requirement.needed_by}).")

    return (len(reasons) == 0, reasons)


def compute_match_score(
    listing: SurplusListing,
    requirement: NGORequirement,
    distance_km: float,
) -> Dict[str, Any]:
    """
    Computes a composite prioritization match score (0.0 - 100.0) with detailed breakdowns.

    Formula Weights:
    - Distance (30%): Closer NGOs receive higher score.
    - Expiry Urgency (25%): Listings expiring sooner receive higher urgency priority.
    - Quantity Match (20%): Proximity of remaining quantity to requirement target.
    - NGO Reliability (15%): Historical completion rate vs no-shows.
    - Fairness / Recency (10%): Distribution balance favoring NGOs without recent donations.
    """
    ngo = requirement.ngo
    max_radius = float(requirement.radius_km or 15.0)

    # 1. Distance Score (0 - 100)
    if distance_km == float("inf"):
        distance_score = 0.0
    else:
        dist_ratio = max(0.0, min(1.0, distance_km / max(1.0, max_radius)))
        distance_score = round((1.0 - dist_ratio) * 100.0, 1)

    # 2. Urgency Score (0 - 100)
    now = timezone.now()
    cutoff_time = listing.safe_until if listing.safe_until else listing.available_until
    hours_left = max(0.0, (cutoff_time - now).total_seconds() / 3600.0)

    if hours_left <= 4.0:
        urgency_score = 100.0
    elif hours_left <= 8.0:
        urgency_score = 85.0
    elif hours_left <= 18.0:
        urgency_score = 70.0
    elif hours_left <= 36.0:
        urgency_score = 50.0
    else:
        urgency_score = 30.0

    # 3. Quantity Score (0 - 100)
    rem_qty = float(listing.remaining_quantity)
    min_qty = float(requirement.min_quantity)
    max_qty = float(requirement.max_quantity)

    if min_qty <= rem_qty <= max_qty:
        quantity_score = 100.0
    elif rem_qty > max_qty:
        # Full demand met with surplus remaining
        ratio = max_qty / max(1.0, rem_qty)
        quantity_score = round(max(50.0, ratio * 100.0), 1)
    else:
        # Below min_qty (partial fill)
        ratio = rem_qty / max(1.0, min_qty)
        quantity_score = round(max(0.0, ratio * 50.0), 1)

    # 4. Reliability Score (0 - 100)
    # Check historical completed vs no-show requests
    ngo_history = DonationRequest.objects.filter(
        ngo=ngo,
        status__in=[DonationRequest.Status.COMPLETED, DonationRequest.Status.NO_SHOW],
    ).aggregate(
        completed=Count("id", filter=Q(status=DonationRequest.Status.COMPLETED)),
        no_show=Count("id", filter=Q(status=DonationRequest.Status.NO_SHOW)),
    )
    completed_count = ngo_history.get("completed") or 0
    no_show_count = ngo_history.get("no_show") or 0
    total_closed = completed_count + no_show_count

    if total_closed == 0:
        reliability_score = 80.0  # Fair neutral baseline for verified NGOs
    else:
        comp_rate = completed_count / total_closed
        reliability_score = round(comp_rate * 100.0, 1)

    # 5. Fairness / Recency Score (0 - 100)
    # Give priority boost to NGOs that haven't received recent donations
    last_completed = DonationRequest.objects.filter(
        ngo=ngo,
        status=DonationRequest.Status.COMPLETED,
    ).aggregate(latest=Max("updated_at"))["latest"]

    if not last_completed:
        fairness_score = 100.0  # First-time or long-waiting NGO
    else:
        days_since = (now - last_completed).total_seconds() / 86400.0
        if days_since >= 7.0:
            fairness_score = 100.0
        elif days_since >= 3.0:
            fairness_score = 75.0
        elif days_since >= 1.0:
            fairness_score = 50.0
        else:
            fairness_score = 25.0

    # Composite Weighted Total (Rule-Based Base Score)
    composite = round(
        (0.30 * distance_score)
        + (0.25 * urgency_score)
        + (0.20 * quantity_score)
        + (0.15 * reliability_score)
        + (0.10 * fairness_score),
        1,
    )

    from marketplace.learning_layer import evaluate_learned_match_score

    learned_eval = evaluate_learned_match_score(
        listing=listing,
        requirement=requirement,
        distance_km=distance_km,
        base_score=composite,
    )

    return {
        "score": learned_eval["final_score"],
        "base_score": learned_eval["base_score"],
        "learned_probability": learned_eval["learned_probability"],
        "is_fallback": learned_eval["is_fallback"],
        "fallback_reason": learned_eval["fallback_reason"],
        "reasons": learned_eval["reasons"],
        "features": learned_eval.get("features", {}),
        "distance_km": distance_km,
        "breakdown": {
            "distance_score": distance_score,
            "urgency_score": urgency_score,
            "quantity_score": quantity_score,
            "reliability_score": reliability_score,
            "fairness_score": fairness_score,
        },
    }


def find_matching_requirements_for_listing(
    listing: SurplusListing,
    limit: int = 20,
    min_score: float = 0.0,
    compatible_only: bool = True,
) -> List[Dict[str, Any]]:
    """
    Finds and ranks all active NGO requirements that match a given SurplusListing.
    Returns a sorted list of match dicts ordered by composite score descending.
    """
    l_lat, l_lon = get_listing_coordinates(listing)

    # Fetch active requirements for verified NGOs
    requirements = (
        NGORequirement.objects.filter(
            is_active=True,
            ngo__org_type=Organization.Type.NGO,
        )
        .filter(
            Q(ngo__is_verified=True)
            | Q(ngo__verification_status=Organization.VerificationStatus.VERIFIED)
        )
        .select_related("ngo")
        .prefetch_related("categories")
    )

    matches: List[Dict[str, Any]] = []

    for req in requirements:
        ngo_lat, ngo_lon = get_ngo_coordinates(req.ngo)
        dist = haversine_distance(l_lat, l_lon, ngo_lat, ngo_lon)
        is_compat, incompat_reasons = evaluate_compatibility(listing, req, dist)

        if compatible_only and not is_compat:
            continue

        score_info = compute_match_score(listing, req, dist)
        if score_info["score"] < min_score:
            continue

        matches.append({
            "requirement_id": req.id,
            "requirement_title": req.title,
            "ngo_id": req.ngo.id,
            "ngo_name": req.ngo.name,
            "ngo_address": req.ngo.address,
            "ngo_phone": req.ngo.phone,
            "min_quantity": req.min_quantity,
            "max_quantity": req.max_quantity,
            "unit": req.unit,
            "radius_km": req.radius_km,
            "accepts_cooked_food": req.accepts_cooked_food,
            "distance_km": dist,
            "is_compatible": is_compat,
            "incompatibility_reasons": incompat_reasons,
            "score": score_info["score"],
            "base_score": score_info.get("base_score"),
            "learned_probability": score_info.get("learned_probability"),
            "is_fallback": score_info.get("is_fallback", True),
            "fallback_reason": score_info.get("fallback_reason"),
            "reasons": score_info.get("reasons", []),
            "breakdown": score_info["breakdown"],
        })

    # Sort descending by score, tiebreak with closer distance
    matches.sort(key=lambda m: (-m["score"], m["distance_km"]))
    return matches[:limit]


def find_matching_listings_for_requirement(
    requirement: NGORequirement,
    limit: int = 20,
    min_score: float = 0.0,
    compatible_only: bool = True,
) -> List[Dict[str, Any]]:
    """
    Finds and ranks all open SurplusListings that match a given NGORequirement.
    Returns a sorted list of match dicts ordered by composite score descending.
    """
    ngo_lat, ngo_lon = get_ngo_coordinates(requirement.ngo)
    now = timezone.now()

    # Fetch OPEN listings with remaining quantity
    listings = (
        SurplusListing.objects.filter(
            status=SurplusListing.Status.OPEN,
            available_until__gt=now,
        )
        .select_related("donor", "category", "batch")
    )

    matches: List[Dict[str, Any]] = []

    for listing in listings:
        if listing.remaining_quantity <= Decimal("0.000"):
            continue

        l_lat, l_lon = get_listing_coordinates(listing)
        dist = haversine_distance(l_lat, l_lon, ngo_lat, ngo_lon)
        is_compat, incompat_reasons = evaluate_compatibility(listing, requirement, dist)

        if compatible_only and not is_compat:
            continue

        score_info = compute_match_score(listing, requirement, dist)
        if score_info["score"] < min_score:
            continue

        matches.append({
            "listing_id": listing.id,
            "listing_title": listing.title,
            "donor_id": listing.donor.id,
            "donor_name": listing.donor.name,
            "pickup_address": listing.pickup_address,
            "category_id": listing.category_id,
            "category_name": listing.category.name if listing.category else None,
            "remaining_quantity": listing.remaining_quantity,
            "quantity_offered": listing.quantity_offered,
            "quantity_reserved": listing.quantity_reserved,
            "unit": listing.unit,
            "is_cooked": listing.is_cooked,
            "available_from": listing.available_from,
            "available_until": listing.available_until,
            "safe_until": listing.safe_until,
            "distance_km": dist,
            "is_compatible": is_compat,
            "incompatibility_reasons": incompat_reasons,
            "score": score_info["score"],
            "base_score": score_info.get("base_score"),
            "learned_probability": score_info.get("learned_probability"),
            "is_fallback": score_info.get("is_fallback", True),
            "fallback_reason": score_info.get("fallback_reason"),
            "reasons": score_info.get("reasons", []),
            "breakdown": score_info["breakdown"],
        })

    matches.sort(key=lambda m: (-m["score"], m["distance_km"]))
    return matches[:limit]


def generate_match_notifications_for_listing(
    listing: SurplusListing,
    top_n: int = 5,
    min_score: float = 40.0,
) -> List[Notification]:
    """
    Finds top matching NGOs for a listing and dispatches in-app notifications.
    Guarantees idempotency: skips notification if an unread or recent SURPLUS_MATCH
    notification already exists for this NGO and listing.
    """
    matches = find_matching_requirements_for_listing(
        listing=listing,
        limit=top_n,
        min_score=min_score,
        compatible_only=True,
    )

    created_notifications: List[Notification] = []
    seen_ngo_ids = set()

    for match in matches:
        ngo_id = match["ngo_id"]
        if ngo_id in seen_ngo_ids:
            continue
        seen_ngo_ids.add(ngo_id)

        target_org = Organization.objects.filter(id=ngo_id).first()
        if not target_org:
            continue

        # Check existing notification within last 24 hours to prevent duplicate spam
        recent_threshold = timezone.now() - timedelta(hours=24)
        link = f"/marketplace?listing={listing.id}"
        already_notified = Notification.objects.filter(
            organization=target_org,
            type="SURPLUS_MATCH",
            link=link,
            created_at__gte=recent_threshold,
        ).exists()

        if already_notified:
            logger.info("Skipping notification for NGO %s; already notified for listing %s", ngo_id, listing.id)
            continue

        notif = Notification.objects.create(
            organization=target_org,
            type="SURPLUS_MATCH",
            title=f"New Surplus Match: {listing.title}",
            body=(
                f"{listing.donor.name} posted {listing.remaining_quantity} {listing.unit} of "
                f"'{listing.title}' ({match['distance_km']:.1f} km away). Match score: {match['score']:.0f}%."
            ),
            link=link,
        )
        created_notifications.append(notif)
        logger.info("Dispatched match notification #%s to NGO %s for listing #%s", notif.id, target_org.name, listing.id)

    return created_notifications


def batch_run_matching_engine(
    min_score: float = 40.0,
    top_n: int = 5,
) -> Dict[str, int]:
    """
    Iterates over all open surplus listings and runs matching & notification dispatch.
    Returns summary statistics.
    """
    now = timezone.now()
    open_listings = SurplusListing.objects.filter(
        status=SurplusListing.Status.OPEN,
        available_until__gt=now,
    ).order_by("-created_at")

    listings_evaluated = 0
    notifications_created = 0
    total_matches_found = 0

    for listing in open_listings:
        if listing.remaining_quantity <= Decimal("0.000"):
            continue

        listings_evaluated += 1
        matches = find_matching_requirements_for_listing(
            listing=listing,
            limit=top_n,
            min_score=min_score,
            compatible_only=True,
        )
        total_matches_found += len(matches)

        notifs = generate_match_notifications_for_listing(
            listing=listing,
            top_n=top_n,
            min_score=min_score,
        )
        notifications_created += len(notifs)

    logger.info(
        "Batch matching run complete: %d listings evaluated, %d matches found, %d notifications created",
        listings_evaluated,
        total_matches_found,
        notifications_created,
    )

    return {
        "listings_evaluated": listings_evaluated,
        "matches_found": total_matches_found,
        "notifications_created": notifications_created,
    }
