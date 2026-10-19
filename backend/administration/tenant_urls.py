from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantIssueViewSet

router = DefaultRouter()
router.register(r"", TenantIssueViewSet, basename="tenant-issues")

urlpatterns = [
    path("", include(router.urls)),
]
