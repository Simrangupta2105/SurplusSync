"""
Views for the marketplace app.

Implements TASK 2: Endpoints under /api/v1/marketplace/
- GET ratings/pending/ (NGO only): picked-up claims the NGO has not rated yet,
  with donor name, item, quantity, pickup date.
- POST claims/<id>/rate/ {stars, comment} (verified NGO only).
- PATCH ratings/<id>/ within the 7-day edit window.
- GET ratings/mine/ (NGO only): ratings the NGO has given, newest first, paginated.
- GET businesses/<id>/ratings/: average stars, count, star breakdown (1-5 counts)
  and recent non-hidden reviews. Use aggregate queries, not Python loops.
- Add rating_avg and rating_count (annotate) to any donor information returned
  in listing or feed responses.
- 403 for non-NGO users and unverified NGOs; 404 (not 403) when the claim belongs
  to another organization.
"""
from datetime import timedelta
from decimal import Decimal
from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import Avg, Count, FloatField, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Organization
from .models import Claim, DonationRequest, Listing, NGORequirement, Notification, Rating, SurplusListing
from .matching import (
    find_matching_listings_for_requirement,
    find_matching_requirements_for_listing,
    generate_match_notifications_for_listing,
)
from .serializers import (
    ClaimSerializer,
    DonationRequestSerializer,
    ImpactAnalyticsSerializer,
    ListingRequirementMatchSerializer,
    ListingSerializer,
    NGORequirementSerializer,
    NotificationSerializer,
    PendingRatingSerializer,
    PickupScheduleItemSerializer,
    RatingReadSerializer,
    RequirementListingMatchSerializer,
    SurplusListingSerializer,
)
from .services import (
    LifecycleError,
    approve_donation_request,
    cancel_donation_request,
    confirm_receipt,
    confirm_schedule_by_ngo,
    create_donation_request,
    mark_collected,
    mark_in_transit,
    mark_no_show,
    reject_donation_request,
)


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class IsVerifiedNGO(permissions.BasePermission):
    """
    Grants access only to authenticated users belonging to a verified NGO organization.
    Returns 403 Forbidden for non-NGO users and unverified NGOs.
    """
    message = "Only verified NGO organizations are allowed to perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        org = getattr(user, "organization", None)
        if not org or org.org_type != Organization.Type.NGO:
            self.message = "Only NGO users are allowed to perform this action."
            return False
        if getattr(org, "verification_status", None) == Organization.VerificationStatus.SUSPENDED:
            self.message = "Suspended organizations cannot perform this action."
            return False
        if not org.is_verified:
            self.message = "Your NGO organization must be verified to perform this action."
            return False
        return True


# ---------------------------------------------------------------------------
# Helper: QuerySet with annotated donor ratings
# ---------------------------------------------------------------------------

def get_annotated_listings_queryset():
    """
    Annotate listings with donor_rating_avg and donor_rating_count via DB subqueries.
    Excludes hidden ratings.
    """
    donor_avg_subquery = Subquery(
        Rating.objects.filter(business_id=OuterRef("donor_id"), is_hidden=False)
        .values("business_id")
        .annotate(avg=Avg("stars"))
        .values("avg")[:1],
        output_field=FloatField(),
    )
    donor_cnt_subquery = Coalesce(
        Subquery(
            Rating.objects.filter(business_id=OuterRef("donor_id"), is_hidden=False)
            .values("business_id")
            .annotate(cnt=Count("id"))
            .values("cnt")[:1],
            output_field=IntegerField(),
        ),
        0,
    )
    return Listing.objects.select_related("donor", "batch").annotate(
        donor_rating_avg=donor_avg_subquery,
        donor_rating_count=donor_cnt_subquery,
    )


# ---------------------------------------------------------------------------
# 1. GET ratings/pending/ (NGO only)
# ---------------------------------------------------------------------------

