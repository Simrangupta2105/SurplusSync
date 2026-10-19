"""
Serializers for the marketplace app.

Security notes
--------------
* ngo and business on Rating are always sourced from the linked Claim inside
  Rating.save(); any client-supplied values are silently ignored.
* The claim's NGO ownership check (rater == claim.ngo) is enforced here.
* Stars 1-5 is validated here AND enforced by a DB CheckConstraint.
* The 7-day edit lock is enforced in the PATCH view; is_editable() is the
  canonical source of truth.
"""
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Organization
from .models import Claim, Listing, Rating


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_verified_ngo(request):
    """
    Raises ValidationError (403-worthy) if the caller is not a verified NGO.
    Used in serializer-level validation.
    """
    user = getattr(request, "user", None)
    org = getattr(user, "organization", None) if user else None
    if not org or org.org_type != Organization.Type.NGO or not org.is_verified:
        raise serializers.ValidationError(
            "Only verified NGO users may perform this action."
        )
    return org


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

class ListingSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source="donor.name", read_only=True)
    donor = serializers.PrimaryKeyRelatedField(read_only=True)
    # Rating aggregates – annotated on the queryset by the view
    donor_rating_avg = serializers.SerializerMethodField()
    donor_rating_count = serializers.SerializerMethodField()
    rating_avg = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    donor_info = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id",
            "donor",
            "donor_name",
            "donor_rating_avg",
            "donor_rating_count",
            "rating_avg",
            "rating_count",
            "donor_info",
            "batch",
            "quantity",
            "title",
            "pickup_window_start",
            "pickup_window_end",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "donor", "created_at", "updated_at"]

    def get_donor_rating_avg(self, obj):
        # Prefer annotated value (no extra query) or compute on the fly.
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


# ---------------------------------------------------------------------------
# Claim
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
    """
    Accepted body for POST /claims/<id>/rate/.
    Only stars and comment come from the client; ngo and business are
    always populated from the claim inside Rating.save().
    """
    stars = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )

    def validate(self, data):
        request = self.context["request"]
        claim: Claim = self.context["claim"]

        # Must be a verified NGO.
        _require_verified_ngo(request)

        # Claim must belong to this NGO (404, not 403).
        user_org = request.user.organization
        if claim.ngo_id != user_org.id:
            raise serializers.ValidationError(
                {"detail": "Not found."},
            )

        # Claim must be PICKED_UP.
        if claim.status != Claim.Status.PICKED_UP:
            raise serializers.ValidationError(
                "You can only rate a claim that has been picked up."
            )

        # One rating per claim (guard before DB constraint fires).
        if hasattr(claim, "rating"):
            raise serializers.ValidationError(
                "A rating already exists for this claim."
            )

        return data

    def create(self, validated_data):
        claim: Claim = self.context["claim"]
        return Rating.objects.create(
            claim=claim,
            # ngo and business are overwritten in Rating.save() from the claim;
            # we pass placeholders that will be replaced atomically.
            ngo=claim.ngo,
            business=claim.listing.donor,
            stars=validated_data["stars"],
            comment=validated_data.get("comment", ""),
        )


# ---------------------------------------------------------------------------
# Rating – patch (edit within 7-day window)
# ---------------------------------------------------------------------------

class RatingPatchSerializer(serializers.ModelSerializer):
    """
    Accepted body for PATCH /ratings/<id>/.
    Only stars and comment may be changed; ngo/business are immutable.
    """
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


# ---------------------------------------------------------------------------
# Rating – read
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Pending-ratings list item (GET /ratings/pending/)
# ---------------------------------------------------------------------------

class PendingRatingSerializer(serializers.ModelSerializer):
    """
    Minimal view of a PICKED_UP claim that the NGO hasn't rated yet.
    Shown in the "Rate donors" tab.
    """
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


# ---------------------------------------------------------------------------
# Business ratings summary (GET /businesses/<id>/ratings/)
# ---------------------------------------------------------------------------

class BusinessRatingSummarySerializer(serializers.Serializer):
    """
    Aggregate stats + recent public reviews for a business.
    All aggregation is done with DB queries, not Python loops.
    """
    business_id = serializers.IntegerField()
    business_name = serializers.CharField()
    rating_avg = serializers.FloatField(allow_null=True)
    rating_count = serializers.IntegerField()
    breakdown = serializers.DictField(child=serializers.IntegerField())
    recent_reviews = RatingReadSerializer(many=True)
