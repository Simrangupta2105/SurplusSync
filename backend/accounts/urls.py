from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    OrganizationViewSet,
    UserViewSet,
    RegisterView,
    MeView,
    CustomTokenObtainPairView,
)

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='account-register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='account-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='account-token-refresh'),
    path('me/', MeView.as_view(), name='account-me'),
    path('', include(router.urls)),
]
