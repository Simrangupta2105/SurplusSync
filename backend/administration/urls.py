from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AdminPingView,
    AdminAuditLogViewSet,
    AdminOrganizationViewSet,
    AdminIssueViewSet,
    AdminRatingViewSet,
    AdminBusinessRatingSummaryView,
    AdminStatsView,
)

router = DefaultRouter()
router.register(r"audit-logs", AdminAuditLogViewSet, basename="admin-audit-logs")
router.register(r"organizations", AdminOrganizationViewSet, basename="admin-organizations")
router.register(r"issues", AdminIssueViewSet, basename="admin-issues")
router.register(r"ratings", AdminRatingViewSet, basename="admin-ratings")

urlpatterns = [
    path("ping/", AdminPingView.as_view(), name="admin-ping"),
    path("stats/", AdminStatsView.as_view(), name="admin-stats"),
    path(
        "businesses/<int:business_id>/rating-summary/",
        AdminBusinessRatingSummaryView.as_view(),
        name="admin-business-rating-summary",
    ),
    path("", include(router.urls)),
]
