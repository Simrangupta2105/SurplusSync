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

    class Meta:
        model = Product
        fields = '__all__'


class BatchSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

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

    class Meta:
        model = ImportJob
        fields = '__all__'


class POSApiKeySerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = POSApiKey
        fields = ['id', 'organization', 'label', 'is_active']
