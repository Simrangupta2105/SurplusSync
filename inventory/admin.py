from django.contrib import admin
from .models import (
    Category,
    StorageLocation,
    Product,
    Batch,
    StockTransaction,
    AlertRule,
    Alert,
    ImportJob,
    POSApiKey,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'perishability_risk', 'storage_type', 'default_shelf_life_days')
    list_filter = ('perishability_risk', 'storage_type')
    search_fields = ('name',)


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'storage_type', 'capacity')
    list_filter = ('storage_type', 'organization')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'barcode', 'category', 'organization', 'unit', 'reorder_level', 'is_active')
    list_filter = ('category', 'is_active', 'organization')
    search_fields = ('name', 'sku', 'barcode')


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('product', 'organization', 'batch_code', 'quantity', 'expiry_date', 'status', 'location')
    list_filter = ('status', 'organization', 'expiry_date')
    search_fields = ('batch_code', 'product__name')


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ('batch', 'organization', 'txn_type', 'quantity', 'source', 'created_by', 'created_at')
    list_filter = ('txn_type', 'source', 'organization')
    search_fields = ('batch__batch_code', 'batch__product__name', 'reason')


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ('organization', 'category', 'days_before_expiry', 'is_active')
    list_filter = ('is_active', 'organization')


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('message', 'organization', 'batch', 'severity', 'is_acknowledged', 'created_at')
    list_filter = ('severity', 'is_acknowledged', 'organization')
    search_fields = ('message', 'batch__batch_code')


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization', 'status', 'rows_ok', 'rows_failed', 'created_at')
    list_filter = ('status', 'organization')


@admin.register(POSApiKey)
class POSApiKeyAdmin(admin.ModelAdmin):
    list_display = ('label', 'organization', 'is_active')
    list_filter = ('is_active', 'organization')
