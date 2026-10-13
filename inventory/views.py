from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.db.models import Sum, F, DecimalField, Q, Case, When, Value, Count
from django.db.models.functions import Coalesce
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .services import (
    resolve_product,
    acquire_external_id_lock,
    deduct_product_fefo,
    InsufficientStockError,
)


from .authentication import POSApiKeyUser
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
from .serializers import (
    CategorySerializer,
    StorageLocationSerializer,
    ProductSerializer,
    BatchSerializer,
    StockTransactionSerializer,
    AlertRuleSerializer,
    AlertSerializer,
    ImportJobSerializer,
    POSApiKeySerializer,
)


class TenantFilteredModelViewSet(viewsets.ModelViewSet):
    """
    Base viewset enforcing multi-tenant isolation.
    Ensures users only access data belonging to their organization.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_tenant_org(self):
        user = getattr(self.request, 'user', None)
        if user and user.is_authenticated and hasattr(user, 'organization') and user.organization:
            return user.organization
        auth = getattr(self.request, 'auth', None)
        if auth and hasattr(auth, 'org_type'):
            return auth
        return None

    def get_queryset(self):
        user = getattr(self.request, 'user', None)
        if user and user.is_authenticated and user.is_superuser:
            return self.queryset.all()
        org = self._get_tenant_org()
        if org:
            return self.queryset.filter(organization=org)
        return self.queryset.none()

    def perform_create(self, serializer):
        org = self._get_tenant_org()
        extra = {}
        if org:
            extra['organization'] = org
        serializer.save(**extra)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['perishability_risk', 'storage_type', 'parent']
    search_fields = ['name']
    ordering_fields = ['name', 'perishability_risk', 'default_shelf_life_days']


class StorageLocationViewSet(TenantFilteredModelViewSet):
    queryset = StorageLocation.objects.all()
    serializer_class = StorageLocationSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['storage_type']
    search_fields = ['name']


class ProductViewSet(TenantFilteredModelViewSet):
    queryset = Product.objects.select_related('category', 'organization').all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_active', 'barcode', 'sku']
    search_fields = ['name', 'sku', 'barcode']
    ordering_fields = ['name', 'unit_cost', 'reorder_level']

    @action(detail=False, methods=['get'], url_path='barcode/(?P<barcode_val>[^/.]+)')
    def lookup_barcode(self, request, barcode_val=None):
        """
        Quick barcode lookup for mobile/scanner inputs.
        Checks local organization product catalog first.
        Falls back to Open Food Facts API if not found locally.
        """
        products = self.get_queryset().filter(barcode=barcode_val)
        if products.exists():
            data = self.get_serializer(products.first()).data
            data['source'] = 'local'
            return Response(data, status=status.HTTP_200_OK)

        # Fallback to Open Food Facts
        from .services import fetch_open_food_facts
        off_data = fetch_open_food_facts(barcode_val)
        if off_data:
            return Response(off_data, status=status.HTTP_200_OK)

        return Response(
            {'detail': f'Product with barcode {barcode_val} not found locally or in Open Food Facts.'},
            status=status.HTTP_404_NOT_FOUND
        )


class BatchViewSet(TenantFilteredModelViewSet):
    queryset = Batch.objects.select_related('product', 'location', 'organization').all()
    serializer_class = BatchSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'product', 'location', 'expiry_date']
    search_fields = ['batch_code', 'product__name']
    ordering_fields = ['expiry_date', 'received_date', 'quantity']

    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Fetch active batches expiring in the next N days (default 7 days)."""
        days = int(request.query_params.get('days', 7))
        cutoff = date.today() + timedelta(days=days)
        batches = self.get_queryset().filter(
            status=Batch.Status.ACTIVE,
            expiry_date__lte=cutoff
        ).order_by('expiry_date')
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='deduct')
    def deduct(self, request):
        """
        FEFO Stock Deduction endpoint (First-Expired, First-Out).
        Accepts JWT or Api-Key authentication.
        Deducts from ACTIVE, non-expired batches using row-level locking.
        Resolves product by exactly one of: product (id), barcode, or sku.
        Supports idempotency via external_id.
        """
        org = self._get_tenant_org()
        if not org:
            return Response({'error': 'Organization context not found.'}, status=status.HTTP_401_UNAUTHORIZED)

        product_val = request.data.get('product')
        barcode_val = request.data.get('barcode')
        sku_val = request.data.get('sku')
        quantity_val = request.data.get('quantity')
        reason = request.data.get('reason', '')
        txn_type = (request.data.get('txn_type') or 'SOLD').strip().upper()
        external_id = str(request.data.get('external_id') or '').strip()

        if len(external_id) > 100:
            return Response({'error': 'external_id must be 100 characters or fewer.'}, status=status.HTTP_400_BAD_REQUEST)

        if txn_type not in ['SOLD', 'DISCARDED', 'WASTED']:
            return Response(
                {'error': "Invalid txn_type. Must be 'SOLD' or 'DISCARDED'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            req_qty = Decimal(str(quantity_val))
            if req_qty <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return Response({'error': 'Quantity must be a positive number.'}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve product within caller's organization
        product, err_data, err_status = resolve_product(
            organization=org,
            product=product_val,
            barcode=barcode_val,
            sku=sku_val
        )
        if err_data:
            return Response(err_data, status=err_status)

        is_pos = isinstance(request.user, POSApiKeyUser) or (hasattr(request, 'auth') and hasattr(request.auth, 'org_type'))
        source = "POS" if is_pos else "MANUAL"
        user = request.user if (request.user and request.user.is_authenticated and not getattr(request.user, 'is_anonymous', False) and hasattr(request.user, 'pk') and request.user.pk) else None

        def _build_replay_response(txns):
            tot = sum(t.quantity for t in txns)
            tot_str = str(tot).rstrip('0').rstrip('.') if '.' in str(tot) else str(tot)
            return {
                'message': 'Stock deducted successfully.',
                'product_id': txns[0].batch.product_id,
                'total_deducted': tot_str,
                'deductions': [
                    {
                        'batch_id': t.batch.id,
                        'batch_code': t.batch.batch_code,
                        'deducted_quantity': str(t.quantity).rstrip('0').rstrip('.') if '.' in str(t.quantity) else str(t.quantity),
                        'remaining_batch_quantity': str(t.batch.quantity).rstrip('0').rstrip('.') if '.' in str(t.batch.quantity) else str(t.batch.quantity),
                        'status': t.batch.status
                    }
                    for t in txns
                ],
                'idempotent_replay': True
            }

        try:
            with transaction.atomic():
                if external_id:
                    acquire_external_id_lock(org.id, external_id)
                    existing_txns = list(
                        StockTransaction.objects.filter(
                            organization=org, external_id=external_id
                        ).select_related('batch').order_by('id')
                    )
                    if existing_txns:
                        return Response(_build_replay_response(existing_txns), status=status.HTTP_200_OK)

                deductions = deduct_product_fefo(
                    organization=org,
                    product=product,
                    quantity=req_qty,
                    txn_type=txn_type,
                    reason=reason,
                    source=source,
                    user=user,
                    external_id=external_id
                )

        except InsufficientStockError as exc:
            return Response({
                'error': str(exc),
                'available_quantity': str(exc.available_quantity),
                'requested_quantity': str(exc.requested_quantity)
            }, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            if external_id:
                existing_txns = list(
                    StockTransaction.objects.filter(
                        organization=org, external_id=external_id
                    ).select_related('batch').order_by('id')
                )
                if existing_txns:
                    return Response(_build_replay_response(existing_txns), status=status.HTTP_200_OK)
            raise

        return Response({
            'message': 'Stock deducted successfully.',
            'product_id': product.id,
            'total_deducted': str(req_qty),
            'deductions': deductions,
            'idempotent_replay': False
        }, status=status.HTTP_200_OK)


class DashboardSummaryView(APIView):
    """
    Dashboard summary metrics scoped to the authenticated organization.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = getattr(request, 'user', None)
        org = None
        if user and user.is_authenticated and hasattr(user, 'organization') and user.organization:
            org = user.organization
        elif hasattr(request, 'auth') and hasattr(request.auth, 'org_type'):
            org = request.auth

        if not org:
            return Response({'error': 'Organization context required.'}, status=status.HTTP_403_FORBIDDEN)

        today = date.today()
        in_48h = today + timedelta(days=2)
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # 1. Total active batches
        total_active_batches = Batch.objects.filter(
            organization=org,
            status=Batch.Status.ACTIVE
        ).count()

        # 2. Total active quantity
        batch_qty_agg = Batch.objects.filter(
            organization=org,
            status=Batch.Status.ACTIVE
        ).aggregate(total_qty=Sum('quantity'))
        total_active_quantity = batch_qty_agg['total_qty'] or Decimal('0.0')

        # 3. Batches expiring within 48 hours
        batches_expiring_48h = Batch.objects.filter(
            organization=org,
            status=Batch.Status.ACTIVE,
            expiry_date__gte=today,
            expiry_date__lte=in_48h
        ).count()

        # 4. Count of unacknowledged CRITICAL alerts
        critical_alerts_unacknowledged = Alert.objects.filter(
            organization=org,
            severity=Alert.Severity.CRITICAL,
            is_acknowledged=False
        ).count()

        # 5. Wasted vs donated value in last 30 days
        cost_expr = Coalesce(F('batch__product__unit_cost'), Value(Decimal('0.0')))
        value_expr = F('quantity') * cost_expr

        recent_txns = StockTransaction.objects.filter(
            organization=org,
            created_at__gte=thirty_days_ago
        )

        txn_stats = recent_txns.aggregate(
            wasted_value=Sum(
                Case(
                    When(Q(txn_type='DISCARDED') | Q(txn_type='WASTED'), then=value_expr),
                    default=Value(Decimal('0.0')),
                    output_field=DecimalField()
                )
            ),
            donated_value=Sum(
                Case(
                    When(txn_type='DONATED', then=value_expr),
                    default=Value(Decimal('0.0')),
                    output_field=DecimalField()
                )
            ),
            missing_cost_items=Count(
                'id',
                filter=(Q(txn_type__in=['DISCARDED', 'WASTED', 'DONATED']) & Q(batch__product__unit_cost__isnull=True))
            )
        )

        wasted_val = txn_stats['wasted_value'] or Decimal('0.0')
        donated_val = txn_stats['donated_value'] or Decimal('0.0')
        missing_cost_items = txn_stats['missing_cost_items'] or 0

        return Response({
            'total_active_batches': total_active_batches,
            'total_active_quantity': str(total_active_quantity),
            'batches_expiring_48h': batches_expiring_48h,
            'critical_alerts_unacknowledged': critical_alerts_unacknowledged,
            'wasted_value_30d': str(wasted_val),
            'donated_value_30d': str(donated_val),
            'missing_cost_items': missing_cost_items,
        }, status=status.HTTP_200_OK)


class StockTransactionViewSet(TenantFilteredModelViewSet):
    queryset = StockTransaction.objects.select_related('batch', 'created_by').all()
    serializer_class = StockTransactionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['txn_type', 'source', 'batch']
    search_fields = ['batch__batch_code', 'reason']
    ordering_fields = ['created_at', 'quantity']

    def perform_create(self, serializer):
        user = self.request.user
        org = self._get_tenant_org()
        created_by_user = user if (user and user.is_authenticated and not getattr(user, 'is_anonymous', False) and hasattr(user, 'pk') and user.pk) else None
        serializer.save(organization=org, created_by=created_by_user)


class AlertRuleViewSet(TenantFilteredModelViewSet):
    queryset = AlertRule.objects.select_related('category', 'organization').all()
    serializer_class = AlertRuleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['is_active', 'category']


class AlertViewSet(TenantFilteredModelViewSet):
    queryset = Alert.objects.select_related('batch', 'rule', 'organization').all()
    serializer_class = AlertSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['severity', 'is_acknowledged', 'batch']
    search_fields = ['message']
    ordering_fields = ['created_at', 'severity']

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Mark an alert as acknowledged by staff."""
        alert = self.get_object()
        alert.is_acknowledged = True
        alert.save(update_fields=['is_acknowledged'])
        return Response({'status': 'alert acknowledged'})


class ImportJobViewSet(TenantFilteredModelViewSet):
    queryset = ImportJob.objects.select_related('organization').all()
    serializer_class = ImportJobSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['created_at']

    def perform_create(self, serializer):
        from .services import process_import_job
        org = self._get_tenant_org()
        import_job = serializer.save(organization=org)
        process_import_job(import_job)


class POSApiKeyViewSet(TenantFilteredModelViewSet):
    queryset = POSApiKey.objects.select_related('organization').all()
    serializer_class = POSApiKeySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']
