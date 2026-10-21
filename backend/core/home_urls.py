"""
URL routing for Home API endpoints (Task B1).
- GET /api/v1/home/
- GET /api/v1/home/public/
"""
from django.urls import path, re_path
from .home_views import AuthenticatedHomeView, PublicHomeView

urlpatterns = [
    re_path(r"^public/?$", PublicHomeView.as_view(), name="home-public"),
    re_path(r"^$", AuthenticatedHomeView.as_view(), name="home-authenticated"),
]