class PendingRatingsView(APIView):
    """
    GET /api/v1/marketplace/ratings/pending/
    Returns picked-up claims the NGO has not rated yet, with donor name, item,
    quantity, and pickup date.
    403 for non-NGO users and unverified NGOs.
    """
    permission_classes = [permissions.IsAuthenticated, IsVerifiedNGO]

    def get(self, request):
        user_org = request.user.organization
        queryset = (
            Claim.objects.filter(
                ngo=user_org,
                status=Claim.Status.PICKED_UP,
                rating__isnull=True,
            )
            .select_related("listing", "listing__donor")
            .order_by("-updated_at")
        )

        if "page" in request.query_params:
            paginator = PageNumberPagination()
            page = paginator.paginate_queryset(queryset, request)
            serializer = PendingRatingSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = PendingRatingSerializer(queryset, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# 2. POST claims/<id>/rate/ (verified NGO only)
# ---------------------------------------------------------------------------

class RateClaimView(APIView):
    """
    POST /api/v1/marketplace/claims/<id>/rate/
    Rate the business that donated food for a PICKED_UP claim.
    403 for non-NGO users and unverified NGOs.
    404 (not 403) when the claim belongs to another organization.
    """
    permission_classes = [permissions.IsAuthenticated, IsVerifiedNGO]

    def post(self, request, claim_id):
        user_org = request.user.organization
        # Return 404 (not 403) if claim doesn't exist or belongs to another organization
        claim = get_object_or_404(Claim, pk=claim_id)
        if claim.ngo_id != user_org.id:
            raise Http404("No Claim matches the given query.")

        # Business rule 1: claim must be PICKED_UP
        if claim.status != Claim.Status.PICKED_UP:
            return Response(
                {"detail": "You can only rate a claim that has been picked up."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Business rule 2: one rating per claim
        if hasattr(claim, "rating") or Rating.objects.filter(claim=claim).exists():
            return Response(
                {"detail": "A rating already exists for this claim."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate stars
        stars = request.data.get("stars")
        if stars is None:
            return Response(
                {"stars": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            stars = int(stars)
            if not (1 <= stars <= 5):
                raise ValueError()
        except (ValueError, TypeError):
            return Response(
                {"stars": ["Stars must be an integer between 1 and 5."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate comment (optional, max 500 chars)
        comment = str(request.data.get("comment", "") or "").strip()
        if len(comment) > 500:
            return Response(
                {"comment": ["Ensure this field has no more than 500 characters."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create rating: ngo and business are copied from claim in Rating.save()
        # Client-sent business or ngo ids are completely ignored.
        rating = Rating(
            claim=claim,
            stars=stars,
            comment=comment,
        )
        try:
            rating.save()
        except IntegrityError:
            return Response(
                {"detail": "A rating already exists for this claim."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(RatingReadSerializer(rating).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# 3. GET / PATCH ratings/<id>/ (within 7-day edit window)
# ---------------------------------------------------------------------------

class RatingDetailView(APIView):
    """
    GET /api/v1/marketplace/ratings/<id>/
    PATCH /api/v1/marketplace/ratings/<id>/
    Allows editing stars and comment within 7 days of creation.
    403 for non-NGO users and unverified NGOs.
    404 (not 403) when the rating belongs to another organization.
    """
    permission_classes = [permissions.IsAuthenticated, IsVerifiedNGO]

    def get(self, request, pk):
        user_org = request.user.organization
        rating = get_object_or_404(Rating, pk=pk)
        if rating.ngo_id != user_org.id:
            raise Http404("No Rating matches the given query.")
        return Response(RatingReadSerializer(rating).data)

    def patch(self, request, pk):
        user_org = request.user.organization
        rating = get_object_or_404(Rating, pk=pk)
        if rating.ngo_id != user_org.id:
            raise Http404("No Rating matches the given query.")

        # Business rule: edit allowed within 7 days, locked after
        if not rating.is_editable():
            return Response(
                {"detail": "This rating is locked; the 7-day edit window has passed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update stars if supplied
        if "stars" in request.data:
            stars = request.data["stars"]
            try:
                stars = int(stars)
                if not (1 <= stars <= 5):
                    raise ValueError()
                rating.stars = stars
            except (ValueError, TypeError):
                return Response(
                    {"stars": ["Stars must be an integer between 1 and 5."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Update comment if supplied
        if "comment" in request.data:
            comment = str(request.data.get("comment", "") or "").strip()
            if len(comment) > 500:
                return Response(
                    {"comment": ["Ensure this field has no more than 500 characters."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            rating.comment = comment

        # Client-supplied ngo, business, claim, etc. are ignored
        rating.save()
        return Response(RatingReadSerializer(rating).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# 4. GET ratings/mine/ (NGO only, paginated)
# ---------------------------------------------------------------------------

class MyRatingsView(APIView):
    """
    GET /api/v1/marketplace/ratings/mine/
    Returns ratings the NGO has given, newest first, paginated.
    403 for non-NGO users and unverified NGOs.
    """
    permission_classes = [permissions.IsAuthenticated, IsVerifiedNGO]

    def get(self, request):
        user_org = request.user.organization
        queryset = (
            Rating.objects.filter(
                ngo=user_org,
                is_hidden=False,
            )
            .select_related("business", "claim", "claim__listing")
            .order_by("-created_at")
        )

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = RatingReadSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# 5. GET businesses/<id>/ratings/
# ---------------------------------------------------------------------------

class BusinessRatingsView(APIView):
    """
    GET /api/v1/marketplace/businesses/<id>/ratings/
    Returns average stars, count, star breakdown (1-5 counts) and recent
    non-hidden reviews.
    All aggregations are computed with database queries, not Python loops.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, business_id):
        business = get_object_or_404(Organization, pk=business_id)
        ratings = Rating.objects.filter(business=business, is_hidden=False)

        # Aggregate queries (no Python loops)
        stats = ratings.aggregate(
            avg=Avg("stars"),
            count=Count("id"),
            star_1=Count("id", filter=Q(stars=1)),
            star_2=Count("id", filter=Q(stars=2)),
            star_3=Count("id", filter=Q(stars=3)),
            star_4=Count("id", filter=Q(stars=4)),
            star_5=Count("id", filter=Q(stars=5)),
        )

        breakdown = {
            1: stats["star_1"],
            2: stats["star_2"],
            3: stats["star_3"],
            4: stats["star_4"],
            5: stats["star_5"],
            "1": stats["star_1"],
            "2": stats["star_2"],
            "3": stats["star_3"],
            "4": stats["star_4"],
            "5": stats["star_5"],
        }

        recent_reviews = (
            ratings.select_related("ngo", "claim")
            .order_by("-created_at")[:5]
        )

        data = {
            "business_id": business.id,
            "business_name": business.name,
            "rating_avg": round(float(stats["avg"]), 2) if stats["avg"] is not None else None,
            "rating_count": stats["count"],
            "breakdown": breakdown,
            "recent_reviews": RatingReadSerializer(recent_reviews, many=True).data,
        }
        return Response(data)


# ---------------------------------------------------------------------------
# 6. Listing and Feed responses (annotated with donor rating info)
# ---------------------------------------------------------------------------

class ListingListView(APIView):
    """
    GET /api/v1/marketplace/listings/
    Returns listings with annotated donor rating_avg and rating_count.
    Supports filtering by ?status=, ?donor=, ?mine=true, ?category=, ?is_cooked=, ?search=
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = get_annotated_listings_queryset()

        status_param = request.query_params.get("status")
        if status_param:
            statuses = [s.strip() for s in status_param.split(",") if s.strip()]
            queryset = queryset.filter(status__in=statuses)

        if request.query_params.get("mine", "").lower() in ("true", "1") and request.user.is_authenticated:
            user_org = getattr(request.user, "organization", None)
            if user_org:
                queryset = queryset.filter(donor=user_org)

        donor_param = request.query_params.get("donor")
        if donor_param:
            queryset = queryset.filter(donor_id=donor_param)

        category_param = request.query_params.get("category")
        if category_param:
            queryset = queryset.filter(category_id=category_param)

        cooked_param = request.query_params.get("is_cooked")
        if cooked_param is not None:
            queryset = queryset.filter(is_cooked=cooked_param.lower() in ("true", "1"))

        search_param = request.query_params.get("search")
        if search_param:
            queryset = queryset.filter(
                Q(title__icontains=search_param)
                | Q(description__icontains=search_param)
                | Q(donor__name__icontains=search_param)
            )

        queryset = queryset.order_by("-created_at")

        if "page" in request.query_params:
            paginator = PageNumberPagination()
            page = paginator.paginate_queryset(queryset, request)
            serializer = ListingSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = ListingSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)
        org = getattr(user, "organization", None)
        if not org or org.org_type != Organization.Type.BUSINESS:
            return Response({"detail": "Only business organizations can list food."}, status=status.HTTP_403_FORBIDDEN)
        if getattr(org, "verification_status", None) == Organization.VerificationStatus.SUSPENDED:
            return Response({"detail": "Suspended organizations cannot list food."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ListingSerializer(data=request.data)
        if serializer.is_valid():
            listing = serializer.save(donor=org)
            return Response(ListingSerializer(listing).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ListingDetailView(APIView):
    """
    GET /api/v1/marketplace/listings/<pk>/
    PATCH /api/v1/marketplace/listings/<pk>/
    DELETE /api/v1/marketplace/listings/<pk>/
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        listing = get_annotated_listings_queryset().filter(pk=pk).first()
        if not listing:
            raise Http404("Listing not found.")
        return Response(ListingSerializer(listing).data)

    def patch(self, request, pk):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)

        listing = get_object_or_404(SurplusListing, pk=pk)
        user_org = getattr(user, "organization", None)
        if not user.is_platform_admin and (not user_org or listing.donor_id != user_org.id):
            raise Http404("Listing not found.")

        # Business rule: cannot reduce quantity_offered below quantity_reserved
        if "quantity_offered" in request.data:
            try:
                new_qty = Decimal(str(request.data["quantity_offered"]))
                if new_qty < listing.quantity_reserved:
                    return Response(
                        {"quantity_offered": [f"Cannot reduce offered quantity below reserved quantity ({listing.quantity_reserved} {listing.unit})."]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception:
                pass

        serializer = ListingSerializer(listing, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(ListingSerializer(updated).data)

    def delete(self, request, pk):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)

        listing = get_object_or_404(SurplusListing, pk=pk)
        user_org = getattr(user, "organization", None)
        if not user.is_platform_admin and (not user_org or listing.donor_id != user_org.id):
            raise Http404("Listing not found.")

        listing.status = SurplusListing.Status.CANCELLED
        listing.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)



class FeedListView(APIView):
    """
    GET /api/v1/marketplace/feed/
    Returns open listings for NGOs with annotated donor rating_avg and rating_count.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = (
            get_annotated_listings_queryset()
            .filter(status=Listing.Status.OPEN)
            .order_by("-created_at")
        )
        if "page" in request.query_params:
            paginator = PageNumberPagination()
            page = paginator.paginate_queryset(queryset, request)
            serializer = ListingSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = ListingSerializer(queryset, many=True)
        return Response(serializer.data)


class ClaimListView(APIView):
    """
    GET /api/v1/marketplace/claims/
    Returns claims for the caller's organization.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_org = getattr(request.user, "organization", None)
        if not user_org:
            return Response([])
        if user_org.org_type == Organization.Type.NGO:
            queryset = Claim.objects.filter(ngo=user_org)
        else:
            queryset = Claim.objects.filter(listing__donor=user_org)
        queryset = queryset.select_related("listing", "listing__donor", "ngo").order_by("-created_at")
        serializer = ClaimSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)
        org = getattr(user, "organization", None)
        if not org or org.org_type != Organization.Type.NGO:
            return Response({"detail": "Only NGO organizations can claim food."}, status=status.HTTP_403_FORBIDDEN)
        if getattr(org, "verification_status", None) == Organization.VerificationStatus.SUSPENDED:
            return Response({"detail": "Suspended organizations cannot claim food."}, status=status.HTTP_403_FORBIDDEN)
        if not org.is_verified:
            return Response({"detail": "Your NGO organization must be verified to claim food."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ClaimSerializer(data=request.data)
        if serializer.is_valid():
            claim = serializer.save(ngo=org)
            return Response(ClaimSerializer(claim).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Donation Request Lifecycle Views (Task 2)
# ---------------------------------------------------------------------------

class DonationRequestListView(APIView):
    """
    GET /api/v1/marketplace/requests/
    POST /api/v1/marketplace/requests/
    Tenant-scoped list and create for donation requests.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_org = getattr(request.user, "organization", None)
        if not user_org:
            return Response([])

        if user_org.org_type == Organization.Type.BUSINESS:
            queryset = DonationRequest.objects.filter(listing__donor=user_org)
        else:
            queryset = DonationRequest.objects.filter(ngo=user_org)

        status_param = request.query_params.get("status")
        if status_param:
            statuses = [s.strip() for s in status_param.split(",") if s.strip()]
            queryset = queryset.filter(status__in=statuses)

        listing_param = request.query_params.get("listing")
        if listing_param:
            queryset = queryset.filter(listing_id=listing_param)

        queryset = queryset.select_related("listing", "listing__donor", "ngo").prefetch_related("status_history").order_by("-requested_at")

        if request.query_params.get("include_counts", "").lower() in ("true", "1", "yes"):
            base_qs = DonationRequest.objects.filter(listing__donor=user_org) if user_org.org_type == Organization.Type.BUSINESS else DonationRequest.objects.filter(ngo=user_org)
            counts = {
                "all": base_qs.count(),
                "pending": base_qs.filter(status=DonationRequest.Status.REQUESTED).count(),
                "scheduled": base_qs.filter(status__in=[DonationRequest.Status.APPROVED, DonationRequest.Status.SCHEDULED]).count(),
                "in_transit": base_qs.filter(status=DonationRequest.Status.IN_TRANSIT).count(),
                "completed": base_qs.filter(status__in=[DonationRequest.Status.COLLECTED, DonationRequest.Status.COMPLETED]).count(),
                "rejected": base_qs.filter(status__in=[DonationRequest.Status.REJECTED, DonationRequest.Status.CANCELLED, DonationRequest.Status.NO_SHOW, DonationRequest.Status.EXPIRED]).count(),
            }
            serializer = DonationRequestSerializer(queryset, many=True)
            return Response({"results": serializer.data, "counts": counts})

        serializer = DonationRequestSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        listing_id = request.data.get("listing") or request.data.get("listing_id")
        if not listing_id:
            return Response({"detail": "listing is required.", "error": "listing is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            req = create_donation_request(
                user=user,
                listing_id=listing_id,
                quantity_requested=request.data.get("quantity_requested"),
                proposed_pickup_start=request.data.get("proposed_pickup_start"),
                proposed_pickup_end=request.data.get("proposed_pickup_end"),
                note=request.data.get("note", ""),
                contact_name=request.data.get("contact_name", ""),
                contact_phone=request.data.get("contact_phone", ""),
            )
            return Response(DonationRequestSerializer(req).data, status=status.HTTP_201_CREATED)
        except LifecycleError as e:
            return Response({"detail": e.message, "error": e.message}, status=e.status_code)


class DonationRequestDetailView(APIView):
    """
    GET /api/v1/marketplace/requests/<code_or_id>/
    Tenant-scoped detail view with status history.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, code_or_id):
        user_org = getattr(request.user, "organization", None)
        if not user_org:
            raise Http404

        if str(code_or_id).isdigit():
            req = DonationRequest.objects.filter(id=int(code_or_id)).select_related("listing", "listing__donor", "ngo").prefetch_related("status_history").first()
        else:
            req = DonationRequest.objects.filter(code=str(code_or_id).strip()).select_related("listing", "listing__donor", "ngo").prefetch_related("status_history").first()

        if not req:
            raise Http404
        if req.ngo_id != user_org.id and req.listing.donor_id != user_org.id:
            raise Http404

        return Response(DonationRequestSerializer(req).data)


class DonationRequestApproveView(APIView):
    """
    POST /api/v1/marketplace/requests/<code_or_id>/approve/
    Business donor approves request (may reduce quantity or change pickup window).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code_or_id):
        try:
            req = approve_donation_request(
                user=request.user,
                request_id_or_code=code_or_id,
                quantity_approved=request.data.get("quantity_approved"),
                pickup_start=request.data.get("confirmed_pickup_start") or request.data.get("pickup_start"),
                pickup_end=request.data.get("confirmed_pickup_end") or request.data.get("pickup_end"),
            )
            return Response(DonationRequestSerializer(req).data, status=status.HTTP_200_OK)
        except LifecycleError as e:
            return Response({"detail": e.message, "error": e.message}, status=e.status_code)


class DonationRequestConfirmScheduleView(APIView):
    """
    POST /api/v1/marketplace/requests/<code_or_id>/confirm-schedule/
    NGO confirms a changed pickup window, moving request from APPROVED to SCHEDULED.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code_or_id):
        try:
            req = confirm_schedule_by_ngo(user=request.user, request_id_or_code=code_or_id)
            return Response(DonationRequestSerializer(req).data, status=status.HTTP_200_OK)
        except LifecycleError as e:
            return Response({"detail": e.message, "error": e.message}, status=e.status_code)


class DonationRequestRejectView(APIView):
    """
    POST /api/v1/marketplace/requests/<code_or_id>/reject/
    Business donor rejects request with a reason.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code_or_id):
        try:
            req = reject_donation_request(
                user=request.user,
                request_id_or_code=code_or_id,
                rejection_reason=request.data.get("rejection_reason") or request.data.get("reason"),
            )
            return Response(DonationRequestSerializer(req).data, status=status.HTTP_200_OK)
        except LifecycleError as e:
            return Response({"detail": e.message, "error": e.message}, status=e.status_code)


class DonationRequestCancelView(APIView):
    """
    POST /api/v1/marketplace/requests/<code_or_id>/cancel/
    NGO or donor cancels an active request (releases reservation).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code_or_id):
        try:
            req = cancel_donation_request(
                user=request.user,
                request_id_or_code=code_or_id,
                reason=request.data.get("reason", ""),
            )
            return Response(DonationRequestSerializer(req).data, status=status.HTTP_200_OK)
        except LifecycleError as e:
            return Response({"detail": e.message, "error": e.message}, status=e.status_code)


class DonationRequestInTransitView(APIView):
    """
    POST /api/v1/marketplace/requests/<code_or_id>/in-transit/
    NGO marks "On my way" when SCHEDULED and within 2 hours of pickup start.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code_or_id):
        try:
            req = mark_in_transit(user=request.user, request_id_or_code=code_or_id)
            return Response(DonationRequestSerializer(req).data, status=status.HTTP_200_OK)
        except LifecycleError as e:
            return Response({"detail": e.message, "error": e.message}, status=e.status_code)


class DonationRequestCollectView(APIView):
    """
    POST /api/v1/marketplace/requests/<code_or_id>/collect/
    Business donor marks collected with actual handed over quantity.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code_or_id):
        qty_col = request.data.get("quantity_collected")
        if qty_col is None:
            return Response(
                {"detail": "quantity_collected is required.", "error": "quantity_collected is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            req = mark_collected(user=request.user, request_id_or_code=code_or_id, quantity_collected=qty_col)
            return Response(DonationRequestSerializer(req).data, status=status.HTTP_200_OK)
        except LifecycleError as e:
            return Response({"detail": e.message, "error": e.message}, status=e.status_code)


class DonationRequestConfirmReceiptView(APIView):
    """
    POST /api/v1/marketplace/requests/<code_or_id>/confirm-receipt/
    NGO confirms receipt of donation, completing the request.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code_or_id):
        try:
            req = confirm_receipt(user=request.user, request_id_or_code=code_or_id)
            return Response(DonationRequestSerializer(req).data, status=status.HTTP_200_OK)
        except LifecycleError as e:
            return Response({"detail": e.message, "error": e.message}, status=e.status_code)


class DonationRequestNoShowView(APIView):
    """
    POST /api/v1/marketplace/requests/<code_or_id>/no-show/
    Business donor marks no-show after pickup window has ended (releases reservation).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code_or_id):
        try:
            req = mark_no_show(user=request.user, request_id_or_code=code_or_id)
            return Response(DonationRequestSerializer(req).data, status=status.HTTP_200_OK)
        except LifecycleError as e:
            return Response({"detail": e.message, "error": e.message}, status=e.status_code)


# ---------------------------------------------------------------------------
# Matching Engine & NGO Requirements (Task 3)
# ---------------------------------------------------------------------------

class NGORequirementListCreateView(APIView):
    """
    GET /api/v1/marketplace/requirements/
    POST /api/v1/marketplace/requirements/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        user_org = getattr(user, "organization", None)

        if user_org and user_org.org_type == Organization.Type.NGO:
            qs = NGORequirement.objects.filter(ngo=user_org)
        else:
            qs = NGORequirement.objects.filter(is_active=True)

        # Filters
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("true", "1"))

        category_id = request.query_params.get("category")
        if category_id:
            qs = qs.filter(categories__id=category_id)

        accepts_cooked = request.query_params.get("accepts_cooked")
        if accepts_cooked is not None:
            qs = qs.filter(accepts_cooked_food=accepts_cooked.lower() in ("true", "1"))

        qs = qs.select_related("ngo").prefetch_related("categories").order_by("-created_at")

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = NGORequirementSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = NGORequirementSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        user_org = getattr(user, "organization", None)

        if not user_org or user_org.org_type != Organization.Type.NGO:
            return Response(
                {"detail": "Only verified NGO organizations can declare food requirements."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = NGORequirementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        req = serializer.save(ngo=user_org)
        return Response(NGORequirementSerializer(req).data, status=status.HTTP_201_CREATED)


class NGORequirementDetailView(APIView):
    """
    GET /api/v1/marketplace/requirements/<pk>/
    PATCH /api/v1/marketplace/requirements/<pk>/
    DELETE /api/v1/marketplace/requirements/<pk>/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        req = get_object_or_404(
            NGORequirement.objects.select_related("ngo").prefetch_related("categories"),
            pk=pk,
        )
        user_org = getattr(request.user, "organization", None)
        # Cross-tenant isolation: if NGO, cannot enumerate other NGOs' private requirements
        if user_org and user_org.org_type == Organization.Type.NGO and req.ngo_id != user_org.id:
            raise Http404("Requirement not found.")

        return Response(NGORequirementSerializer(req).data)

    def patch(self, request, pk):
        req = get_object_or_404(NGORequirement, pk=pk)
        user_org = getattr(request.user, "organization", None)

        if not request.user.is_platform_admin and (not user_org or req.ngo_id != user_org.id):
            raise Http404("Requirement not found.")

        serializer = NGORequirementSerializer(req, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(NGORequirementSerializer(updated).data)

    def delete(self, request, pk):
        req = get_object_or_404(NGORequirement, pk=pk)
        user_org = getattr(request.user, "organization", None)

        if not request.user.is_platform_admin and (not user_org or req.ngo_id != user_org.id):
            raise Http404("Requirement not found.")

        req.is_active = False
        req.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListingMatchesView(APIView):
    """
    GET /api/v1/marketplace/listings/<listing_id>/matches/
    Returns ranked NGO requirements matching a surplus listing.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, listing_id):
        listing = get_object_or_404(
            SurplusListing.objects.select_related("donor", "category", "batch"),
            pk=listing_id,
        )
        user_org = getattr(request.user, "organization", None)

        # Cross-tenant protection: only listing donor or platform admin can view listing matches
        if not request.user.is_platform_admin and (not user_org or listing.donor_id != user_org.id):
            raise Http404("Listing not found.")

        limit = int(request.query_params.get("limit", 20))
        min_score = float(request.query_params.get("min_score", 0.0))
        compatible_only = request.query_params.get("compatible_only", "true").lower() in ("true", "1")

        matches = find_matching_requirements_for_listing(
            listing=listing,
            limit=limit,
            min_score=min_score,
            compatible_only=compatible_only,
        )
        serializer = ListingRequirementMatchSerializer(matches, many=True)
        return Response({
            "listing_id": listing.id,
            "listing_title": listing.title,
            "matches_count": len(matches),
            "matches": serializer.data,
        })


class ListingNotifyMatchesView(APIView):
    """
    POST /api/v1/marketplace/listings/<listing_id>/notify-matches/
    Dispatches in-app notifications to top matching NGOs for a listing.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, listing_id):
        listing = get_object_or_404(
            SurplusListing.objects.select_related("donor"),
            pk=listing_id,
        )
        user_org = getattr(request.user, "organization", None)

        if not request.user.is_platform_admin and (not user_org or listing.donor_id != user_org.id):
            raise Http404("Listing not found.")

        top_n = int(request.data.get("top_n", request.query_params.get("top_n", 5)))
        min_score = float(request.data.get("min_score", request.query_params.get("min_score", 40.0)))

        notifs = generate_match_notifications_for_listing(
            listing=listing,
            top_n=top_n,
            min_score=min_score,
        )

        return Response({
            "status": "success",
            "listing_id": listing.id,
            "notifications_dispatched": len(notifs),
        }, status=status.HTTP_200_OK)


class RequirementMatchesView(APIView):
    """
    GET /api/v1/marketplace/requirements/<pk>/matches/
    Returns ranked surplus listings matching an NGO requirement.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        req = get_object_or_404(
            NGORequirement.objects.select_related("ngo").prefetch_related("categories"),
            pk=pk,
        )
        user_org = getattr(request.user, "organization", None)

        # Cross-tenant protection: only requirement owner NGO or platform admin can view its matches
        if not request.user.is_platform_admin and (not user_org or req.ngo_id != user_org.id):
            raise Http404("Requirement not found.")

        limit = int(request.query_params.get("limit", 20))
        min_score = float(request.query_params.get("min_score", 0.0))
        compatible_only = request.query_params.get("compatible_only", "true").lower() in ("true", "1")

        matches = find_matching_listings_for_requirement(
            requirement=req,
            limit=limit,
            min_score=min_score,
            compatible_only=compatible_only,
        )
        serializer = RequirementListingMatchSerializer(matches, many=True)
        return Response({
            "requirement_id": req.id,
            "requirement_title": req.title,
            "matches_count": len(matches),
            "matches": serializer.data,
        })


# ---------------------------------------------------------------------------
# Pickup Schedule, Impact Analytics & Notifications (Task 4)
# ---------------------------------------------------------------------------

class PickupScheduleView(APIView):
    """
    GET /api/v1/marketplace/schedule/
    Returns calendar / agenda view of scheduled pickups for the authenticated organization.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_org = getattr(request.user, "organization", None)
        if not user_org and not request.user.is_platform_admin:
            raise Http404("Organization context required.")

        if request.user.is_platform_admin:
            qs = DonationRequest.objects.all()
        elif user_org.org_type == Organization.Type.BUSINESS:
            qs = DonationRequest.objects.filter(listing__donor=user_org)
        else:
            qs = DonationRequest.objects.filter(ngo=user_org)

        # Status filtering
        status_param = request.query_params.get("status")
        if status_param:
            if status_param.upper() != "ALL":
                statuses = [s.strip().upper() for s in status_param.split(",") if s.strip()]
                qs = qs.filter(status__in=statuses)
        else:
            # Default active scheduled pickups
            qs = qs.filter(
                status__in=[
                    DonationRequest.Status.APPROVED,
                    DonationRequest.Status.SCHEDULED,
                    DonationRequest.Status.IN_TRANSIT,
                ]
            )

        # Date filtering
        start_date = request.query_params.get("start_date")
        if start_date:
            qs = qs.filter(
                Q(confirmed_pickup_start__date__gte=start_date)
                | Q(proposed_pickup_start__date__gte=start_date)
            )

        end_date = request.query_params.get("end_date")
        if end_date:
            qs = qs.filter(
                Q(confirmed_pickup_end__date__lte=end_date)
                | Q(proposed_pickup_end__date__lte=end_date)
            )

        qs = qs.select_related("listing", "listing__donor", "listing__category", "ngo").order_by(
            "confirmed_pickup_start", "proposed_pickup_start"
        )

        now = timezone.now()
        items = []
        for r in qs:
            start = r.confirmed_pickup_start or r.proposed_pickup_start
            end = r.confirmed_pickup_end or r.proposed_pickup_end
            is_overdue = bool(
                end
                and end < now
                and r.status not in [
                    DonationRequest.Status.COLLECTED,
                    DonationRequest.Status.COMPLETED,
                    DonationRequest.Status.CANCELLED,
                    DonationRequest.Status.REJECTED,
                    DonationRequest.Status.EXPIRED,
                ]
            )
            is_today = bool(start and start.date() == now.date())
            time_until = int((start - now).total_seconds() / 60) if start else None

            items.append({
                "request_id": r.id,
                "request_code": r.code,
                "status": r.status,
                "listing_id": r.listing_id,
                "item_title": r.listing.title,
                "category_name": r.listing.category.name if r.listing.category else None,
                "quantity": r.quantity_approved or r.quantity_requested,
                "unit": r.listing.unit,
                "pickup_window_start": start,
                "pickup_window_end": end,
                "donor_id": r.listing.donor_id,
                "donor_name": r.listing.donor.name,
                "donor_address": r.listing.pickup_address or r.listing.donor.address,
                "donor_phone": r.listing.donor.phone,
                "ngo_id": r.ngo_id,
                "ngo_name": r.ngo.name,
                "contact_name": r.contact_name,
                "contact_phone": r.contact_phone,
                "note": r.note,
                "is_overdue": is_overdue,
                "is_today": is_today,
                "time_until_pickup_minutes": time_until,
            })

        serializer = PickupScheduleItemSerializer(items, many=True)
        return Response({
            "results": serializer.data,
            "total_count": len(items),
        })


class ImpactAnalyticsView(APIView):
    """
    GET /api/v1/marketplace/impact/
    Returns cumulative and monthly breakdown metrics for food rescued and redistributed.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_org = getattr(request.user, "organization", None)
        if not user_org and not request.user.is_platform_admin:
            raise Http404("Organization context required.")

        completed_statuses = [
            DonationRequest.Status.COLLECTED,
            DonationRequest.Status.COMPLETED,
        ]

        if request.user.is_platform_admin:
            qs = DonationRequest.objects.filter(status__in=completed_statuses)
        elif user_org.org_type == Organization.Type.BUSINESS:
            qs = DonationRequest.objects.filter(listing__donor=user_org, status__in=completed_statuses)
        else:
            qs = DonationRequest.objects.filter(ngo=user_org, status__in=completed_statuses)

        qs = qs.select_related("listing", "listing__category")

        total_completed = qs.count()
        total_quantity_kg = sum(
            float(r.quantity_approved or r.quantity_requested)
            for r in qs
        )
        total_quantity_kg = round(total_quantity_kg, 2)

        # Standard food redistribution multipliers
        meals_provided = int(round(total_quantity_kg * 2.4))
        co2_diverted_kg = round(total_quantity_kg * 2.5, 2)
        water_saved_liters = int(round(total_quantity_kg * 1000.0))
        financial_value_saved = round(total_quantity_kg * 150.0, 2)  # Benchmark ~₹150/kg

        # Category breakdown
        category_map = {}
        for r in qs:
            cat_name = r.listing.category.name if (r.listing and r.listing.category) else "Uncategorized"
            qty = float(r.quantity_approved or r.quantity_requested)
            category_map[cat_name] = category_map.get(cat_name, 0.0) + qty

        category_breakdown = []
        for cat_name, cat_qty in sorted(category_map.items(), key=lambda x: -x[1]):
            percentage = round((cat_qty / max(0.001, total_quantity_kg)) * 100.0, 1) if total_quantity_kg > 0 else 0.0
            category_breakdown.append({
                "category_name": cat_name,
                "quantity_kg": round(cat_qty, 2),
                "percentage": percentage,
            })

        # Monthly trend (last 6 months chronological)
        now = timezone.now()
        monthly_trend = []
        for i in range(5, -1, -1):
            target_date = now - timedelta(days=i * 30)
            month_str = target_date.strftime("%Y-%m")
            # Filter requests in this calendar month
            month_qs = [
                r for r in qs
                if (r.confirmed_pickup_end or r.requested_at).strftime("%Y-%m") == month_str
            ]
            month_qty = sum(float(r.quantity_approved or r.quantity_requested) for r in month_qs)
            monthly_trend.append({
                "month": month_str,
                "quantity_kg": round(month_qty, 2),
                "meals": int(round(month_qty * 2.4)),
                "donations_count": len(month_qs),
            })

        data = {
            "total_donations_completed": total_completed,
            "total_quantity_donated_kg": total_quantity_kg,
            "meals_provided": meals_provided,
            "co2_diverted_kg": co2_diverted_kg,
            "water_saved_liters": water_saved_liters,
            "financial_value_saved": financial_value_saved,
            "category_breakdown": category_breakdown,
            "monthly_trend": monthly_trend,
        }

        serializer = ImpactAnalyticsSerializer(data)
        return Response(serializer.data)


class PublicImpactAnalyticsView(APIView):
    """
    GET /api/v1/marketplace/impact/public/
    Platform-wide aggregate totals (kg, meals, CO2e, donors, NGOs) cached for 10 minutes.
    No authentication required, zero organization or personal details leaked.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        cache_key = "marketplace_public_impact_metrics"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        completed_statuses = [
            DonationRequest.Status.COLLECTED,
            DonationRequest.Status.COMPLETED,
        ]
        qs = DonationRequest.objects.filter(status__in=completed_statuses)
        total_quantity_kg = sum(
            float(r.quantity_approved or r.quantity_requested)
            for r in qs
        )
        total_quantity_kg = round(total_quantity_kg, 2)
        # Standard benchmark: 1 meal = 0.42 kg (WRAP / FAO)
        meals_provided = int(round(total_quantity_kg / 0.42)) if total_quantity_kg > 0 else 0
        co2_diverted_kg = round(total_quantity_kg * 2.5, 2)

        donors_count = Organization.objects.filter(org_type=Organization.Type.BUSINESS).count()
        ngos_count = Organization.objects.filter(org_type=Organization.Type.NGO, is_verified=True).count()

        data = {
            "total_quantity_donated_kg": total_quantity_kg,
            "meals_provided": meals_provided,
            "co2_diverted_kg": co2_diverted_kg,
            "total_donors": donors_count,
            "total_ngos": ngos_count,
        }
        cache.set(cache_key, data, timeout=600)  # 10 minutes cache
        return Response(data)


class NotificationListView(APIView):
    """
    GET /api/v1/marketplace/notifications/
    Returns in-app notifications for the authenticated tenant organization.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_org = getattr(request.user, "organization", None)
        if not user_org:
            return Response({"results": [], "unread_count": 0})

        qs = Notification.objects.filter(organization=user_org)

        unread_only = request.query_params.get("unread_only", "").lower() in ("true", "1")
        if unread_only:
            qs = qs.filter(is_read=False)

        unread_count = Notification.objects.filter(organization=user_org, is_read=False).count()

        if "page" in request.query_params:
            paginator = PageNumberPagination()
            paginator.page_size = 20
            page = paginator.paginate_queryset(qs, request)
            serializer = NotificationSerializer(page, many=True)
            res = paginator.get_paginated_response(serializer.data)
            res.data["unread_count"] = unread_count
            return res

        serializer = NotificationSerializer(qs, many=True)
        return Response({
            "results": serializer.data,
            "unread_count": unread_count,
        })


class NotificationMarkReadView(APIView):
    """
    PATCH /api/v1/marketplace/notifications/<pk>/read/
    POST /api/v1/marketplace/notifications/<pk>/read/
    Marks a single notification as read.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _mark_read(self, request, pk):
        user_org = getattr(request.user, "organization", None)
        notif = get_object_or_404(Notification, pk=pk)

        # Cross-tenant isolation
        if not request.user.is_platform_admin and (not user_org or notif.organization_id != user_org.id):
            raise Http404("Notification not found.")

        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notif).data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        return self._mark_read(request, pk)

    def post(self, request, pk):
        return self._mark_read(request, pk)


class NotificationMarkAllReadView(APIView):
    """
    POST /api/v1/marketplace/notifications/mark-all-read/
    Marks all notifications for the authenticated organization as read.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user_org = getattr(request.user, "organization", None)
        if not user_org:
            return Response({"status": "success", "updated_count": 0})

        updated = Notification.objects.filter(organization=user_org, is_read=False).update(is_read=True)
        return Response({
            "status": "success",
            "updated_count": updated,
        }, status=status.HTTP_200_OK)




