from django.contrib.auth.models import AbstractUser
from django.db import models


class Organization(models.Model):
    class Type(models.TextChoices):
        BUSINESS = "BUSINESS"
        NGO = "NGO"

    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"
        SUSPENDED = "SUSPENDED", "Suspended"

    class BusinessSegment(models.TextChoices):
        RESTAURANT = "Restaurant", "Restaurant"
        SUPERMARKET = "Supermarket", "Supermarket"
        CAFETERIA = "Cafeteria", "Cafeteria"
        CLOUD_KITCHEN = "Cloud Kitchen", "Cloud Kitchen"

    name = models.CharField(max_length=200)
    org_type = models.CharField(max_length=10, choices=Type.choices)
    business_segment = models.CharField(
        max_length=20,
        choices=BusinessSegment.choices,
        null=True,
        blank=True,
        db_index=True,
        help_text="Operational business segment for AI demand scaling and waste benchmarks.",
    )
    promotion_active = models.BooleanField(
        default=False,
        help_text="Flag indicating whether an active promotional discount is running, driving demand lift.",
    )
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_verified = models.BooleanField(default=False)
    email_alerts_enabled = models.BooleanField(default=True)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
    )
    verification_note = models.TextField(blank=True, default="")
    verified_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    max_concurrent_pickups = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.verification_status == self.VerificationStatus.VERIFIED:
            self.is_verified = True
            if not self.verified_at:
                self.verified_at = timezone.now()
        elif self.is_verified and self.verification_status == self.VerificationStatus.PENDING:
            self.verification_status = self.VerificationStatus.VERIFIED
            if not self.verified_at:
                self.verified_at = timezone.now()
        else:
            self.is_verified = False
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "OWNER"
        STAFF = "STAFF"

    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.CASCADE, related_name="users")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)

    class Meta:
        ordering = ["id"]

    @property
    def is_platform_admin(self) -> bool:
        """
        A platform admin is a User with is_staff=True and no organization.
        Separate from tenant organization roles (OWNER/STAFF).
        """
        return bool(self.is_staff and self.organization_id is None)

    def __str__(self):
        return f"{self.username} ({self.role})"
