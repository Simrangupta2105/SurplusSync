from rest_framework import serializers
from accounts.models import Organization, User
from .models import AdminAuditLog, Issue


class AdminAuditLogSerializer(serializers.ModelSerializer):
    admin_username = serializers.CharField(source="admin_user.username", read_only=True)
    admin_email = serializers.CharField(source="admin_user.email", read_only=True)

    class Meta:
        model = AdminAuditLog
        fields = [
            "id",
            "admin_user",
            "admin_username",
            "admin_email",
            "action",
            "target_type",
            "target_id",
            "details",
            "created_at",
        ]
        read_only_fields = fields


class AdminUserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "date_joined",
            "last_login",
        ]
        read_only_fields = fields


class AdminOrganizationListSerializer(serializers.ModelSerializer):
    users_count = serializers.IntegerField(read_only=True, default=0)
    batches_count = serializers.IntegerField(read_only=True, default=0)
    claims_count = serializers.IntegerField(read_only=True, default=0)
    listings_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "org_type",
            "address",
            "latitude",
            "longitude",
            "phone",
            "is_verified",
            "verification_status",
            "verification_note",
            "verified_at",
            "created_at",
            "users_count",
            "batches_count",
            "claims_count",
            "listings_count",
        ]
        read_only_fields = fields


class AdminOrganizationDetailSerializer(AdminOrganizationListSerializer):
    users = AdminUserMiniSerializer(many=True, read_only=True)
    recent_activity = serializers.SerializerMethodField()

    class Meta(AdminOrganizationListSerializer.Meta):
        fields = AdminOrganizationListSerializer.Meta.fields + [
            "users",
            "recent_activity",
        ]
        read_only_fields = fields

    def get_recent_activity(self, obj):
        from marketplace.models import Listing, Claim, Rating
        from inventory.models import Batch
        from .models import AdminAuditLog

        activity = {
            "listings": [],
            "batches": [],
            "claims": [],
            "ratings": [],
            "audit_logs": [],
        }

        if obj.org_type == Organization.Type.BUSINESS:
            listings_data = list(
                Listing.objects.filter(donor=obj)
                .order_by("-created_at")[:10]
                .values("id", "title", "quantity_offered", "status", "created_at")
            )
            for item in listings_data:
                item["quantity"] = item.pop("quantity_offered", None)
            activity["listings"] = listings_data
            activity["batches"] = list(
                Batch.objects.filter(organization=obj)
                .select_related("product")
                .order_by("-created_at")[:10]
                .values("id", "product__name", "quantity", "status", "expiry_date", "created_at")
            )
            activity["ratings"] = list(
                Rating.objects.filter(business=obj, is_hidden=False)
                .order_by("-created_at")[:10]
                .values("id", "ngo__name", "stars", "comment", "created_at")
            )
        elif obj.org_type == Organization.Type.NGO:
            activity["claims"] = list(
                Claim.objects.filter(ngo=obj)
                .select_related("listing", "listing__donor")
                .order_by("-created_at")[:10]
                .values("id", "listing_id", "listing__title", "listing__donor__name", "status", "pickup_eta", "created_at")
            )
            activity["ratings"] = list(
                Rating.objects.filter(ngo=obj, is_hidden=False)
                .order_by("-created_at")[:10]
                .values("id", "business__name", "stars", "comment", "created_at")
            )

        activity["audit_logs"] = list(
            AdminAuditLog.objects.filter(target_type="Organization", target_id=str(obj.id))
            .select_related("admin_user")
            .order_by("-created_at")[:10]
            .values("id", "action", "admin_user__username", "details", "created_at")
        )

        return activity


class IssueCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = [
            "category",
            "description",
            "target_org",
            "claim",
            "priority",
        ]

    def validate_description(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Description is required.")
        return value.strip()

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        user_org = getattr(user, "organization", None)
        if not user_org:
            raise serializers.ValidationError("User must belong to an organization to report an issue.")

        claim = attrs.get("claim")
        target_org = attrs.get("target_org")

        if claim:
            if claim.ngo_id != user_org.id and claim.listing.donor_id != user_org.id:
                raise serializers.ValidationError(
                    {"claim": "You can only report issues for claims involving your organization."}
                )
            if not target_org:
                if user_org.id == claim.ngo_id:
                    attrs["target_org"] = claim.listing.donor
                else:
                    attrs["target_org"] = claim.ngo

        return attrs


class IssueReadSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source="reporter.username", read_only=True)
    reporter_org_name = serializers.CharField(source="reporter_org.name", read_only=True)
    reporter_org_type = serializers.CharField(source="reporter_org.org_type", read_only=True)
    target_org_name = serializers.CharField(source="target_org.name", read_only=True, default=None)
    target_org_type = serializers.CharField(source="target_org.org_type", read_only=True, default=None)
    claim_title = serializers.CharField(source="claim.listing.title", read_only=True, default=None)

    class Meta:
        model = Issue
        fields = [
            "id",
            "reporter",
            "reporter_name",
            "reporter_org",
            "reporter_org_name",
            "reporter_org_type",
            "target_org",
            "target_org_name",
            "target_org_type",
            "claim",
            "claim_title",
            "category",
            "description",
            "status",
            "priority",
            "admin_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AdminIssueSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source="reporter.username", read_only=True)
    reporter_email = serializers.CharField(source="reporter.email", read_only=True)
    reporter_org_name = serializers.CharField(source="reporter_org.name", read_only=True)
    reporter_org_type = serializers.CharField(source="reporter_org.org_type", read_only=True)
    target_org_name = serializers.CharField(source="target_org.name", read_only=True, default=None)
    target_org_type = serializers.CharField(source="target_org.org_type", read_only=True, default=None)
    claim_title = serializers.CharField(source="claim.listing.title", read_only=True, default=None)
    claim_status = serializers.CharField(source="claim.status", read_only=True, default=None)
    assigned_to_name = serializers.CharField(source="assigned_to.username", read_only=True, default=None)
    assigned_to_email = serializers.CharField(source="assigned_to.email", read_only=True, default=None)
    resolved_by_name = serializers.CharField(source="resolved_by.username", read_only=True, default=None)

    class Meta:
        model = Issue
        fields = [
            "id",
            "reporter",
            "reporter_name",
            "reporter_email",
            "reporter_org",
            "reporter_org_name",
            "reporter_org_type",
            "target_org",
            "target_org_name",
            "target_org_type",
            "claim",
            "claim_title",
            "claim_status",
            "category",
            "description",
            "status",
            "priority",
            "admin_notes",
            "assigned_to",
            "assigned_to_name",
            "assigned_to_email",
            "resolved_by",
            "resolved_by_name",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reporter",
            "reporter_name",
            "reporter_email",
            "reporter_org",
            "reporter_org_name",
            "reporter_org_type",
            "target_org",
            "target_org_name",
            "target_org_type",
            "claim",
            "claim_title",
            "claim_status",
            "category",
            "description",
            "resolved_by",
            "resolved_by_name",
            "resolved_at",
            "created_at",
            "updated_at",
        ]


class AdminRatingSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="business.name", read_only=True)
    ngo_name = serializers.CharField(source="ngo.name", read_only=True)
    claim_title = serializers.CharField(source="claim.listing.title", read_only=True, default=None)

    class Meta:
        from marketplace.models import Rating
        model = Rating
        fields = [
            "id",
            "stars",
            "comment",
            "is_hidden",
            "hidden_reason",
            "business",
            "business_name",
            "ngo",
            "ngo_name",
            "claim",
            "claim_title",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


