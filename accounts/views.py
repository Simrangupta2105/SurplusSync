from rest_framework import viewsets, permissions, generics
from .models import Organization, User
from .serializers import (
    OrganizationSerializer,
    UserSerializer,
    RegisterSerializer,
    MeSerializer,
)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


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
        user = self.request.user
        if user.is_superuser:
            return self.queryset.all()
        if hasattr(user, 'organization') and user.organization:
            return self.queryset.filter(id=user.organization.id)
        return self.queryset.none()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return self.queryset.all()
        if hasattr(user, 'organization') and user.organization:
            return self.queryset.filter(organization=user.organization)
        return self.queryset.filter(id=user.id)
