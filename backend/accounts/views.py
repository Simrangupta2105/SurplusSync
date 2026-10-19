from rest_framework import viewsets, permissions, generics
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import Organization, User
from .serializers import (
    OrganizationSerializer,
    UserSerializer,
    RegisterSerializer,
    MeSerializer,
    CustomTokenObtainPairSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        try:
            from core.emailing import send_registration_welcome_email
            send_registration_welcome_email(user.id)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to trigger welcome email for user %s: %s", user.id, exc)


class MeView(generics.RetrieveAPIView):
    serializer_class = MeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Avg, Count, Q
        qs = self.queryset.annotate(
            rating_avg=Avg('ratings_received__stars', filter=Q(ratings_received__is_hidden=False)),
            rating_count=Count('ratings_received', filter=Q(ratings_received__is_hidden=False)),
        ).order_by('name')
        user = self.request.user
        if not user or not user.is_authenticated:
            return qs.none()
        if user.is_platform_admin or user.is_superuser:
            return qs.all()
        if hasattr(user, 'organization') and user.organization:
            return qs.filter(id=user.organization.id)
        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        if not (user.is_platform_admin or user.is_superuser):
            raise permissions.exceptions.PermissionDenied(
                "Organizations can only be registered via the registration endpoint."
            )
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        target_org = self.get_object()
        if user.is_platform_admin or user.is_superuser:
            serializer.save()
            return
        # Ensure normal users can never modify is_verified
        serializer.save(is_verified=target_org.is_verified)

    def perform_destroy(self, instance):
        user = self.request.user
        if not (user.is_platform_admin or user.is_superuser):
            raise permissions.exceptions.PermissionDenied(
                "Organizations cannot be deleted by tenant members."
            )
        instance.delete()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return self.queryset.none()
        if user.is_platform_admin or user.is_superuser:
            return self.queryset.all()
        if hasattr(user, 'organization') and user.organization:
            return self.queryset.filter(organization=user.organization)
        return self.queryset.filter(id=user.id)

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_platform_admin or user.is_superuser:
            serializer.save()
            return

        if not hasattr(user, 'organization') or not user.organization:
            raise permissions.exceptions.PermissionDenied("You must belong to an organization to add members.")
        if user.role != User.Role.OWNER:
            raise permissions.exceptions.PermissionDenied("Only organization owners can create new members.")

        # Force tenant organization and prevent privilege escalation
        serializer.save(
            organization=user.organization,
            is_staff=False,
            is_superuser=False,
        )

    def perform_update(self, serializer):
        user = self.request.user
        target = self.get_object()

        if user.is_platform_admin or user.is_superuser:
            serializer.save()
            return

        # Ensure normal tenant users cannot alter tenant or escalate privileges
        extra_kwargs = {
            'organization': target.organization,
            'is_staff': False,
            'is_superuser': False,
        }
        if user.role != User.Role.OWNER:
            # Staff cannot alter roles
            extra_kwargs['role'] = target.role

        serializer.save(**extra_kwargs)

    def perform_destroy(self, instance):
        user = self.request.user
        if user.is_platform_admin or user.is_superuser:
            instance.delete()
            return

        if not hasattr(user, 'organization') or not user.organization:
            raise permissions.exceptions.PermissionDenied("Permission denied.")
        if user.role != User.Role.OWNER:
            raise permissions.exceptions.PermissionDenied("Only organization owners can remove members.")
        if instance.organization_id != user.organization_id:
            raise permissions.exceptions.PermissionDenied("Cannot delete users from another organization.")
        instance.delete()
