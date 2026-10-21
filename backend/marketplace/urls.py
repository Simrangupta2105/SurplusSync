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
    DonationRequestApproveView,
    DonationRequestCancelView,
    DonationRequestCollectView,
    DonationRequestConfirmReceiptView,
    DonationRequestConfirmScheduleView,
    DonationRequestDetailView,
    DonationRequestInTransitView,
    DonationRequestListView,
    DonationRequestNoShowView,
    DonationRequestRejectView,
    FeedListView,
    ImpactAnalyticsView,
    ListingDetailView,
    PublicImpactAnalyticsView,
    ListingListView,
    ListingMatchesView,
    ListingNotifyMatchesView,
    MyRatingsView,
    NGORequirementDetailView,
    NGORequirementListCreateView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    PendingRatingsView,
    PickupScheduleView,
    RateClaimView,
    RatingDetailView,
    RequirementMatchesView,
)

urlpatterns = [
    # Ratings & Reviews
    re_path(r"^ratings/pending/?$", PendingRatingsView.as_view(), name="ratings-pending"),
    re_path(r"^claims/(?P<claim_id>\d+)/rate/?$", RateClaimView.as_view(), name="claim-rate"),
    re_path(r"^ratings/(?P<pk>\d+)/?$", RatingDetailView.as_view(), name="rating-detail"),
    re_path(r"^ratings/mine/?$", MyRatingsView.as_view(), name="ratings-mine"),
    re_path(r"^businesses/(?P<business_id>\d+)/ratings/?$", BusinessRatingsView.as_view(), name="business-ratings"),

    # Listings, Feed & Claims
    re_path(r"^listings/(?P<listing_id>\d+)/matches/?$", ListingMatchesView.as_view(), name="listing-matches"),
    re_path(r"^listings/(?P<listing_id>\d+)/notify-matches/?$", ListingNotifyMatchesView.as_view(), name="listing-notify-matches"),
    re_path(r"^listings/(?P<pk>\d+)/?$", ListingDetailView.as_view(), name="listing-detail"),
    re_path(r"^listings/?$", ListingListView.as_view(), name="listing-list"),
    re_path(r"^feed/?$", FeedListView.as_view(), name="feed-list"),
    re_path(r"^claims/?$", ClaimListView.as_view(), name="claim-list"),

    # NGO Requirements & Matches (Task 3)
    re_path(r"^requirements/(?P<pk>\d+)/matches/?$", RequirementMatchesView.as_view(), name="requirement-matches"),
    re_path(r"^requirements/(?P<pk>\d+)/?$", NGORequirementDetailView.as_view(), name="requirement-detail"),
    re_path(r"^requirements/?$", NGORequirementListCreateView.as_view(), name="requirement-list"),

    # Pickup Schedule (Task 4)
    re_path(r"^schedule/?$", PickupScheduleView.as_view(), name="pickup-schedule"),

    # Impact Analytics (Task 4)
    re_path(r"^impact/public/?$", PublicImpactAnalyticsView.as_view(), name="impact-public"),
    re_path(r"^impact/?$", ImpactAnalyticsView.as_view(), name="impact-analytics"),
    re_path(r"^analytics/impact/?$", ImpactAnalyticsView.as_view(), name="analytics-impact"),

    # Notifications (Task 4)
    re_path(r"^notifications/mark-all-read/?$", NotificationMarkAllReadView.as_view(), name="notification-mark-all-read"),
    re_path(r"^notifications/(?P<pk>\d+)/read/?$", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    re_path(r"^notifications/?$", NotificationListView.as_view(), name="notification-list"),

    # Donation Request Lifecycle (Task 2)
    re_path(r"^requests/?$", DonationRequestListView.as_view(), name="request-list"),
    re_path(r"^requests/(?P<code_or_id>[^/]+)/approve/?$", DonationRequestApproveView.as_view(), name="request-approve"),
    re_path(r"^requests/(?P<code_or_id>[^/]+)/confirm-schedule/?$", DonationRequestConfirmScheduleView.as_view(), name="request-confirm-schedule"),
    re_path(r"^requests/(?P<code_or_id>[^/]+)/reject/?$", DonationRequestRejectView.as_view(), name="request-reject"),
    re_path(r"^requests/(?P<code_or_id>[^/]+)/cancel/?$", DonationRequestCancelView.as_view(), name="request-cancel"),
    re_path(r"^requests/(?P<code_or_id>[^/]+)/in-transit/?$", DonationRequestInTransitView.as_view(), name="request-in-transit"),
    re_path(r"^requests/(?P<code_or_id>[^/]+)/collect/?$", DonationRequestCollectView.as_view(), name="request-collect"),
    re_path(r"^requests/(?P<code_or_id>[^/]+)/confirm-receipt/?$", DonationRequestConfirmReceiptView.as_view(), name="request-confirm-receipt"),
    re_path(r"^requests/(?P<code_or_id>[^/]+)/no-show/?$", DonationRequestNoShowView.as_view(), name="request-no-show"),
    re_path(r"^requests/(?P<code_or_id>[^/]+)/?$", DonationRequestDetailView.as_view(), name="request-detail"),
]


