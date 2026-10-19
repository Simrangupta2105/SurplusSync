"""
URL configuration for the marketplace app.

All routes are mounted at /api/v1/marketplace/
Endpoints:
- GET  ratings/pending/                  -> PendingRatingsView
- POST claims/<id>/rate/                 -> RateClaimView
- GET  ratings/<id>/                     -> RatingDetailView
- PATCH ratings/<id>/                    -> RatingDetailView
- GET  ratings/mine/                     -> MyRatingsView
- GET  businesses/<id>/ratings/          -> BusinessRatingsView
- GET  listings/                         -> ListingListView
- GET  feed/                             -> FeedListView
- GET  claims/                           -> ClaimListView
"""
from django.urls import re_path
from .views import (
    BusinessRatingsView,
    ClaimListView,
    FeedListView,
    ListingListView,
    MyRatingsView,
    PendingRatingsView,
    RateClaimView,
    RatingDetailView,
)

urlpatterns = [
    re_path(r"^ratings/pending/?$", PendingRatingsView.as_view(), name="ratings-pending"),
    re_path(r"^claims/(?P<claim_id>\d+)/rate/?$", RateClaimView.as_view(), name="claim-rate"),
    re_path(r"^ratings/(?P<pk>\d+)/?$", RatingDetailView.as_view(), name="rating-detail"),
    re_path(r"^ratings/mine/?$", MyRatingsView.as_view(), name="ratings-mine"),
    re_path(r"^businesses/(?P<business_id>\d+)/ratings/?$", BusinessRatingsView.as_view(), name="business-ratings"),
    re_path(r"^listings/?$", ListingListView.as_view(), name="listing-list"),
    re_path(r"^feed/?$", FeedListView.as_view(), name="feed-list"),
    re_path(r"^claims/?$", ClaimListView.as_view(), name="claim-list"),
]
