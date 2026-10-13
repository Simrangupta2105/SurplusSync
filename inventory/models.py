from django.conf import settings
from django.db import models


class Category(models.Model):
    """Food taxonomy: Dairy > Milk, Produce > Leafy Greens, etc."""
    class Risk(models.IntegerChoices):
        LOW = 1
        MEDIUM = 2
        HIGH = 3
        CRITICAL = 4

    class Storage(models.TextChoices):
        AMBIENT = "AMBIENT"
        CHILLED = "CHILLED"
        FROZEN = "FROZEN"

    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    perishability_risk = models.IntegerField(choices=Risk.choices, default=Risk.MEDIUM)
    storage_type = models.CharField(max_length=10, choices=Storage.choices, default=Storage.AMBIENT)
    default_shelf_life_days = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class StorageLocation(models.Model):
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)          # "Walk-in fridge 1"
    storage_type = models.CharField(max_length=10, choices=Category.Storage.choices)
    capacity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.storage_type})"


class Product(models.Model):
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=64, blank=True)
    barcode = models.CharField(max_length=64, blank=True, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    unit = models.CharField(max_length=20, default="kg")      # kg, L, pcs
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    reorder_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "sku"],
                name="uniq_sku_per_org",
                condition=~models.Q(sku="")
            ),
        ]

    def __str__(self):
        return self.name


class Batch(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        EXPIRED = "EXPIRED"
        DEPLETED = "DEPLETED"
        DONATED = "DONATED"

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE)  # denormalized for fast tenant filtering
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="batches")
    location = models.ForeignKey(StorageLocation, null=True, blank=True, on_delete=models.SET_NULL)
    batch_code = models.CharField(max_length=64, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    received_date = models.DateField()
    expiry_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Batches"
        ordering = ["expiry_date", "id"]
        indexes = [
            models.Index(fields=["organization", "status", "expiry_date"]),
        ]

    def __str__(self):
        return f"{self.product.name} - Batch {self.batch_code or self.id}"


class StockTransaction(models.Model):
    """Append-only ledger. This is the history the AI module will train on."""
    class Type(models.TextChoices):
        RECEIVED = "RECEIVED"
        SOLD = "SOLD"
        WASTED = "WASTED"
        DONATED = "DONATED"
        ADJUSTMENT = "ADJUSTMENT"

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="transactions")
    txn_type = models.CharField(max_length=12, choices=Type.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=200, blank=True)   # "spoiled", "damaged"
    source = models.CharField(max_length=20, default="MANUAL")  # MANUAL / CSV / POS / SCAN
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.txn_type} {self.quantity} - {self.batch}"


class AlertRule(models.Model):
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE)  # null = all
    days_before_expiry = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        cat = self.category.name if self.category else "All Categories"
        return f"{cat} - {self.days_before_expiry} days"


class Alert(models.Model):
    class Severity(models.TextChoices):
        INFO = "INFO"
        WARNING = "WARNING"
        CRITICAL = "CRITICAL"

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="alerts")
    rule = models.ForeignKey(AlertRule, null=True, on_delete=models.SET_NULL)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    message = models.CharField(max_length=255)
    is_acknowledged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.severity}] {self.message}"


class ImportJob(models.Model):
    """CSV bulk upload tracking."""
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE)
    file = models.FileField(upload_to="imports/")
    status = models.CharField(max_length=10, default="PENDING")   # PENDING/DONE/FAILED
    rows_ok = models.PositiveIntegerField(default=0)
    rows_failed = models.PositiveIntegerField(default=0)
    error_report = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Import #{self.id} ({self.status})"


class POSApiKey(models.Model):
    """For POS integration via REST. Store only a hash of the key."""
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE)
    key_hash = models.CharField(max_length=128, unique=True)
    label = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.label} ({self.organization.name})"
