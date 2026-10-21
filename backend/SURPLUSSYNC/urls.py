"""
URL configuration for SURPLUSSYNC project.
"""
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from accounts.models import User


def api_users_view(request):
    users = [
        {
            "id": u.id,
            "name": u.username,
            "email": u.email or f"{u.username}@surplussync.com",
        }
        for u in User.objects.all()
    ]
    return JsonResponse(users, safe=False)


urlpatterns = [
    path('admin/', admin.site.urls),
    re_path(r'^api/?$', api_users_view, name='api-users-root'),
    path('api/accounts/', include('accounts.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/v1/accounts/', include('accounts.urls')),
    path('api/v1/inventory/', include('inventory.urls')),
    path('api/v1/marketplace/', include('marketplace.urls')),
    path('api/v1/issues/', include('administration.tenant_urls')),
    path('api/v1/admin/', include('administration.urls')),
    path('api/v1/home/', include('core.home_urls')),
    path('api/v1/predictions/', include('predictions.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
