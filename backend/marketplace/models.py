"""
Marketplace models: SurplusListing, NGORequirement, DonationRequest,
DonationStatusHistory, Notification, Claim, and Rating.
"""
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class SurplusListingQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        # Gracefully translate legacy field lookups if passed
        new_kwargs = {}
        for k, v in kwargs.items():
            if k == 'pickup_window_start' or k.startswith('pickup_window_start__'):
                new_kwargs[k.replace('pickup_window_start', 'available_from')] = v
            elif k == 'pickup_window_end' or k.startswith('pickup_window_end__'):
                new_kwargs[k.replace('pickup_window_end', 'available_until')] = v
            elif k == 'quantity' or k.startswith('quantity__'):
                new_kwargs[k.replace('quantity', 'quantity_offered')] = v
            else:
                new_kwargs[k] = v
        return super().filter(*args, **new_kwargs)


class SurplusListing(models.Model):
    """
    A surplus food donation offer published by a business.
    """
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        FULLY_RESERVED = "FULLY_RESERVED", "Fully Reserved"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    Status.RESERVED = Status.FULLY_RESERVED

    donor = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="listings",
        limit_choices_to={"org_type": "BUSINESS"},
        help_text="Business organization that is offering the surplus food.",
    )
    batch = models.ForeignKey(
        "inventory.Batch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="surplus_listings",
        help_text="Optional inventory batch linked to this listing.",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    category = models.ForeignKey(
        "inventory.Category",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="surplus_listings",
    )
    quantity_offered = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text="Total quantity offered for donation.",
    )
    quantity_reserved = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="Quantity currently reserved by approved/scheduled requests.",
    )
    unit = models.CharField(max_length=20, default="kg")
    pickup_address = models.TextField(blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    available_from = models.DateTimeField()
    available_until = models.DateTimeField()
    is_cooked = models.BooleanField(default=False)
    safe_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The time after which the food must not be handed over; available_until may not exceed it.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SurplusListingQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "available_until"], name="idx_listing_status_avail"),
            models.Index(fields=["donor", "status"], name="idx_listing_donor_status"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_offered__gt=0),
                name="check_listing_qty_offered_gt_0",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_reserved__gte=0) & models.Q(quantity_reserved__lte=models.F("quantity_offered")),
                name="check_listing_qty_reserved_range",
            ),
            models.CheckConstraint(
                condition=models.Q(available_until__gt=models.F("available_from")),
                name="check_listing_avail_until_gt_from",
            ),
            models.CheckConstraint(
                condition=models.Q(safe_until__isnull=True) | models.Q(available_until__lte=models.F("safe_until")),
                name="check_listing_avail_lte_safe",
            ),
        ]

    def __init__(self, *args, **kwargs):
        # Map legacy field names if provided
        if "quantity" in kwargs and "quantity_offered" not in kwargs:
            kwargs["quantity_offered"] = kwargs.pop("quantity")
        if "pickup_window_start" in kwargs and "available_from" not in kwargs:
            kwargs["available_from"] = kwargs.pop("pickup_window_start")
        if "pickup_window_end" in kwargs and "available_until" not in kwargs:
            kwargs["available_until"] = kwargs.pop("pickup_window_end")
        super().__init__(*args, **kwargs)

    @property
    def remaining_quantity(self) -> Decimal:
        return max(Decimal("0.000"), self.quantity_offered - self.quantity_reserved)

    # Legacy property aliases
    @property
    def quantity(self) -> Decimal:
        return self.quantity_offered

    @quantity.setter
    def quantity(self, val: Decimal):
        self.quantity_offered = val

    @property
    def pickup_window_start(self):
        return self.available_from

    @pickup_window_start.setter
    def pickup_window_start(self, val):
        self.available_from = val

    @property
    def pickup_window_end(self):
        return self.available_until

    @pickup_window_end.setter
    def pickup_window_end(self, val):
        self.available_until = val

    def save(self, *args, **kwargs):
        # Default category from batch product if not set
        if not self.category_id and self.batch_id and self.batch.product_id:
            self.category = self.batch.product.category
        # Default unit from batch product if not set
        if (not self.unit or self.unit == "kg") and self.batch_id and self.batch.product_id:
            self.unit = self.batch.product.unit or "kg"
        # Default location from donor if not set
        if self.donor_id:
            if not self.pickup_address:
                self.pickup_address = self.donor.address or ""
            if self.latitude is None:
                self.latitude = self.donor.latitude
            if self.longitude is None:
                self.longitude = self.donor.longitude
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Listing #{self.id} – {self.title} ({self.status})"


