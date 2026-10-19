from decimal import Decimal
from django.db.models import Avg, Count, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce, TruncWeek
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Organization, User
from inventory.models import Batch, StockTransaction
from marketplace.models import Claim, Listing, Rating
from .models import AdminAuditLog, Issue, log_admin_action
from .notifications import notify_organization_decision, notify_issue_status_change
from .permissions import IsPlatformAdmin
from .serializers import (
    AdminAuditLogSerializer,
    AdminOrganizationDetailSerializer,
    AdminOrganizationListSerializer,
    IssueCreateSerializer,
    IssueReadSerializer,
    AdminIssueSerializer,
    AdminRatingSerializer,
)


def get_admin_organizations_queryset():
    """
    Returns Organization QuerySet with subquery-annotated counts
    for users, batches, claims, and listings to avoid Cartesian join explosion.
    """
    users_sq = Coalesce(
        Subquery(
            User.objects.filter(organization=OuterRef("pk"))
            .values("organization")
            .annotate(cnt=Count("id"))
            .values("cnt")[:1],
            output_field=IntegerField(),
        ),
        0,
    )

    batches_sq = Coalesce(
        Subquery(
            Batch.objects.filter(organization=OuterRef("pk"))
            .values("organization")
            .annotate(cnt=Count("id"))
            .values("cnt")[:1],
            output_field=IntegerField(),
        ),
        0,
    )

    claims_sq = Coalesce(
        Subquery(
            Claim.objects.filter(ngo=OuterRef("pk"))
            .values("ngo")
            .annotate(cnt=Count("id"))
            .values("cnt")[:1],
            output_field=IntegerField(),
        ),
        0,
    )

    listings_sq = Coalesce(
        Subquery(
            Listing.objects.filter(donor=OuterRef("pk"))
            .values("donor")
            .annotate(cnt=Count("id"))
            .values("cnt")[:1],
            output_field=IntegerField(),
        ),
        0,
    )

    return Organization.objects.annotate(
        users_count=users_sq,
        batches_count=batches_sq,
        claims_count=claims_sq,
        listings_count=listings_sq,
    )


class AdminPingView(APIView):
    """
    Diagnostic root verification endpoint for platform admin authentication.
    Requires authenticated platform administrator (is_staff=True, organization=None).
    """
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        return Response({
            "status": "active",
            "message": "SurplusSync Platform Administration API",
            "admin": request.user.username,
            "email": request.user.email,
            "is_platform_admin": True,
        })


class AdminAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for platform administrators to review the append-only audit trail.
    """
    queryset = AdminAuditLog.objects.select_related("admin_user").all().order_by("-created_at")
    serializer_class = AdminAuditLogSerializer
    permission_classes = [IsPlatformAdmin]
    pagination_class = PageNumberPagination
    filterset_fields = ["action", "target_type", "target_id"]
    search_fields = ["action", "target_type", "target_id", "admin_user__username"]


class AdminOrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Platform administrator viewset for reviewing and managing organizations.
    Endpoints:
    - GET /api/v1/admin/organizations/?org_type=&is_verified=&verification_status=&search=
    - GET /api/v1/admin/organizations/<id>/
    - POST /api/v1/admin/organizations/<id>/verify/
    - POST /api/v1/admin/organizations/<id>/reject/
    - POST /api/v1/admin/organizations/<id>/suspend/
    - POST /api/v1/admin/organizations/<id>/reinstate/
    """
    permission_classes = [IsPlatformAdmin]
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminOrganizationDetailSerializer
        return AdminOrganizationListSerializer

    def get_queryset(self):
        qs = get_admin_organizations_queryset()

        # Query parameter filters
        org_type = self.request.query_params.get("org_type")
        if org_type:
            qs = qs.filter(org_type__iexact=org_type)

        is_verified = self.request.query_params.get("is_verified")
        if is_verified is not None:
            if is_verified.lower() in ["true", "1"]:
                qs = qs.filter(is_verified=True)
            elif is_verified.lower() in ["false", "0"]:
                qs = qs.filter(is_verified=False)

        verification_status = self.request.query_params.get("verification_status")
        if verification_status:
            qs = qs.filter(verification_status__iexact=verification_status)

        search = self.request.query_params.get("search")
        if search:
            search = search.strip()
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(address__icontains=search)
                | Q(phone__icontains=search)
            )

        return qs.order_by("-created_at", "id")

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        org = self.get_object()
        prev_status = org.verification_status
        note = request.data.get("note") or request.data.get("verification_note", "")
        note = str(note).strip()

        org.verification_status = Organization.VerificationStatus.VERIFIED
        org.is_verified = True
        org.verified_at = timezone.now()
        if note:
            org.verification_note = note
        org.save()

        log_admin_action(
            admin_user=request.user,
            action="ORGANIZATION_VERIFY",
            target_type="Organization",
            target_id=str(org.id),
            details={
                "previous_status": prev_status,
                "new_status": Organization.VerificationStatus.VERIFIED,
                "note": note,
            },
        )
        notify_organization_decision(org, "VERIFIED", note)
        serializer = AdminOrganizationDetailSerializer(org)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        org = self.get_object()
        reason = request.data.get("reason") or request.data.get("note", "")
        reason = str(reason).strip()
        if not reason:
            return Response(
                {"reason": ["A reason is required to reject an organization."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prev_status = org.verification_status
        org.verification_status = Organization.VerificationStatus.REJECTED
        org.is_verified = False
        org.verification_note = reason
        org.save()

        log_admin_action(
            admin_user=request.user,
            action="ORGANIZATION_REJECT",
            target_type="Organization",
            target_id=str(org.id),
            details={
                "previous_status": prev_status,
                "new_status": Organization.VerificationStatus.REJECTED,
                "reason": reason,
            },
        )
        notify_organization_decision(org, "REJECTED", reason)
        serializer = AdminOrganizationDetailSerializer(org)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, pk=None):
        org = self.get_object()
        reason = request.data.get("reason") or request.data.get("note", "")
        reason = str(reason).strip()

        prev_status = org.verification_status
        org.verification_status = Organization.VerificationStatus.SUSPENDED
        org.is_verified = False
        if reason:
            org.verification_note = reason
        org.save()

        log_admin_action(
            admin_user=request.user,
            action="ORGANIZATION_SUSPEND",
            target_type="Organization",
            target_id=str(org.id),
            details={
                "previous_status": prev_status,
                "new_status": Organization.VerificationStatus.SUSPENDED,
                "reason": reason,
            },
        )
        notify_organization_decision(org, "SUSPENDED", reason)
        serializer = AdminOrganizationDetailSerializer(org)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reinstate")
    def reinstate(self, request, pk=None):
        org = self.get_object()
        reason = request.data.get("reason") or request.data.get("note", "")
        reason = str(reason).strip()

        prev_status = org.verification_status
        org.verification_status = Organization.VerificationStatus.VERIFIED
        org.is_verified = True
        org.verified_at = timezone.now()
        if reason:
            org.verification_note = reason
        org.save()

        log_admin_action(
            admin_user=request.user,
            action="ORGANIZATION_REINSTATE",
            target_type="Organization",
            target_id=str(org.id),
            details={
                "previous_status": prev_status,
                "new_status": Organization.VerificationStatus.VERIFIED,
                "reason": reason,
            },
        )
        notify_organization_decision(org, "REINSTATED", reason)
        serializer = AdminOrganizationDetailSerializer(org)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TenantIssueViewSet(viewsets.ModelViewSet):
    """
    Tenant endpoint for Business and NGO users to report issues and view their own issues.
    Endpoints:
    - POST /api/v1/issues/ (report an issue)
    - GET  /api/v1/issues/ (list own issues)
    - GET  /api/v1/issues/<id>/ (retrieve own issue)
    """
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        if self.action == "create":
            return IssueCreateSerializer
        return IssueReadSerializer

    def get_queryset(self):
        user = self.request.user
        org = getattr(user, "organization", None)
        if not org:
            return Issue.objects.none()
        return (
            Issue.objects.filter(reporter_org=org)
            .select_related("reporter", "reporter_org", "target_org", "claim", "claim__listing")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        user = self.request.user
        org = getattr(user, "organization", None)
        if not org:
            raise permissions.exceptions.PermissionDenied(
                "You must belong to an organization to report an issue."
            )
        serializer.save(
            reporter=user,
            reporter_org=org,
            status=Issue.Status.OPEN,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        read_serializer = IssueReadSerializer(serializer.instance)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


class AdminIssueViewSet(viewsets.ModelViewSet):
    """
    Platform administrator viewset for moderating, filtering, and updating reported issues.
    Endpoints:
    - GET   /api/v1/admin/issues/?status=&category=&priority=&search=
    - GET   /api/v1/admin/issues/<id>/
    - PATCH /api/v1/admin/issues/<id>/
    """
    permission_classes = [IsPlatformAdmin]
    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = AdminIssueSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        qs = Issue.objects.select_related(
            "reporter",
            "reporter_org",
            "target_org",
            "claim",
            "claim__listing",
            "assigned_to",
            "resolved_by",
        ).all()

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status__iexact=status_param)

        category_param = self.request.query_params.get("category")
        if category_param:
            qs = qs.filter(category__iexact=category_param)

        priority_param = self.request.query_params.get("priority")
        if priority_param:
            qs = qs.filter(priority__iexact=priority_param)

        search = self.request.query_params.get("search")
        if search:
            search = search.strip()
            qs = qs.filter(
                Q(description__icontains=search)
                | Q(reporter__username__icontains=search)
                | Q(reporter_org__name__icontains=search)
                | Q(target_org__name__icontains=search)
            )

        return qs.order_by("-created_at", "id")

    def perform_update(self, serializer):
        issue = self.get_object()
        prev_status = issue.status
        prev_priority = issue.priority

        new_status = serializer.validated_data.get("status", prev_status)
        extra_kwargs = {}
        if new_status in [Issue.Status.RESOLVED, Issue.Status.DISMISSED] and prev_status not in [Issue.Status.RESOLVED, Issue.Status.DISMISSED]:
            extra_kwargs["resolved_by"] = self.request.user
            extra_kwargs["resolved_at"] = timezone.now()

        updated_issue = serializer.save(**extra_kwargs)

        # Audit log
        log_admin_action(
            admin_user=self.request.user,
            action="ISSUE_UPDATE",
            target_type="Issue",
            target_id=str(updated_issue.id),
            details={
                "previous_status": prev_status,
                "new_status": updated_issue.status,
                "previous_priority": prev_priority,
                "new_priority": updated_issue.priority,
                "admin_notes": updated_issue.admin_notes,
                "assigned_to": updated_issue.assigned_to_id,
            },
        )

        # Notify reporter if status changed
        if prev_status != updated_issue.status:
            notify_issue_status_change(
                issue=updated_issue,
                previous_status=prev_status,
                new_status=updated_issue.status,
                note=updated_issue.admin_notes,
            )


class AdminRatingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Platform administrator viewset for moderating NGO-to-Business ratings.
    Endpoints:
    - GET  /api/v1/admin/ratings/?stars=&business=&ngo=&is_hidden=&search=
    - GET  /api/v1/admin/ratings/<id>/
    - POST /api/v1/admin/ratings/<id>/hide/
    - POST /api/v1/admin/ratings/<id>/unhide/
    """
    permission_classes = [IsPlatformAdmin]
    serializer_class = AdminRatingSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        qs = Rating.objects.select_related(
            "business",
            "ngo",
            "claim",
            "claim__listing",
        ).all()

        stars = self.request.query_params.get("stars")
        if stars:
            try:
                qs = qs.filter(stars=int(stars))
            except (ValueError, TypeError):
                pass

        business = self.request.query_params.get("business")
        if business:
            qs = qs.filter(business_id=business)

        ngo = self.request.query_params.get("ngo")
        if ngo:
            qs = qs.filter(ngo_id=ngo)

        is_hidden = self.request.query_params.get("is_hidden")
        if is_hidden is not None:
            if is_hidden.lower() in ["true", "1"]:
                qs = qs.filter(is_hidden=True)
            elif is_hidden.lower() in ["false", "0"]:
                qs = qs.filter(is_hidden=False)

        search = self.request.query_params.get("search")
        if search:
            search = search.strip()
            qs = qs.filter(
                Q(comment__icontains=search)
                | Q(ngo__name__icontains=search)
                | Q(business__name__icontains=search)
            )

        return qs.order_by("-created_at", "id")

    @action(detail=True, methods=["post"], url_path="hide")
    def hide(self, request, pk=None):
        rating = self.get_object()
        reason = request.data.get("reason", "")
        reason = str(reason).strip() if reason else ""
        if not reason:
            return Response(
                {"reason": ["A reason is required to hide a rating."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rating.is_hidden = True
        rating.hidden_reason = reason
        rating.save(update_fields=["is_hidden", "hidden_reason", "updated_at"])

        log_admin_action(
            admin_user=request.user,
            action="RATING_HIDE",
            target_type="Rating",
            target_id=str(rating.id),
            details={
                "reason": reason,
                "stars": rating.stars,
                "business_id": rating.business_id,
                "business_name": rating.business.name,
                "ngo_id": rating.ngo_id,
                "ngo_name": rating.ngo.name,
            },
        )
        serializer = self.get_serializer(rating)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="unhide")
    def unhide(self, request, pk=None):
        rating = self.get_object()
        reason = request.data.get("reason", "")
        reason = str(reason).strip() if reason else ""
        if not reason:
            return Response(
                {"reason": ["A reason is required to unhide a rating."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rating.is_hidden = False
        rating.hidden_reason = reason
        rating.save(update_fields=["is_hidden", "hidden_reason", "updated_at"])

        log_admin_action(
            admin_user=request.user,
            action="RATING_UNHIDE",
            target_type="Rating",
            target_id=str(rating.id),
            details={
                "reason": reason,
                "stars": rating.stars,
                "business_id": rating.business_id,
                "business_name": rating.business.name,
                "ngo_id": rating.ngo_id,
                "ngo_name": rating.ngo.name,
            },
        )
        serializer = self.get_serializer(rating)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminBusinessRatingSummaryView(APIView):
    """
    Platform administrator endpoint for viewing a business's rating moderation summary.
    Endpoint: GET /api/v1/admin/businesses/<business_id>/rating-summary/
    Requires platform administrator privileges.
    All aggregations computed directly in the database without Python loops.
    """
    permission_classes = [IsPlatformAdmin]

    def get(self, request, business_id):
        business = get_object_or_404(Organization, pk=business_id)
        ratings = Rating.objects.filter(business=business)

        stats = ratings.aggregate(
            total_count=Count("id"),
            hidden_count=Count("id", filter=Q(is_hidden=True)),
            active_count=Count("id", filter=Q(is_hidden=False)),
            rating_avg=Avg("stars", filter=Q(is_hidden=False)),
            star_1=Count("id", filter=Q(is_hidden=False, stars=1)),
            star_2=Count("id", filter=Q(is_hidden=False, stars=2)),
            star_3=Count("id", filter=Q(is_hidden=False, stars=3)),
            star_4=Count("id", filter=Q(is_hidden=False, stars=4)),
            star_5=Count("id", filter=Q(is_hidden=False, stars=5)),
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

        return Response({
            "business_id": business.id,
            "business_name": business.name,
            "rating_avg": round(float(stats["rating_avg"]), 2) if stats["rating_avg"] is not None else None,
            "rating_count": stats["active_count"],
            "total_count": stats["total_count"],
            "hidden_count": stats["hidden_count"],
            "breakdown": breakdown,
        }, status=status.HTTP_200_OK)


class AdminStatsView(APIView):
    """
    Platform administrator overview statistics endpoint.
    Endpoint: GET /api/v1/admin/stats/
    Requires platform administrator privileges.
    All metrics computed via database aggregation queries without Python loops.
    """
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        # 1. Organization aggregates
        org_stats = Organization.objects.aggregate(
            total_businesses=Count("id", filter=Q(org_type=Organization.Type.BUSINESS)),
            total_ngos=Count("id", filter=Q(org_type=Organization.Type.NGO)),
            pending_verifications=Count(
                "id",
                filter=Q(
                    org_type=Organization.Type.NGO,
                    verification_status=Organization.VerificationStatus.PENDING,
                ),
            ),
        )

        # 2. Issues aggregates
        issue_stats = Issue.objects.aggregate(
            open_issues=Count("id", filter=Q(status=Issue.Status.OPEN)),
            in_review_issues=Count("id", filter=Q(status=Issue.Status.IN_REVIEW)),
            total_issues=Count("id"),
        )

        # 3. Marketplace listings aggregates
        listing_stats = Listing.objects.aggregate(
            active_listings=Count("id", filter=Q(status=Listing.Status.OPEN)),
            completed_kg=Sum("quantity", filter=Q(status=Listing.Status.COMPLETED)),
        )

        # 4. Inventory donations aggregate
        txn_stats = StockTransaction.objects.filter(
            txn_type=StockTransaction.Type.DONATED
        ).aggregate(
            donated_kg=Sum("quantity"),
        )

        total_kg_donated = (txn_stats["donated_kg"] or Decimal("0")) + (
            listing_stats["completed_kg"] or Decimal("0")
        )

        # 5. Platform rating aggregate (excluding hidden ratings)
        rating_stats = Rating.objects.filter(is_hidden=False).aggregate(
            avg=Avg("stars"),
            count=Count("id"),
        )
        avg_rating = (
            round(float(rating_stats["avg"]), 2)
            if rating_stats["avg"] is not None
            else None
        )

        # 6. New signups per week (chart series)
        signups_qs = (
            User.objects.annotate(week=TruncWeek("date_joined"))
            .values("week")
            .annotate(
                total=Count("id"),
                businesses=Count(
                    "id", filter=Q(organization__org_type=Organization.Type.BUSINESS)
                ),
                ngos=Count("id", filter=Q(organization__org_type=Organization.Type.NGO)),
            )
            .order_by("week")
        )

        signups_per_week = [
            {
                "week": entry["week"].strftime("%Y-%m-%d") if entry["week"] else "",
                "label": entry["week"].strftime("Week of %b %d") if entry["week"] else "",
                "total": entry["total"],
                "count": entry["total"],
                "signups": entry["total"],
                "businesses": entry["businesses"],
                "ngos": entry["ngos"],
            }
            for entry in signups_qs
        ]

        # 7. Quick queue helpers for Overview UI (recent pending NGOs & open issues)
        needs_approval = list(
            Organization.objects.filter(
                org_type=Organization.Type.NGO,
                verification_status=Organization.VerificationStatus.PENDING,
            )
            .order_by("-created_at")[:5]
            .values("id", "name", "phone", "address", "created_at")
        )

        recent_open_issues = list(
            Issue.objects.filter(status=Issue.Status.OPEN)
            .select_related("reporter_org")
            .order_by("-created_at")[:5]
            .values(
                "id",
                "category",
                "priority",
                "description",
                "reporter_org__name",
                "created_at",
            )
        )

        data = {
            "total_businesses": org_stats["total_businesses"],
            "total_ngos": org_stats["total_ngos"],
            "pending_verifications": org_stats["pending_verifications"],
            "pending_ngo_verifications": org_stats["pending_verifications"],
            "open_issues": issue_stats["open_issues"],
            "total_kg_donated": round(float(total_kg_donated), 2),
            "active_listings": listing_stats["active_listings"],
            "average_platform_rating": avg_rating,
            "average_rating": avg_rating,
            "total_ratings": rating_stats["count"],
            "signups_per_week": signups_per_week,
            "needs_approval_queue": needs_approval,
            "open_issues_queue": recent_open_issues,
        }

        return Response(data, status=status.HTTP_200_OK)



