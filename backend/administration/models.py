from django.conf import settings
from django.db import models


class AdminAuditLog(models.Model):
    """
    Append-only audit trail recording every administrative decision and action.
    Target types: Organization, Issue, Rating, User, System, etc.
    """
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_audit_logs",
        help_text="Platform administrator who executed the action.",
    )
    action = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Administrative action (e.g. VERIFY_ORG, REJECT_ORG, HIDE_RATING).",
    )
    target_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Model class or domain entity being acted upon.",
    )
    target_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Primary key identifier of the target entity.",
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured context parameters (reasons, status changes, notes).",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Admin Audit Log"
        verbose_name_plural = "Admin Audit Logs"
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        admin_name = self.admin_user.username if self.admin_user else "System"
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {admin_name} -> {self.action} on {self.target_type}#{self.target_id}"

    def delete(self, *args, **kwargs):
        raise PermissionError("AdminAuditLog records are append-only and cannot be deleted.")

    def save(self, *args, **kwargs):
        if self.pk and AdminAuditLog.objects.filter(pk=self.pk).exists():
            raise PermissionError("AdminAuditLog records are append-only and cannot be modified.")
        super().save(*args, **kwargs)


def log_admin_action(
    admin_user,
    action: str,
    target_type: str,
    target_id: str | int,
    details: dict | None = None,
) -> AdminAuditLog:
    """
    Helper to record an append-only administrative audit log entry.
    """
    return AdminAuditLog.objects.create(
        admin_user=admin_user,
        action=action,
        target_type=str(target_type),
        target_id=str(target_id),
        details=details or {},
    )


class Issue(models.Model):
    """
    Platform incident / dispute / grievance report filed by Business or NGO users,
    or flagged internally.
    """
    class Category(models.TextChoices):
        FOOD_QUALITY = "FOOD_QUALITY", "Food Quality"
        NO_SHOW = "NO_SHOW", "No Show"
        WRONG_QUANTITY = "WRONG_QUANTITY", "Wrong Quantity"
        ABUSE = "ABUSE", "Abuse"
        TECHNICAL = "TECHNICAL", "Technical"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_REVIEW = "IN_REVIEW", "In Review"
        RESOLVED = "RESOLVED", "Resolved"
        DISMISSED = "DISMISSED", "Dismissed"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reported_issues",
        help_text="User who reported the issue.",
    )
    reporter_org = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="reported_issues",
        help_text="Organization of the reporting user.",
    )
    target_org = models.ForeignKey(
        "accounts.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="targeted_issues",
        help_text="Organization against which the issue is reported (if any).",
    )
    claim = models.ForeignKey(
        "marketplace.Claim",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issues",
        help_text="Associated marketplace claim (if any).",
    )
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.OTHER,
        db_index=True,
    )
    description = models.TextField(
        help_text="Detailed description of the issue or dispute.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )
    admin_notes = models.TextField(
        blank=True,
        default="",
        help_text="Internal notes or communication records by platform admins.",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_issues",
        help_text="Platform administrator assigned to investigate.",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_issues",
        help_text="Platform administrator who resolved or dismissed the issue.",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Issue"
        verbose_name_plural = "Issues"
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["reporter_org", "status"]),
            models.Index(fields=["target_org"]),
        ]

    def __str__(self) -> str:
        return f"Issue #{self.id}: {self.category} ({self.status}) by {self.reporter.username}"

