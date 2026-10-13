from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from .models import Organization, User


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'organization', 'role']


class MeSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'organization']

    def get_organization(self, obj):
        o = obj.organization
        if not o:
            return None
        return {
            'id': o.id,
            'name': o.name,
            'type': o.org_type,
            'is_verified': o.is_verified,
        }


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    org_name = serializers.CharField(max_length=200)
    org_type = serializers.ChoiceField(choices=Organization.Type.choices)
    address = serializers.CharField(required=False, allow_blank=True, default='')
    phone = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        org = Organization.objects.create(
            name=validated_data['org_name'],
            org_type=validated_data['org_type'],
            address=validated_data.get('address', ''),
            phone=validated_data.get('phone', ''),
            is_verified=False,
        )
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            organization=org,
            role=User.Role.OWNER,
        )
        return user

    def to_representation(self, instance):
        return MeSerializer(instance).data
