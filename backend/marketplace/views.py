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
from django.db import IntegrityError
from django.db.models import Avg, Count, FloatField, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Organization
from .models import Claim, Listing, Rating
from .serializers import (
    ClaimSerializer,
    ListingSerializer,
    PendingRatingSerializer,
    RatingReadSerializer,
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
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = get_annotated_listings_queryset().order_by("-created_at")
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

