import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from django.conf import settings
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
from django_q.tasks import async_task

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
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_active', 'barcode', 'sku']
    search_fields = ['name', 'sku', 'barcode']
    ordering_fields = ['name', 'unit_cost', 'reorder_level']

    def _get_tenant_org(self):
        org = super()._get_tenant_org()
        if not org:
            from accounts.models import Organization
            return Organization.objects.first()
        return org

    @action(detail=False, methods=['get'], url_path='barcode/(?P<barcode_val>[^/.]+)')
    def lookup_barcode(self, request, barcode_val=None):
        """
        Quick barcode lookup for mobile/scanner inputs.
        Checks local organization product catalog first.
        Falls back to Open Food Facts API if not found locally.
        """
        products = Product.objects.filter(barcode=barcode_val)
        if products.exists():
            prod = products.first()
            data = self.get_serializer(prod).data
            data['source'] = 'local'
            batch = Batch.objects.filter(product=prod, status=Batch.Status.ACTIVE).first()
            if batch:
                data['batch_code'] = batch.batch_code
                data['current_stock'] = float(batch.quantity)
                data['expiry_date'] = str(batch.expiry_date)
            return Response(data, status=status.HTTP_200_OK)

        # 2. FatSecret API lookup
        from .services import fetch_fatsecret_food, fetch_open_food_facts
        fatsecret_data = fetch_fatsecret_food(barcode_val)
        if fatsecret_data:
            return Response(fatsecret_data, status=status.HTTP_200_OK)

        # 3. Fallback to Open Food Facts
        off_data = fetch_open_food_facts(barcode_val)
        if off_data:
            return Response(off_data, status=status.HTTP_200_OK)

        return Response(
            {'detail': f'Product with barcode {barcode_val} not found locally or in Open Food Facts.'},
            status=status.HTTP_404_NOT_FOUND
        )


