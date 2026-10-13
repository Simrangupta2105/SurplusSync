from django.contrib.auth.models import AbstractUser
from django.db import models


class Organization(models.Model):
    class Type(models.TextChoices):
        BUSINESS = "BUSINESS"
        NGO = "NGO"

    name = models.CharField(max_length=200)
    org_type = models.CharField(max_length=10, choices=Type.choices)
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

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

    def __str__(self):
        return f"{self.username} ({self.role})"
