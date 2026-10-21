from rest_framework import serializers
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


def get_serializer_org(serializer):
    request = serializer.context.get('request')
    if not request:
        return None
    user = getattr(request, 'user', None)
    if user and user.is_authenticated and hasattr(user, 'organization') and user.organization:
        return user.organization
    auth = getattr(request, 'auth', None)
    if auth and hasattr(auth, 'org_type'):
        return auth
    return None


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class StorageLocationSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StorageLocation
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default='')

    class Meta:
        model = Product
        fields = '__all__'


class BatchSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True, default='')
    product_barcode = serializers.CharField(source='product.barcode', read_only=True, default='')
    category = serializers.CharField(source='product.category.name', read_only=True, default='')
    category_name = serializers.CharField(source='product.category.name', read_only=True, default='')
    unit = serializers.CharField(source='product.unit', read_only=True, default='kg')
    unit_cost = serializers.DecimalField(source='product.unit_cost', max_digits=10, decimal_places=2, read_only=True, allow_null=True)
    location_name = serializers.CharField(source='location.name', read_only=True, default='')
    sellable_quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = Batch
        fields = '__all__'

    def validate_product(self, value):
        org = get_serializer_org(self)
        if org and value.organization_id != org.id:
            raise serializers.ValidationError("Product does not belong to your organization.")
        return value

    def validate_location(self, value):
        if value is not None:
            org = get_serializer_org(self)
            if org and value.organization_id != org.id:
                raise serializers.ValidationError("Storage location does not belong to your organization.")
        return value


class StockTransactionSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StockTransaction
        fields = '__all__'

    def validate_batch(self, value):
        org = get_serializer_org(self)
        if org and value.organization_id != org.id:
            raise serializers.ValidationError("Batch does not belong to your organization.")
        return value


class AlertRuleSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = AlertRule
        fields = '__all__'


class AlertSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    product_name = serializers.CharField(source='batch.product.name', read_only=True, default='')
    batch_code = serializers.CharField(source='batch.batch_code', read_only=True, default='')
    batch_status = serializers.CharField(source='batch.status', read_only=True, default='')
    expiry_date = serializers.DateField(source='batch.expiry_date', read_only=True, default=None)

    class Meta:
        model = Alert
        fields = '__all__'

    def validate_batch(self, value):
        org = get_serializer_org(self)
        if org and value.organization_id != org.id:
            raise serializers.ValidationError("Batch does not belong to your organization.")
        return value

    def validate_rule(self, value):
        if value is not None:
            org = get_serializer_org(self)
            if org and value.organization_id != org.id:
                raise serializers.ValidationError("Alert rule does not belong to your organization.")
        return value


class ImportJobSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    worker_may_be_down = serializers.SerializerMethodField()

    class Meta:
        model = ImportJob
        fields = [
            'id',
            'organization',
            'file',
            'status',
            'total_rows',
            'processed_rows',
            'started_at',
            'finished_at',
            'error_message',
            'rows_ok',
            'rows_failed',
            'error_report',
            'created_at',
            'worker_may_be_down',
        ]
        read_only_fields = [
            'status',
            'total_rows',
            'processed_rows',
            'started_at',
            'finished_at',
            'error_message',
            'rows_ok',
            'rows_failed',
            'error_report',
            'created_at',
            'worker_may_be_down',
        ]

    def get_worker_may_be_down(self, obj) -> bool:
        if obj.status == ImportJob.Status.PENDING and obj.created_at:
            from django.utils import timezone
            from datetime import timedelta
            return timezone.now() - obj.created_at > timedelta(minutes=2)
        return False



class POSApiKeySerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    raw_key = serializers.SerializerMethodField(read_only=True)
    key_prefix = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = POSApiKey
        fields = ['id', 'organization', 'label', 'is_active', 'raw_key', 'key_prefix']

    def get_raw_key(self, obj):
        return getattr(obj, '_raw_key', None)

    def get_key_prefix(self, obj):
        if getattr(obj, 'key_hash', None):
            h = obj.key_hash
            prefix = "sps_test" if "test" in (obj.label or "").lower() else "sps_live"
            return f"{prefix}_{h[:2]}...{h[12:16]}" if len(h) >= 16 else f"{prefix}_{h[:6]}..."
        return "sps_live_******"
