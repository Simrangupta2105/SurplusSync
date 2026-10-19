from django.contrib import admin
from .models import Listing, Claim, Rating


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "donor", "status", "pickup_window_start", "pickup_window_end", "created_at")
    list_filter = ("status", "donor")
    search_fields = ("title", "donor__name")
    ordering = ("-created_at",)


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "ngo", "status", "pickup_eta", "created_at")
    list_filter = ("status", "ngo")
    search_fields = ("ngo__name", "listing__title")
    ordering = ("-created_at",)


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("id", "stars", "ngo", "business", "claim", "is_hidden", "created_at")
    list_filter = ("stars", "is_hidden", "business")
    search_fields = ("ngo__name", "business__name", "comment")
    ordering = ("-created_at",)
    readonly_fields = ("ngo", "business", "claim", "created_at", "updated_at")
    actions = ["hide_ratings", "unhide_ratings"]

    @admin.action(description="Hide selected ratings (moderation)")
    def hide_ratings(self, request, queryset):
        updated = queryset.update(is_hidden=True)
        self.message_user(request, f"Hidden {updated} rating(s).")

    @admin.action(description="Unhide selected ratings")
    def unhide_ratings(self, request, queryset):
        updated = queryset.update(is_hidden=False)
        self.message_user(request, f"Unhidden {updated} rating(s).")
