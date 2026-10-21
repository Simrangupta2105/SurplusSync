"""
Home API views (Task B1).
Provides:
- GET /api/v1/home/ (authenticated, tenant-scoped, role-aware summary)
- GET /api/v1/home/public/ (unauthenticated platform totals, cached 10 minutes)
"""
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List

from django.apps import apps
from django.core.cache import cache
from django.db import models
from django.db.models import F, Q, Sum, Case, When
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Organization
from inventory.models import Alert, Batch, ImportJob, POSApiKey, Product
from marketplace.models import (
    DonationRequest,
    DonationStatusHistory,
    NGORequirement,
    Notification,
    SurplusListing,
)


class AuthenticatedHomeView(APIView):
    """
    GET /api/v1/home/
    Authenticated, scoped to the caller's organization, role-aware.
    Returns:
    - greeting (organization name, role, verification status)
    - role-specific counts (Business or NGO only)
    - needs_attention (up to 5 prioritized items)
    - recent_activity (latest 10 status transitions and notifications for this tenant)
    - getting_started (checklist computed from real data)
    - impact_snapshot (last 30 days kg, meals, CO2e)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        user_org = getattr(user, "organization", None)

        if not user_org:
            if user.is_platform_admin:
                return self._get_admin_home(request)
            raise PermissionDenied("Organization context required.")

        now = timezone.now()
        today = now.date()
        role = user_org.org_type

        # 1. Greeting
        greeting = {
            "organization_name": user_org.name,
            "role": role,
            "verification_status": user_org.verification_status,
            "is_verified": user_org.is_verified,
        }

        # 2. Role-specific counts & Needs Attention
        needs_attention: List[Dict[str, Any]] = []

        if role == Organization.Type.BUSINESS:
            # Business metrics
            in_48h = today + timedelta(days=2)
            batches_expiring_48h = Batch.objects.filter(
                organization=user_org,
                status=Batch.Status.ACTIVE,
                expiry_date__gte=today,
                expiry_date__lte=in_48h,
                quantity__gt=0,
            ).count()

            unack_critical_alerts = Alert.objects.filter(
                organization=user_org,
                severity=Alert.Severity.CRITICAL,
                is_acknowledged=False,
                batch__status=Batch.Status.ACTIVE,
                batch__expiry_date__gte=today,
            ).count()

            donation_requests_pending_approval = DonationRequest.objects.filter(
                listing__donor=user_org,
                status=DonationRequest.Status.REQUESTED,
            ).count()

            next_24h = now + timedelta(hours=24)
            pickups_scheduled_24h = DonationRequest.objects.filter(
                listing__donor=user_org,
                status__in=[
                    DonationRequest.Status.APPROVED,
                    DonationRequest.Status.SCHEDULED,
                    DonationRequest.Status.IN_TRANSIT,
                ],
            ).filter(
                Q(confirmed_pickup_start__gte=now, confirmed_pickup_start__lte=next_24h)
                | (Q(confirmed_pickup_start__isnull=True) & Q(proposed_pickup_start__gte=now, proposed_pickup_start__lte=next_24h))
            ).count()

            active_listings = SurplusListing.objects.filter(
                donor=user_org,
                status=SurplusListing.Status.OPEN,
                available_until__gt=now,
            ).count()

            # Prioritized Needs Attention items for Business
            if unack_critical_alerts > 0:
                needs_attention.append({
                    "type": "CRITICAL_ALERT",
                    "title": f"{unack_critical_alerts} unacknowledged critical alert(s)",
                    "link": "/alerts",
                    "urgency": "CRITICAL",
                })
            if batches_expiring_48h > 0:
                needs_attention.append({
                    "type": "BATCH_EXPIRY",
                    "title": f"{batches_expiring_48h} batch(es) expire within 48 hours",
                    "link": "/inventory",
                    "urgency": "HIGH",
                })
            if donation_requests_pending_approval > 0:
                needs_attention.append({
                    "type": "DONATION_APPROVAL",
                    "title": f"{donation_requests_pending_approval} request(s) waiting for your approval",
                    "link": "/donations",
                    "urgency": "HIGH",
                })
            if pickups_scheduled_24h > 0:
                needs_attention.append({
                    "type": "PICKUP_UPCOMING",
                    "title": f"{pickups_scheduled_24h} pickup(s) scheduled in the next 24 hours",
                    "link": "/schedule",
                    "urgency": "MEDIUM",
                })
            if active_listings == 0 and batches_expiring_48h > 0:
                needs_attention.append({
                    "type": "LISTING_SUGGESTION",
                    "title": "You have expiring batches ready to list on the surplus marketplace",
                    "link": "/marketplace",
                    "urgency": "LOW",
                })

            counts = {
                "batches_expiring_48h": batches_expiring_48h,
                "unacknowledged_critical_alerts": unack_critical_alerts,
                "donation_requests_pending_approval": donation_requests_pending_approval,
                "pickups_scheduled_24h": pickups_scheduled_24h,
                "active_listings": active_listings,
            }

            # Checklist for Business
            loc_done = bool(user_org.latitude is not None and user_org.longitude is not None)
            product_done = Product.objects.filter(organization=user_org).exists()
            batch_done = Batch.objects.filter(organization=user_org).exists()
            pos_or_csv_done = (
                ImportJob.objects.filter(organization=user_org).exists()
                or POSApiKey.objects.filter(organization=user_org).exists()
            )
            listing_done = SurplusListing.objects.filter(donor=user_org).exists()

            getting_started = [
                {
                    "id": "set_location",
                    "title": "Set organization location",
                    "done": loc_done,
                    "link": "/settings",
                },
                {
                    "id": "add_product",
                    "title": "Add first product",
                    "done": product_done,
                    "link": "/inventory",
                },
                {
                    "id": "add_batch",
                    "title": "Add first batch",
                    "done": batch_done,
                    "link": "/inventory",
                },
                {
                    "id": "pos_or_csv",
                    "title": "Upload a CSV or create a POS key",
                    "done": pos_or_csv_done,
                    "link": "/import",
                },
                {
                    "id": "create_listing",
                    "title": "Create first surplus listing",
                    "done": listing_done,
                    "link": "/marketplace",
                },
            ]

        else:
            # NGO metrics
            open_requests_awaiting_donor = DonationRequest.objects.filter(
                ngo=user_org,
                status=DonationRequest.Status.REQUESTED,
            ).count()

            next_24h = now + timedelta(hours=24)
            pickups_scheduled_24h = DonationRequest.objects.filter(
                ngo=user_org,
                status__in=[
                    DonationRequest.Status.APPROVED,
                    DonationRequest.Status.SCHEDULED,
                    DonationRequest.Status.IN_TRANSIT,
                ],
            ).filter(
                Q(confirmed_pickup_start__gte=now, confirmed_pickup_start__lte=next_24h)
                | (Q(confirmed_pickup_start__isnull=True) & Q(proposed_pickup_start__gte=now, proposed_pickup_start__lte=next_24h))
            ).count()

            active_requirements = NGORequirement.objects.filter(
                ngo=user_org,
                is_active=True,
            ).count()

            # Find matching listings created in last 24h using matching engine
            new_matching_listings_24h = 0
            if user_org.is_verified:
                try:
                    from marketplace.matching import find_matching_listings
                    active_reqs = NGORequirement.objects.filter(ngo=user_org, is_active=True)
                    matched_listing_ids = set()
                    last_24h = now - timedelta(hours=24)
                    for req in active_reqs:
                        matches = find_matching_listings(req, min_score=0.0)
                        for m in matches:
                            lid = m.get("listing_id")
                            if lid:
                                matched_listing_ids.add(lid)
                    if matched_listing_ids:
                        new_matching_listings_24h = SurplusListing.objects.filter(
                            id__in=matched_listing_ids,
                            created_at__gte=last_24h,
                            status=SurplusListing.Status.OPEN,
                        ).count()
                except Exception:
                    new_matching_listings_24h = 0

            # Prioritized Needs Attention items for NGO
            if not user_org.is_verified:
                needs_attention.append({
                    "type": "VERIFICATION_PENDING",
                    "title": "Account verification pending approval by platform administrator",
                    "link": "/profile",
                    "urgency": "HIGH",
                })
            if pickups_scheduled_24h > 0:
                needs_attention.append({
                    "type": "PICKUP_UPCOMING",
                    "title": f"{pickups_scheduled_24h} pickup(s) scheduled in the next 24 hours",
                    "link": "/schedule",
                    "urgency": "HIGH",
                })
            if open_requests_awaiting_donor > 0:
                needs_attention.append({
                    "type": "REQUEST_PENDING",
                    "title": f"{open_requests_awaiting_donor} donation request(s) awaiting donor response",
                    "link": "/claims",
                    "urgency": "MEDIUM",
                })
            if new_matching_listings_24h > 0:
                needs_attention.append({
                    "type": "SURPLUS_MATCH",
                    "title": f"{new_matching_listings_24h} new matching surplus listing(s) available",
                    "link": "/marketplace",
                    "urgency": "MEDIUM",
                })
            if active_requirements == 0 and user_org.is_verified:
                needs_attention.append({
                    "type": "REQUIREMENT_NEEDED",
                    "title": "Post your food relief requirements to receive matching surplus alerts",
                    "link": "/requirements",
                    "urgency": "LOW",
                })

            counts = {
                "open_requests_awaiting_donor": open_requests_awaiting_donor,
                "pickups_scheduled_24h": pickups_scheduled_24h,
                "new_matching_listings_24h": new_matching_listings_24h,
                "active_requirements": active_requirements,
            }

            # Checklist for NGO
            loc_done = bool(user_org.latitude is not None and user_org.longitude is not None)
            req_done = NGORequirement.objects.filter(ngo=user_org).exists()
            request_done = DonationRequest.objects.filter(ngo=user_org).exists()

            getting_started = [
                {
                    "id": "set_location",
                    "title": "Set organization location",
                    "done": loc_done,
                    "link": "/settings",
                },
                {
                    "id": "create_requirement",
                    "title": "Create first requirement",
                    "done": req_done,
                    "link": "/requirements",
                },
                {
                    "id": "make_request",
                    "title": "Make first request",
                    "done": request_done,
                    "link": "/marketplace",
                },
            ]

        # 3. Recent Activity (latest 10 events strictly scoped to this organization)
        events = []
        if role == Organization.Type.BUSINESS:
            history_qs = (
                DonationStatusHistory.objects.filter(request__listing__donor=user_org)
                .select_related("request")
                .order_by("-created_at")[:10]
            )
            link_prefix = "/donations"
        else:
            history_qs = (
                DonationStatusHistory.objects.filter(request__ngo=user_org)
                .select_related("request")
                .order_by("-created_at")[:10]
            )
            link_prefix = "/claims"

        for h in history_qs:
            events.append({
                "id": f"history-{h.id}",
                "type": "STATUS_HISTORY",
                "title": f"Donation {h.request.code} moved to {h.to_status.replace('_', ' ').title()}",
                "time": h.created_at.isoformat(),
                "link": f"{link_prefix}?code={h.request.code}",
                "_created": h.created_at,
            })

        notif_qs = Notification.objects.filter(organization=user_org).order_by("-created_at")[:10]
        for n in notif_qs:
            events.append({
                "id": f"notif-{n.id}",
                "type": "NOTIFICATION",
                "title": n.title,
                "time": n.created_at.isoformat(),
                "link": n.link or "/notifications",
                "_created": n.created_at,
            })

        events.sort(key=lambda x: x["_created"], reverse=True)
        recent_activity = [
            {
                "id": e["id"],
                "type": e["type"],
                "title": e["title"],
                "time": e["time"],
                "link": e["link"],
            }
            for e in events[:10]
        ]

        # 4. Impact Snapshot for the last 30 days
        cutoff_30d = now - timedelta(days=30)
        completed_statuses = [
            DonationRequest.Status.COLLECTED,
            DonationRequest.Status.COMPLETED,
        ]

        if role == Organization.Type.BUSINESS:
            impact_qs = DonationRequest.objects.filter(
                listing__donor=user_org,
                status__in=completed_statuses,
                updated_at__gte=cutoff_30d,
            )
        else:
            impact_qs = DonationRequest.objects.filter(
                ngo=user_org,
                status__in=completed_statuses,
                updated_at__gte=cutoff_30d,
            )

        agg = impact_qs.aggregate(
            total_kg=Sum(
                Case(
                    When(quantity_collected__isnull=False, then=F("quantity_collected")),
                    When(quantity_approved__isnull=False, then=F("quantity_approved")),
                    default=F("quantity_requested"),
                    output_field=models.DecimalField(),
                )
            )
        )
        total_kg = float(round(agg["total_kg"] or Decimal("0.000"), 2))
        meals = int(round(total_kg * 2.4))
        co2e = round(total_kg * 2.5, 2)

        impact_snapshot = {
            "kg": total_kg,
            "meals": meals,
            "co2e": co2e,
        }

        response_data: Dict[str, Any] = {
            "greeting": greeting,
            "needs_attention": needs_attention[:5],
            "recent_activity": recent_activity,
            "getting_started": getting_started,
            "impact_snapshot": impact_snapshot,
            "counts": counts,
        }

        # Flattens role-specific counts into top-level response for frontend convenience
        for k, v in counts.items():
            response_data[k] = v

        # AI waste-risk summary only if the predictions app exists
        if apps.is_installed("predictions"):
            try:
                from predictions.services import get_waste_risk_summary
                response_data["waste_risk_summary"] = get_waste_risk_summary(user_org)
            except Exception:
                pass

        return Response(response_data)

    def _get_admin_home(self, request) -> Response:
        """Fallback response for platform administrators."""
        greeting = {
            "organization_name": "Platform Administration",
            "role": "ADMIN",
            "verification_status": "VERIFIED",
            "is_verified": True,
        }
        return Response({
            "greeting": greeting,
            "needs_attention": [],
            "recent_activity": [],
            "getting_started": [],
            "impact_snapshot": {"kg": 0.0, "meals": 0, "co2e": 0.0},
            "counts": {},
        })


class PublicHomeView(APIView):
    """
    GET /api/v1/home/public/
    Public unauthenticated platform totals, cached for 10 minutes.
    Returns honest numbers (zeros when empty). Zero organization or personal data.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        cache_key = "home_public_totals"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        completed_statuses = [
            DonationRequest.Status.COLLECTED,
            DonationRequest.Status.COMPLETED,
        ]
        completed_qs = DonationRequest.objects.filter(status__in=completed_statuses)
        completed_donations = completed_qs.count()

        agg = completed_qs.aggregate(
            total_kg=Sum(
                Case(
                    When(quantity_collected__isnull=False, then=F("quantity_collected")),
                    When(quantity_approved__isnull=False, then=F("quantity_approved")),
                    default=F("quantity_requested"),
                    output_field=models.DecimalField(),
                )
            )
        )
        total_kg = float(round(agg["total_kg"] or Decimal("0.000"), 2))
        meals = int(round(total_kg * 2.4))
        co2e = round(total_kg * 2.5, 2)

        verified_donors = Organization.objects.filter(
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
        ).count()
        verified_ngos = Organization.objects.filter(
            org_type=Organization.Type.NGO,
            is_verified=True,
        ).count()

        data = {
            "kg_redistributed": total_kg,
            "meals": meals,
            "co2e": co2e,
            "verified_donors": verified_donors,
            "verified_ngos": verified_ngos,
            "completed_donations": completed_donations,
            # Aliases for frontend counter compatibility
            "total_quantity_donated_kg": total_kg,
            "meals_provided": meals,
            "co2_diverted_kg": co2e,
            "total_donors": verified_donors,
            "total_ngos": verified_ngos,
        }
        cache.set(cache_key, data, timeout=600)  # 10 minutes cache
        return Response(data)