class BatchViewSet(TenantFilteredModelViewSet):
    queryset = Batch.objects.select_related('product', 'product__category', 'location', 'organization').all()
    serializer_class = BatchSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'product', 'location', 'expiry_date']
    search_fields = ['batch_code', 'product__name', 'product__sku']
    ordering_fields = ['expiry_date', 'received_date', 'quantity', 'created_at', 'id']
    ordering = ['-created_at', '-id']

    def perform_create(self, serializer):
        super().perform_create(serializer)
        org = self._get_tenant_org()
        if org:
            from .services import evaluate_expiry_alerts
            evaluate_expiry_alerts(organization=org)


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
            is_acknowledged=False,
            batch__status=Batch.Status.ACTIVE,
            batch__expiry_date__gte=today,
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
    queryset = Alert.objects.select_related('batch', 'batch__product', 'rule', 'organization').all()
    serializer_class = AlertSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['severity', 'is_acknowledged', 'batch']
    search_fields = ['message', 'batch__product__name', 'batch__batch_code']
    ordering_fields = ['created_at', 'severity', 'batch__expiry_date', 'batch__status']
    ordering = ['is_acknowledged', 'batch__status', 'batch__expiry_date', '-id']

    def get_queryset(self):
        org = self._get_tenant_org()
        from .services import evaluate_expiry_alerts
        if org:
            evaluate_expiry_alerts(organization=org)
        elif getattr(self.request.user, 'is_superuser', False):
            evaluate_expiry_alerts(organization=None)
        today = date.today()
        return super().get_queryset().filter(
            batch__status=Batch.Status.ACTIVE,
            batch__expiry_date__gte=today,
        )

    @action(detail=False, methods=['post'], url_path='evaluate')
    def evaluate(self, request):
        """Force evaluation of expiry alerts for caller's organization."""
        org = self._get_tenant_org()
        from .services import evaluate_expiry_alerts
        res = evaluate_expiry_alerts(organization=org)
        return Response(res, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='bulk-acknowledge')
    def bulk_acknowledge(self, request):
        """Acknowledge multiple alerts at once."""
        ids = request.data.get('ids', [])
        if not isinstance(ids, list):
            return Response({'error': 'ids must be a list of alert IDs.'}, status=status.HTTP_400_BAD_REQUEST)
        qs = self.get_queryset().filter(id__in=ids, is_acknowledged=False)
        count = qs.update(is_acknowledged=True)
        return Response({'success': True, 'count': count}, status=status.HTTP_200_OK)

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
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['created_at']

    def _get_tenant_org(self):
        user = getattr(self.request, 'user', None)
        if user and user.is_authenticated and hasattr(user, 'organization') and user.organization:
            return user.organization
        auth = getattr(self.request, 'auth', None)
        if auth and hasattr(auth, 'org_type'):
            return auth
        if user and user.is_authenticated:
            return None
        from accounts.models import Organization
        return Organization.objects.first()

    def create(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response(
                {"error": "No file uploaded. Please provide a CSV file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Size limit: 2 MB (2 * 1024 * 1024 bytes)
        MAX_SIZE = 2 * 1024 * 1024
        if file_obj.size > MAX_SIZE:
            return Response(
                {"error": "File size exceeds the 2 MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. File type validation (filename must end with .csv)
        file_name = getattr(file_obj, 'name', '') or ''
        if not file_name.lower().endswith('.csv'):
            return Response(
                {"error": "Invalid file type. Only CSV files (.csv) are accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Read content & check not empty
        try:
            raw_content = file_obj.read()
            file_obj.seek(0)
            if not raw_content or not raw_content.strip():
                return Response(
                    {"error": "Uploaded CSV file is empty."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                decoded_content = raw_content.decode('utf-8-sig')
            except UnicodeDecodeError:
                decoded_content = raw_content.decode('latin-1')
        except Exception as e:
            return Response(
                {"error": f"Could not read CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cleaned_content = decoded_content.replace('\x00', '')
        stream = io.StringIO(cleaned_content)
        reader = csv.DictReader(stream)

        # 4. Check required headers
        fieldnames = [f.strip().lower() for f in (reader.fieldnames or []) if f]
        has_product = ('product_name' in fieldnames) or ('name' in fieldnames)
        has_quantity = 'quantity' in fieldnames
        has_expiry = 'expiry_date' in fieldnames

        if not (has_product and has_quantity and has_expiry):
            missing = []
            if not has_product:
                missing.append("product_name (or name)")
            if not has_quantity:
                missing.append("quantity")
            if not has_expiry:
                missing.append("expiry_date")
            return Response(
                {"error": f"CSV is missing required headers: {', '.join(missing)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Check not header-only (must contain at least 1 data row)
        data_rows = list(reader)
        total_rows = len(data_rows)
        if total_rows == 0:
            return Response(
                {"error": "CSV contains headers only and no data rows."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        org = self._get_tenant_org()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        import_job = serializer.save(
            organization=org,
            total_rows=total_rows,
            status=ImportJob.Status.PENDING,
        )

        sync_limit = getattr(settings, 'IMPORT_SYNC_ROW_LIMIT', 50)

        if total_rows <= sync_limit:
            # Small file: process immediately in request and return 201
            from .services import process_import_job as service_process
            service_process(import_job)
            import_job.refresh_from_db()
            response_serializer = self.get_serializer(import_job)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        else:
            # Large file: enqueue background task and return 202
            async_task('inventory.tasks.process_import_job', import_job.id)
            response_serializer = self.get_serializer(import_job)
            return Response(response_serializer.data, status=status.HTTP_202_ACCEPTED)


class POSApiKeyViewSet(TenantFilteredModelViewSet):
    queryset = POSApiKey.objects.select_related('organization').all()
    serializer_class = POSApiKeySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']

    def _get_tenant_org(self):
        org = super()._get_tenant_org()
        if not org:
            from accounts.models import Organization
            return Organization.objects.first()
        return org

    def perform_create(self, serializer):
        import secrets, hashlib
        org = self._get_tenant_org()
        raw_key = secrets.token_hex(16)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        instance = serializer.save(organization=org, key_hash=key_hash)
        instance._raw_key = f"sps_live_{raw_key}"

    @action(detail=True, methods=['post'])
    def rotate(self, request, pk=None):
        import secrets, hashlib
        key_obj = self.get_object()
        raw_key = secrets.token_hex(16)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_obj.key_hash = key_hash
        key_obj.save(update_fields=['key_hash'])
        new_token = f"sps_live_{raw_key}"
        return Response({
            'status': 'key rotated',
            'raw_key': new_token,
            'key_prefix': f"sps_live_{raw_key[:2]}...{raw_key[-4:]}"
        })