# Backward compatibility alias
Listing = SurplusListing


class NGORequirement(models.Model):
    """
    An NGO's recurring or one-time food requirements.
    """
    class Frequency(models.TextChoices):
        ONE_TIME = "ONE_TIME", "One Time"
        DAILY = "DAILY", "Daily"
        WEEKLY = "WEEKLY", "Weekly"

    ngo = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="requirements",
        limit_choices_to={"org_type": "NGO"},
        help_text="NGO organization declaring this requirement.",
    )
    title = models.CharField(max_length=200)
    categories = models.ManyToManyField(
        "inventory.Category",
        blank=True,
        related_name="ngo_requirements",
    )
    min_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
    )
    max_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )
    unit = models.CharField(max_length=20, default="kg")
    radius_km = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("15.00"),
    )
    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.ONE_TIME,
    )
    needed_by = models.DateField(null=True, blank=True)
    dietary_notes = models.TextField(blank=True, default="")
    accepts_cooked_food = models.BooleanField(default=False)
    preferred_pickup_start = models.TimeField(null=True, blank=True)
    preferred_pickup_end = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ngo", "is_active"], name="idx_ngo_req_active"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(min_quantity__gte=0)
                    & models.Q(max_quantity__gt=0)
                    & models.Q(max_quantity__gte=models.F("min_quantity"))
                ),
                name="check_ngo_req_quantity_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(radius_km__gt=0),
                name="check_ngo_req_radius_gt_0",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ngo.name} – {self.title} ({self.min_quantity}-{self.max_quantity} {self.unit})"


class DonationRequestSequence(models.Model):
    """
    Guarantees thread-safe, monotonic, collision-free code generation REQ-####.
    """
    last_val = models.PositiveIntegerField(default=1000)

    class Meta:
        db_table = "marketplace_request_sequence"


class DonationRequest(models.Model):
    """
    A donation request initiated by an NGO against a SurplusListing.
    """
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        APPROVED = "APPROVED", "Approved"
        SCHEDULED = "SCHEDULED", "Scheduled"
        IN_TRANSIT = "IN_TRANSIT", "In Transit"
        COLLECTED = "COLLECTED", "Collected"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        NO_SHOW = "NO_SHOW", "No Show"
        EXPIRED = "EXPIRED", "Expired"

    code = models.CharField(max_length=20, unique=True, db_index=True)
    listing = models.ForeignKey(
        SurplusListing,
        on_delete=models.CASCADE,
        related_name="requests",
    )
    ngo = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="donation_requests",
        limit_choices_to={"org_type": "NGO"},
    )
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_approved = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )
    quantity_collected = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
        db_index=True,
    )
    proposed_pickup_start = models.DateTimeField()
    proposed_pickup_end = models.DateTimeField()
    confirmed_pickup_start = models.DateTimeField(null=True, blank=True)
    confirmed_pickup_end = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default="")
    rejection_reason = models.TextField(blank=True, default="")
    contact_name = models.CharField(max_length=100, blank=True, default="")
    contact_phone = models.CharField(max_length=30, blank=True, default="")
    beneficiaries_served = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional count of individuals/beneficiaries served from this donation.",
    )

    # Status timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    in_transit_at = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    no_show_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["ngo", "status"], name="idx_req_ngo_status"),
            models.Index(fields=["listing", "status"], name="idx_req_listing_status"),
            models.Index(fields=["status", "confirmed_pickup_start"], name="idx_req_status_pickup_start"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_requested__gt=0),
                name="check_request_qty_requested_gt_0",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_approved__isnull=True) | models.Q(quantity_approved__gt=0),
                name="check_request_qty_approved_gt_0",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_collected__isnull=True) | models.Q(quantity_collected__gte=0),
                name="check_request_qty_collected_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(proposed_pickup_end__gt=models.F("proposed_pickup_start")),
                name="check_req_prop_end_gt_start",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(confirmed_pickup_end__isnull=True)
                    | models.Q(confirmed_pickup_end__gt=models.F("confirmed_pickup_start"))
                ),
                name="check_req_conf_end_gt_start",
            ),
            models.CheckConstraint(
                condition=models.Q(beneficiaries_served__isnull=True) | models.Q(beneficiaries_served__gte=0),
                name="check_request_beneficiaries_served_gte_0",
            ),
            models.UniqueConstraint(
                fields=["listing", "ngo"],
                condition=models.Q(
                    status__in=[
                        "REQUESTED",
                        "APPROVED",
                        "SCHEDULED",
                        "IN_TRANSIT",
                        "COLLECTED",
                    ]
                ),
                name="uniq_active_req_per_ngo_listing",
            ),
        ]

    @classmethod
    def generate_next_code(cls) -> str:
        with transaction.atomic():
            seq, _ = DonationRequestSequence.objects.select_for_update().get_or_create(
                id=1,
                defaults={"last_val": 1000},
            )
            seq.last_val += 1
            seq.save(update_fields=["last_val"])
            code = f"REQ-{seq.last_val:04d}"
            while cls.objects.filter(code=code).exists():
                seq.last_val += 1
                seq.save(update_fields=["last_val"])
                code = f"REQ-{seq.last_val:04d}"
            return code

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = DonationRequest.generate_next_code()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} ({self.status}) – {self.ngo.name} on Listing #{self.listing_id}"


