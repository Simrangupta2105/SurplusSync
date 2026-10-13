from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    StorageLocationViewSet,
    ProductViewSet,
    BatchViewSet,
    StockTransactionViewSet,
    AlertRuleViewSet,
    AlertViewSet,
    ImportJobViewSet,
    POSApiKeyViewSet,
    DashboardSummaryView,
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'storage-locations', StorageLocationViewSet)
router.register(r'products', ProductViewSet)
router.register(r'batches', BatchViewSet)
router.register(r'transactions', StockTransactionViewSet)
router.register(r'alert-rules', AlertRuleViewSet)
router.register(r'alerts', AlertViewSet)
router.register(r'import-jobs', ImportJobViewSet)
router.register(r'pos-keys', POSApiKeyViewSet)

urlpatterns = [
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('', include(router.urls)),
]
