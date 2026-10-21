from django.contrib import admin
from .models import (
    Claim,
    DonationRequest,
    DonationStatusHistory,
    NGORequirement,
    Notification,
    Rating,
    SurplusListing,
)


@admin.register(SurplusListing)
class SurplusListingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "donor",
        "category",
        "quantity_offered",
        "quantity_reserved",
        "unit",
        "status",
        "available_from",
        "available_until",
        "created_at",
    )
    list_filter = ("status", "donor", "category", "is_cooked")
    search_fields = ("title", "donor__name", "description")
    ordering = ("-created_at",)


@admin.register(NGORequirement)
class NGORequirementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "ngo",
        "min_quantity",
        "max_quantity",
        "unit",
        "radius_km",
        "frequency",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "frequency", "accepts_cooked_food", "ngo")
    search_fields = ("title", "ngo__name", "dietary_notes")
    ordering = ("-created_at",)


class DonationStatusHistoryInline(admin.TabularInline):
    model = DonationStatusHistory
    extra = 0
    readonly_fields = ("from_status", "to_status", "actor", "note", "created_at")
    can_delete = False


@admin.register(DonationRequest)
class DonationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "listing",
        "ngo",
        "quantity_requested",
        "quantity_approved",
        "quantity_collected",
        "status",
        "proposed_pickup_start",
        "confirmed_pickup_start",
        "requested_at",
    )
    list_filter = ("status", "ngo")
    search_fields = ("code", "ngo__name", "listing__title", "contact_name", "contact_phone")
    ordering = ("-requested_at",)
    inlines = [DonationStatusHistoryInline]


@admin.register(DonationStatusHistory)
class DonationStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "request", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status",)
    search_fields = ("request__code", "actor__username", "note")
    ordering = ("-created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "type", "title", "is_read", "created_at")
    list_filter = ("type", "is_read", "organization")
    search_fields = ("title", "body", "organization__name")
    ordering = ("-created_at",)


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "ngo", "status", "pickup_eta", "created_at")
    list_filter = ("status", "ngo")
    search_fields = ("ngo__name", "listing__title")
    ordering = ("-created_at",)


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("id", "stars", "ngo", "business", "claim", "request", "is_hidden", "created_at")
    list_filter = ("stars", "is_hidden", "business")
    search_fields = ("ngo__name", "business__name", "comment")
    ordering = ("-created_at",)
    readonly_fields = ("ngo", "business", "claim", "request", "created_at", "updated_at")
    actions = ["hide_ratings", "unhide_ratings"]

    @admin.action(description="Hide selected ratings (moderation)")
    def hide_ratings(self, request, queryset):
        updated = queryset.update(is_hidden=True)
        self.message_user(request, f"Hidden {updated} rating(s).")

    @admin.action(description="Unhide selected ratings")
    def unhide_ratings(self, request, queryset):
        updated = queryset.update(is_hidden=False)
        self.message_user(request, f"Unhidden {updated} rating(s).")