class DonationStatusHistory(models.Model):
    """
    Append-only audit trail of every status transition on a DonationRequest.
    """
    request = models.ForeignKey(
        DonationRequest,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="donation_status_changes",
    )
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["request", "created_at"], name="idx_hist_req_created"),
        ]

    def __str__(self) -> str:
        return f"{self.request.code}: {self.from_status} -> {self.to_status} at {self.created_at}"


class Notification(models.Model):
    """
    Tenant-scoped notifications for business and NGO users.
    """
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    body = models.TextField()
    link = models.CharField(max_length=255, blank=True, default="")
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "is_read", "created_at"], name="idx_notif_org_read_created"),
        ]

    def __str__(self) -> str:
        return f"[{self.type}] {self.title} for {self.organization.name}"


class Claim(models.Model):
    """
    Legacy claim model maintained for backwards compatibility with existing tests.
    """
    class Status(models.TextChoices):
        PENDING = "PENDING"
        CONFIRMED = "CONFIRMED"
        PICKED_UP = "PICKED_UP"
        CANCELLED = "CANCELLED"

    listing = models.ForeignKey(
        SurplusListing,
        on_delete=models.CASCADE,
        related_name="claims",
    )
    ngo = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="claims",
        help_text="NGO organisation that is claiming the food.",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    pickup_eta = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Estimated pickup date/time agreed between parties.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ngo", "status"]),
            models.Index(fields=["listing", "ngo"]),
        ]

    def __str__(self) -> str:
        return f"Claim #{self.id} by {self.ngo} on Listing #{self.listing_id} ({self.status})"


class Rating(models.Model):
    """
    An NGO's rating of the business that donated food.
    Supports both legacy Claim and new DonationRequest.
    """
    claim = models.OneToOneField(
        Claim,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="rating",
        help_text="The PICKED_UP claim this rating is for.",
    )
    request = models.OneToOneField(
        DonationRequest,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="rating",
        help_text="The COMPLETED donation request this rating is for.",
    )
    ngo = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="ratings_given",
        help_text="NGO that submitted the rating.",
    )
    business = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="ratings_received",
        help_text="Business that was rated.",
    )
    stars = models.PositiveSmallIntegerField(
        help_text="Rating from 1 (worst) to 5 (best).",
    )
    comment = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Optional review comment (max 500 characters).",
    )
    is_hidden = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Hidden by admin moderation; excluded from public averages.",
    )
    hidden_reason = models.TextField(
        blank=True,
        default="",
        help_text="Reason provided by admin when moderating this rating.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "is_hidden"]),
            models.Index(fields=["ngo", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stars__gte=1) & models.Q(stars__lte=5),
                name="rating_stars_1_to_5",
            ),
        ]

    def is_editable(self) -> bool:
        return timezone.now() <= self.created_at + timedelta(days=7)

    def save(self, *args, **kwargs) -> None:
        if self.request_id:
            self.ngo_id = self.request.ngo_id
            self.business_id = self.request.listing.donor_id
        elif self.claim_id:
            self.ngo_id = self.claim.ngo_id
            self.business_id = self.claim.listing.donor_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Rating #{self.id}: {self.stars}★ by {self.ngo} for {self.business}"
