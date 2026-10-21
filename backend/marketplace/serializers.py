"""
Serializers for the marketplace app:
SurplusListing, NGORequirement, DonationRequest, DonationStatusHistory,
Notification, Claim, and Rating.
"""
from datetime import timedelta
from decimal import Decimal
from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Organization
from .models import (
    Claim,
    DonationRequest,
    DonationStatusHistory,
    NGORequirement,
    Notification,
    Rating,
    SurplusListing,
)


def _require_verified_ngo(request):
    """
    Raises ValidationError if the caller is not a verified NGO.
    """
    user = getattr(request, "user", None)
    org = getattr(user, "organization", None) if user else None
    if not org or org.org_type != Organization.Type.NGO or not org.is_verified:
        raise serializers.ValidationError(
            "Only verified NGO users may perform this action."
        )
    return org


# ---------------------------------------------------------------------------
# SurplusListing
# ---------------------------------------------------------------------------

class SurplusListingSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source="donor.name", read_only=True)
    donor = serializers.PrimaryKeyRelatedField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    batch_code = serializers.CharField(source="batch.batch_code", read_only=True, default="")
    remaining_quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)

    # Legacy field aliases
    quantity = serializers.DecimalField(source="quantity_offered", max_digits=12, decimal_places=3, required=False)
    pickup_window_start = serializers.DateTimeField(source="available_from", required=False)
    pickup_window_end = serializers.DateTimeField(source="available_until", required=False)

    # Rating aggregates
    donor_rating_avg = serializers.SerializerMethodField()
    donor_rating_count = serializers.SerializerMethodField()
    rating_avg = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    donor_info = serializers.SerializerMethodField()

    class Meta:
        model = SurplusListing
        fields = [
            "id",
            "donor",
            "donor_name",
            "batch",
            "batch_code",
            "title",
            "description",
            "category",
            "category_name",
            "quantity_offered",
            "quantity_reserved",
            "remaining_quantity",
            "unit",
            "pickup_address",
            "latitude",
            "longitude",
            "available_from",
            "available_until",
            "is_cooked",
            "safe_until",
            "status",
            "created_at",
            "updated_at",
            # Legacy compatibility fields
            "quantity",
            "pickup_window_start",
            "pickup_window_end",
            "donor_rating_avg",
            "donor_rating_count",
            "rating_avg",
            "rating_count",
            "donor_info",
        ]
        read_only_fields = [
            "id",
            "donor",
            "quantity_reserved",
            "remaining_quantity",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        # Handle input aliases if provided
        if "quantity_offered" not in data and "quantity" in self.initial_data:
            data["quantity_offered"] = self.initial_data["quantity"]
        if "available_from" not in data and "pickup_window_start" in self.initial_data:
            data["available_from"] = self.initial_data["pickup_window_start"]
        if "available_until" not in data and "pickup_window_end" in self.initial_data:
            data["available_until"] = self.initial_data["pickup_window_end"]

        avail_from = data.get("available_from") or getattr(self.instance, "available_from", None)
        avail_until = data.get("available_until") or getattr(self.instance, "available_until", None)
        safe_until = data.get("safe_until") if "safe_until" in data else getattr(self.instance, "safe_until", None)

        if avail_from and avail_until and avail_until <= avail_from:
            raise serializers.ValidationError({"available_until": "available_until must be strictly after available_from."})

        if avail_until and safe_until and avail_until > safe_until:
            raise serializers.ValidationError({"available_until": "available_until may not exceed safe_until."})

        qty = data.get("quantity_offered") or getattr(self.instance, "quantity_offered", None)
        if qty is not None and qty <= 0:
            raise serializers.ValidationError({"quantity_offered": "quantity_offered must be greater than 0."})

        return data

    def get_donor_rating_avg(self, obj):
        val = getattr(obj, "donor_rating_avg", None)
        if val is not None:
            return round(float(val), 2)
        agg = Rating.objects.filter(
            business=obj.donor, is_hidden=False
        ).aggregate(avg=Avg("stars"))
        return round(float(agg["avg"]), 2) if agg["avg"] else None

    def get_donor_rating_count(self, obj):
        val = getattr(obj, "donor_rating_count", None)
        if val is not None:
            return val
        return Rating.objects.filter(
            business=obj.donor, is_hidden=False
        ).count()

    def get_rating_avg(self, obj):
        return self.get_donor_rating_avg(obj)

    def get_rating_count(self, obj):
        return self.get_donor_rating_count(obj)

    def get_donor_info(self, obj):
        donor = getattr(obj, "donor", None)
        return {
            "id": donor.id if donor else None,
            "name": donor.name if donor else "",
            "rating_avg": self.get_donor_rating_avg(obj),
            "rating_count": self.get_donor_rating_count(obj),
        }


ListingSerializer = SurplusListingSerializer


# ---------------------------------------------------------------------------
# NGORequirement
# ---------------------------------------------------------------------------

class NGORequirementSerializer(serializers.ModelSerializer):
    ngo_name = serializers.CharField(source="ngo.name", read_only=True)
    ngo = serializers.PrimaryKeyRelatedField(read_only=True)
    category_names = serializers.SerializerMethodField()

    class Meta:
        model = NGORequirement
        fields = [
            "id",
            "ngo",
            "ngo_name",
            "title",
            "categories",
            "category_names",
            "min_quantity",
            "max_quantity",
            "unit",
            "radius_km",
            "frequency",
            "needed_by",
            "dietary_notes",
            "accepts_cooked_food",
            "preferred_pickup_start",
            "preferred_pickup_end",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "ngo", "created_at", "updated_at"]

    def get_category_names(self, obj):
        return [c.name for c in obj.categories.all()]

    def validate(self, data):
        min_qty = data.get("min_quantity", getattr(self.instance, "min_quantity", Decimal("0.000")))
        max_qty = data.get("max_quantity", getattr(self.instance, "max_quantity", None))
        radius = data.get("radius_km", getattr(self.instance, "radius_km", Decimal("15.00")))

        if min_qty is not None and min_qty < 0:
            raise serializers.ValidationError({"min_quantity": "min_quantity must be non-negative."})
        if max_qty is not None and max_qty <= 0:
            raise serializers.ValidationError({"max_quantity": "max_quantity must be greater than zero."})
        if max_qty is not None and min_qty is not None and max_qty < min_qty:
            raise serializers.ValidationError({"max_quantity": "max_quantity must be greater than or equal to min_quantity."})
        if radius is not None and radius <= 0:
            raise serializers.ValidationError({"radius_km": "radius_km must be greater than zero."})

        return data


# ---------------------------------------------------------------------------
# DonationStatusHistory
# ---------------------------------------------------------------------------

class DonationStatusHistorySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.username", read_only=True, default="")

    class Meta:
        model = DonationStatusHistory
        fields = [
            "id",
            "request",
            "from_status",
            "to_status",
            "actor",
            "actor_name",
            "note",
            "created_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# DonationRequest
# ---------------------------------------------------------------------------

class DonationRequestSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)
    ngo = serializers.PrimaryKeyRelatedField(read_only=True)
    ngo_name = serializers.CharField(source="ngo.name", read_only=True)
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    donor_name = serializers.CharField(source="listing.donor.name", read_only=True)
    donor_id = serializers.IntegerField(source="listing.donor_id", read_only=True)
    unit = serializers.CharField(source="listing.unit", read_only=True)
    status_history = DonationStatusHistorySerializer(many=True, read_only=True)
    has_rating = serializers.SerializerMethodField()

    class Meta:
        model = DonationRequest
        fields = [
            "id",
            "code",
            "listing",
            "listing_title",
            "donor_id",
            "donor_name",
            "ngo",
            "ngo_name",
            "quantity_requested",
            "quantity_approved",
            "quantity_collected",
            "unit",
            "status",
            "proposed_pickup_start",
            "proposed_pickup_end",
            "confirmed_pickup_start",
            "confirmed_pickup_end",
            "note",
            "rejection_reason",
            "contact_name",
            "contact_phone",
            "requested_at",
            "approved_at",
            "scheduled_at",
            "in_transit_at",
            "collected_at",
            "completed_at",
            "rejected_at",
            "cancelled_at",
            "no_show_at",
            "expired_at",
            "updated_at",
            "status_history",
            "has_rating",
        ]
        read_only_fields = [
            "id",
            "code",
            "ngo",
            "status",
            "quantity_approved",
            "quantity_collected",
            "confirmed_pickup_start",
            "confirmed_pickup_end",
            "rejection_reason",
            "requested_at",
            "approved_at",
            "scheduled_at",
            "in_transit_at",
            "collected_at",
            "completed_at",
            "rejected_at",
            "cancelled_at",
            "no_show_at",
            "expired_at",
            "updated_at",
        ]

    def get_has_rating(self, obj):
        return hasattr(obj, "rating")

    def validate(self, data):
        prop_start = data.get("proposed_pickup_start")
        prop_end = data.get("proposed_pickup_end")
        if prop_start and prop_end and prop_end <= prop_start:
            raise serializers.ValidationError({"proposed_pickup_end": "proposed_pickup_end must be after proposed_pickup_start."})
        qty = data.get("quantity_requested")
        if qty is not None and qty <= 0:
            raise serializers.ValidationError({"quantity_requested": "quantity_requested must be greater than zero."})
        return data


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "organization",
            "user",
            "type",
            "title",
            "body",
            "link",
            "is_read",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "user",
            "type",
            "title",
            "body",
            "link",
            "created_at",
        ]


