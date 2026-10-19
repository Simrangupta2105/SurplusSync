"""
Marketplace models: Listing and Claim.
Only the fields required to support the Rating feature (Task 1).
"""
from django.db import models


class Listing(models.Model):
    """A surplus-food donation offer published by a business."""

    class Status(models.TextChoices):
        OPEN = "OPEN"
        RESERVED = "RESERVED"
        COMPLETED = "COMPLETED"
        CANCELLED = "CANCELLED"

    donor = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="listings",
        help_text="Business organisation that is donating the food.",
    )
    batch = models.ForeignKey(
        "inventory.Batch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="listings",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text="Quantity offered (same unit as the batch product).",
    )
    title = models.CharField(max_length=200)
    pickup_window_start = models.DateTimeField()
    pickup_window_end = models.DateTimeField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["donor", "status"]),
        ]

    def __str__(self) -> str:
        return f"Listing #{self.id} – {self.title} ({self.status})"


class Claim(models.Model):
    """An NGO's claim on a Listing."""

    class Status(models.TextChoices):
        PENDING = "PENDING"
        CONFIRMED = "CONFIRMED"
        PICKED_UP = "PICKED_UP"
        CANCELLED = "CANCELLED"

    listing = models.ForeignKey(
        Listing,
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

    Business rules enforced at both the model/serializer AND database level:
    - The claim must be in PICKED_UP status before a rating can be created.
    - The rater (ngo) must be the NGO that made the claim.
    - ngo and business are copied from the claim on save; client-supplied ids
      are ignored.
    - One rating per claim (OneToOneField + unique DB constraint).
    - Stars must be 1–5 (CheckConstraint on the DB, plus serializer validation).
    - Editing is allowed only within 7 days of created_at; after that the record
      is locked (enforced in the serializer / view).
    - Users cannot delete ratings; admins can hide them via is_hidden.
    """

    claim = models.OneToOneField(
        Claim,
        on_delete=models.CASCADE,
        related_name="rating",
        help_text="The PICKED_UP claim this rating is for.",
    )
    # Denormalized from the claim on save – never taken from the request.
    ngo = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="ratings_given",
        help_text="NGO that submitted the rating (copied from claim.ngo).",
    )
    business = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="ratings_received",
        help_text="Business that was rated (copied from claim.listing.donor).",
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
            # Enforce stars 1–5 at the database level.
            models.CheckConstraint(
                condition=models.Q(stars__gte=1) & models.Q(stars__lte=5),
                name="rating_stars_1_to_5",
            ),
        ]

    def is_editable(self) -> bool:
        """Return True if the rating is still within the 7-day edit window."""
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() <= self.created_at + timedelta(days=7)

    def save(self, *args, **kwargs) -> None:  # type: ignore[override]
        """
        Always copy ngo and business from the linked claim.
        This ensures client-supplied organisation ids can never be used.
        """
        self.ngo_id = self.claim.ngo_id
        self.business_id = self.claim.listing.donor_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"Rating #{self.id}: {self.stars}★ by {self.ngo} "
            f"for {self.business} (Claim #{self.claim_id})"
        )
