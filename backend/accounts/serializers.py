from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from .models import Organization, User


from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import exceptions


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user and self.user.organization:
            if getattr(self.user.organization, 'verification_status', None) == Organization.VerificationStatus.SUSPENDED:
                raise exceptions.AuthenticationFailed(
                    "Your organization has been suspended. Please contact platform support."
                )
        return data


class OrganizationSerializer(serializers.ModelSerializer):
    rating_avg = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = '__all__'
        read_only_fields = [
            'id',
            'is_verified',
            'verification_status',
            'verification_note',
            'verified_at',
            'created_at',
        ]

    def get_rating_avg(self, obj):
        if obj.org_type != Organization.Type.BUSINESS:
            return None
        val = getattr(obj, "rating_avg", None)
        if val is not None:
            return round(float(val), 2)
        from django.db.models import Avg
        from marketplace.models import Rating
        agg = Rating.objects.filter(business=obj, is_hidden=False).aggregate(avg=Avg("stars"))
        return round(float(agg["avg"]), 2) if agg["avg"] else None

    def get_rating_count(self, obj):
        if obj.org_type != Organization.Type.BUSINESS:
            return None
        val = getattr(obj, "rating_count", None)
        if val is not None:
            return val
        from marketplace.models import Rating
        return Rating.objects.filter(business=obj, is_hidden=False).count()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'organization', 'role']
        read_only_fields = ['id', 'organization']


class MeSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    is_platform_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'organization', 'is_platform_admin']

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
            is_staff=False,
            is_superuser=False,
        )
        return user

    def to_representation(self, instance):
        return MeSerializer(instance).data