# ---------------------------------------------------------------------------
# Claim (Legacy)
# ---------------------------------------------------------------------------

class ClaimSerializer(serializers.ModelSerializer):
    ngo_name = serializers.CharField(source="ngo.name", read_only=True)
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    donor_name = serializers.CharField(source="listing.donor.name", read_only=True)
    has_rating = serializers.SerializerMethodField()

    class Meta:
        model = Claim
        fields = [
            "id",
            "listing",
            "listing_title",
            "ngo",
            "ngo_name",
            "donor_name",
            "status",
            "pickup_eta",
            "notes",
            "has_rating",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "ngo", "created_at", "updated_at"]

    def get_has_rating(self, obj):
        return hasattr(obj, "rating")


# ---------------------------------------------------------------------------
# Rating – create
# ---------------------------------------------------------------------------

class RatingCreateSerializer(serializers.Serializer):
    stars = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )

    def validate(self, data):
        request = self.context["request"]
        claim = self.context.get("claim")
        req = self.context.get("donation_request")

        _require_verified_ngo(request)
        user_org = request.user.organization

        if claim:
            if claim.ngo_id != user_org.id:
                raise serializers.ValidationError({"detail": "Not found."})
            if claim.status != Claim.Status.PICKED_UP:
                raise serializers.ValidationError("You can only rate a claim that has been picked up.")
            if hasattr(claim, "rating"):
                raise serializers.ValidationError("A rating already exists for this claim.")
        elif req:
            if req.ngo_id != user_org.id:
                raise serializers.ValidationError({"detail": "Not found."})
            if req.status not in (DonationRequest.Status.COLLECTED, DonationRequest.Status.COMPLETED):
                raise serializers.ValidationError("You can only rate a request that has been collected.")
            if hasattr(req, "rating"):
                raise serializers.ValidationError("A rating already exists for this request.")
        else:
            raise serializers.ValidationError("Target claim or request must be provided.")

        return data

    def create(self, validated_data):
        claim = self.context.get("claim")
        req = self.context.get("donation_request")
        if req:
            return Rating.objects.create(
                request=req,
                ngo=req.ngo,
                business=req.listing.donor,
                stars=validated_data["stars"],
                comment=validated_data.get("comment", ""),
            )
        return Rating.objects.create(
            claim=claim,
            ngo=claim.ngo,
            business=claim.listing.donor,
            stars=validated_data["stars"],
            comment=validated_data.get("comment", ""),
        )


class RatingPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ["stars", "comment"]

    def validate_stars(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Stars must be between 1 and 5.")
        return value

    def validate(self, data):
        instance: Rating = self.instance
        if instance and not instance.is_editable():
            raise serializers.ValidationError(
                "This rating is locked; the 7-day edit window has passed."
            )
        return data


class RatingReadSerializer(serializers.ModelSerializer):
    ngo_name = serializers.CharField(source="ngo.name", read_only=True)
    business_name = serializers.CharField(source="business.name", read_only=True)
    is_editable = serializers.SerializerMethodField()
    edit_deadline = serializers.SerializerMethodField()

    class Meta:
        model = Rating
        fields = [
            "id",
            "claim",
            "request",
            "ngo",
            "ngo_name",
            "business",
            "business_name",
            "stars",
            "comment",
            "is_hidden",
            "is_editable",
            "edit_deadline",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_is_editable(self, obj):
        return obj.is_editable()

    def get_edit_deadline(self, obj):
        return (obj.created_at + timedelta(days=7)).isoformat()


class PendingRatingSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source="listing.donor.name", read_only=True)
    donor_id = serializers.IntegerField(source="listing.donor_id", read_only=True)
    item = serializers.CharField(source="listing.title", read_only=True)
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    claim_id = serializers.IntegerField(source="id", read_only=True)
    quantity = serializers.DecimalField(
        source="listing.quantity", max_digits=12, decimal_places=3, read_only=True
    )
    pickup_date = serializers.DateTimeField(source="pickup_eta", read_only=True)
    pickup_eta = serializers.DateTimeField(read_only=True)
    donor_rating_avg = serializers.SerializerMethodField()
    donor_rating_count = serializers.SerializerMethodField()

    class Meta:
        model = Claim
        fields = [
            "id",
            "claim_id",
            "donor_id",
            "donor_name",
            "donor_rating_avg",
            "donor_rating_count",
            "item",
            "listing_title",
            "quantity",
            "pickup_date",
            "pickup_eta",
            "updated_at",
        ]

    def get_donor_rating_avg(self, obj):
        agg = Rating.objects.filter(
            business_id=obj.listing.donor_id, is_hidden=False
        ).aggregate(avg=Avg("stars"))
        return round(float(agg["avg"]), 2) if agg["avg"] else None

    def get_donor_rating_count(self, obj):
        return Rating.objects.filter(
            business_id=obj.listing.donor_id, is_hidden=False
        ).count()


class BusinessRatingSummarySerializer(serializers.Serializer):
    business_id = serializers.IntegerField()
    business_name = serializers.CharField()
    rating_avg = serializers.FloatField(allow_null=True)
    rating_count = serializers.IntegerField()
    breakdown = serializers.DictField(child=serializers.IntegerField())
    recent_reviews = RatingReadSerializer(many=True)


# ---------------------------------------------------------------------------
# Matching Engine Serializers (Task 3)
# ---------------------------------------------------------------------------

class MatchBreakdownSerializer(serializers.Serializer):
    distance_score = serializers.FloatField()
    urgency_score = serializers.FloatField()
    quantity_score = serializers.FloatField()
    reliability_score = serializers.FloatField()
    fairness_score = serializers.FloatField()


class ListingRequirementMatchSerializer(serializers.Serializer):
    requirement_id = serializers.IntegerField()
    requirement_title = serializers.CharField()
    ngo_id = serializers.IntegerField()
    ngo_name = serializers.CharField()
    ngo_address = serializers.CharField(allow_blank=True)
    ngo_phone = serializers.CharField(allow_blank=True)
    min_quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    max_quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    unit = serializers.CharField()
    radius_km = serializers.DecimalField(max_digits=6, decimal_places=2)
    accepts_cooked_food = serializers.BooleanField()
    distance_km = serializers.FloatField()
    is_compatible = serializers.BooleanField()
    incompatibility_reasons = serializers.ListField(child=serializers.CharField())
    score = serializers.FloatField()
    breakdown = MatchBreakdownSerializer()


class RequirementListingMatchSerializer(serializers.Serializer):
    listing_id = serializers.IntegerField()
    listing_title = serializers.CharField()
    donor_id = serializers.IntegerField()
    donor_name = serializers.CharField()
    pickup_address = serializers.CharField(allow_blank=True)
    category_id = serializers.IntegerField(allow_null=True)
    category_name = serializers.CharField(allow_null=True)
    remaining_quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    quantity_offered = serializers.DecimalField(max_digits=12, decimal_places=3)
    quantity_reserved = serializers.DecimalField(max_digits=12, decimal_places=3)
    unit = serializers.CharField()
    is_cooked = serializers.BooleanField()
    available_from = serializers.DateTimeField()
    available_until = serializers.DateTimeField()
    safe_until = serializers.DateTimeField(allow_null=True)
    distance_km = serializers.FloatField()
    is_compatible = serializers.BooleanField()
    incompatibility_reasons = serializers.ListField(child=serializers.CharField())
    score = serializers.FloatField()
    breakdown = MatchBreakdownSerializer()


# ---------------------------------------------------------------------------
# Pickup Schedule & Impact Analytics Serializers (Task 4)
# ---------------------------------------------------------------------------

class PickupScheduleItemSerializer(serializers.Serializer):
    request_id = serializers.IntegerField()
    request_code = serializers.CharField()
    status = serializers.CharField()
    listing_id = serializers.IntegerField()
    item_title = serializers.CharField()
    category_name = serializers.CharField(allow_null=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    unit = serializers.CharField()
    pickup_window_start = serializers.DateTimeField()
    pickup_window_end = serializers.DateTimeField()
    donor_id = serializers.IntegerField()
    donor_name = serializers.CharField()
    donor_address = serializers.CharField(allow_blank=True)
    donor_phone = serializers.CharField(allow_blank=True)
    ngo_id = serializers.IntegerField()
    ngo_name = serializers.CharField()
    contact_name = serializers.CharField(allow_blank=True)
    contact_phone = serializers.CharField(allow_blank=True)
    note = serializers.CharField(allow_blank=True)
    is_overdue = serializers.BooleanField()
    is_today = serializers.BooleanField()
    time_until_pickup_minutes = serializers.IntegerField(allow_null=True)


class ImpactCategoryBreakdownSerializer(serializers.Serializer):
    category_name = serializers.CharField()
    quantity_kg = serializers.FloatField()
    percentage = serializers.FloatField()


class ImpactMonthlyTrendSerializer(serializers.Serializer):
    month = serializers.CharField()
    quantity_kg = serializers.FloatField()
    meals = serializers.IntegerField()
    donations_count = serializers.IntegerField()


class ImpactAnalyticsSerializer(serializers.Serializer):
    total_donations_completed = serializers.IntegerField()
    total_quantity_donated_kg = serializers.FloatField()
    meals_provided = serializers.IntegerField()
    co2_diverted_kg = serializers.FloatField()
    water_saved_liters = serializers.IntegerField()
    financial_value_saved = serializers.FloatField()
    category_breakdown = ImpactCategoryBreakdownSerializer(many=True)
    monthly_trend = ImpactMonthlyTrendSerializer(many=True)


