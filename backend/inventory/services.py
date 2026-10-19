import csv
import io
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from decimal import Decimal
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from .models import Category, StorageLocation, Product, Batch, StockTransaction, ImportJob, Alert, AlertRule

logger = logging.getLogger(__name__)


class InsufficientStockError(Exception):
    def __init__(self, message, available_quantity=Decimal('0'), requested_quantity=Decimal('0')):
        super().__init__(message)
        self.available_quantity = available_quantity
        self.requested_quantity = requested_quantity


def resolve_product(organization, product=None, barcode=None, sku=None):
    """
    Resolves a product within the caller's organization.
    Accepts exactly one of product (id), barcode, or sku.
    Returns (product, None, 200) on success.
    Returns (None, error_dict, 400) if none or more than one given.
    Returns (None, error_dict, 404) if not found in that organization.
    """
    inputs = {
        'product': product,
        'barcode': barcode,
        'sku': sku,
    }
    provided = {
        k: v for k, v in inputs.items()
        if v is not None and str(v).strip() != ""
    }

    if len(provided) == 0:
        return None, {'error': 'Exactly one of product, barcode, or sku must be provided.'}, 400

    if len(provided) > 1:
        return None, {'error': 'Ambiguous input: provide exactly one of product, barcode, or sku.'}, 400

    key, val = next(iter(provided.items()))

    if key == 'product':
        try:
            prod = Product.objects.filter(id=val, organization=organization).first()
        except (ValueError, TypeError):
            prod = None
    elif key == 'barcode':
        prod = Product.objects.filter(barcode=str(val).strip(), organization=organization).first()
    elif key == 'sku':
        prod = Product.objects.filter(sku=str(val).strip(), organization=organization).first()
    else:
        prod = None

    if not prod:
        return None, {'error': f'Product not found in your organization.'}, 404

    return prod, None, 200


def acquire_external_id_lock(organization_id, external_id: str):
    """
    Acquires a PostgreSQL transaction-scoped advisory lock based on (organization_id, external_id).
    Prevents concurrent deduction requests with the same external_id from executing in parallel.
    No-op on non-PostgreSQL databases (e.g., SQLite).
    """
    if connection.vendor == 'postgresql' and external_id:
        lock_str = f"{organization_id}:{external_id}"
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s));", [lock_str])


def deduct_product_fefo(
    organization,
    product,
    quantity: Decimal,
    txn_type: str = "SOLD",
    reason: str = "",
    source: str = "MANUAL",
    user=None,
    external_id: str = ""
):
    """
    Deducts stock for a product within organization using FEFO (First-Expired, First-Out).
    Batches are locked with select_for_update().
    Must be called inside transaction.atomic().
    Returns list of deduction dictionaries.
    Raises InsufficientStockError if total available stock is insufficient.
    """
    today = date.today()

    batches = list(
        Batch.objects.select_for_update().filter(
            organization=organization,
            product=product,
            status=Batch.Status.ACTIVE,
            expiry_date__gte=today,
            quantity__gt=0
        ).order_by('expiry_date', 'received_date', 'id')
    )

    total_available = sum((b.quantity for b in batches), Decimal('0'))
    if total_available < quantity:
        raise InsufficientStockError(
            'Insufficient available stock for deduction.',
            available_quantity=total_available,
            requested_quantity=quantity,
        )

    remaining_to_deduct = quantity
    deductions = []

    for batch in batches:
        if remaining_to_deduct <= 0:
            break

        take = min(batch.quantity, remaining_to_deduct)
        batch.quantity -= take
        if batch.quantity == 0:
            batch.status = Batch.Status.DEPLETED
        batch.save(update_fields=['quantity', 'status'])

        StockTransaction.objects.create(
            organization=organization,
            batch=batch,
            txn_type=txn_type,
            quantity=take,
            reason=reason,
            source=source,
            created_by=user,
            external_id=external_id or ""
        )

        deductions.append({
            'batch_id': batch.id,
            'batch_code': batch.batch_code,
            'deducted_quantity': str(take),
            'remaining_batch_quantity': str(batch.quantity),
            'status': batch.status
        })

        remaining_to_deduct -= take

    return deductions


def _parse_flexible_date(date_str: str) -> date:
    cleaned = (date_str or '').strip()
    if not cleaned:
        raise ValueError("Missing date")
    # Try ISO YYYY-MM-DD
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        pass
    # Try alternative common ERP/CSV formats
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date format '{cleaned}'. Expected YYYY-MM-DD or DD-MM-YYYY.")


def process_import_job(import_job: ImportJob):
    """
    Parses an uploaded CSV file, creating Products and Batches for the tenant organization.
    Records success and failure rows into import_job.error_report.
    Uses per-row transactions to isolate row errors and prevent cascading aborted transactions.
    Safe to retry:
    - If import_job.status == 'DONE', do nothing.
    - Rows already imported are matched by (organization, product, batch_code) and never duplicated.
    """
    if import_job.status == ImportJob.Status.DONE:
        logger.info("ImportJob #%s is already DONE; skipping.", import_job.id)
        return import_job

    org = import_job.organization
    errors = []
    rows_ok = 0
    rows_failed = 0
    processed_rows = 0

    import_job.status = ImportJob.Status.PROCESSING
    if not import_job.started_at:
        import_job.started_at = timezone.now()
    import_job.save(update_fields=['status', 'started_at'])

    try:
        import_job.file.open('r')
        content = import_job.file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8-sig')

        content = content.replace('\x00', '')
        reader = list(csv.DictReader(io.StringIO(content)))
        total_rows = len(reader)
        if import_job.total_rows != total_rows:
            import_job.total_rows = total_rows
            import_job.save(update_fields=['total_rows'])

        for idx, row in enumerate(reader):
            row_num = idx + 2  # row 1 is header
            try:
                with transaction.atomic():
                    product_name = (row.get('product_name') or row.get('name') or '').strip()
                    if not product_name:
                        raise ValueError("Missing product_name")

                    category_val = (row.get('category') or '').strip()
                    category = None
                    if category_val:
                        category = Category.objects.filter(name__iexact=category_val).first()
                        if not category:
                            category, _ = Category.objects.get_or_create(
                                name=category_val,
                                defaults={'storage_type': Category.Storage.AMBIENT}
                            )
                    if not category:
                        category = Category.objects.first()
                    if not category:
                        category, _ = Category.objects.get_or_create(
                            name='General',
                            defaults={'storage_type': Category.Storage.AMBIENT}
                        )

                    sku = (row.get('sku') or '').strip()
                    barcode = (row.get('barcode') or '').strip()
                    unit = (row.get('unit') or 'kg').strip()

                    unit_cost = None
                    cost_val = row.get('unit_cost') or row.get('cost_price')
                    if cost_val is not None and str(cost_val).strip():
                        try:
                            unit_cost = Decimal(str(cost_val).strip())
                        except Exception:
                            pass

                    reorder_level = Decimal('0')
                    reorder_val = row.get('reorder_level') or row.get('min_stock_level')
                    if reorder_val is not None and str(reorder_val).strip():
                        try:
                            reorder_level = Decimal(str(reorder_val).strip())
                        except Exception:
                            pass

                    # Resolve existing product:
                    # 1. Match by SKU within organization
                    # 2. Match by Barcode within organization
                    # 3. Match by Name within organization
                    product = None
                    if sku:
                        product = Product.objects.filter(organization=org, sku=sku).first()
                    if not product and barcode:
                        product = Product.objects.filter(organization=org, barcode=barcode).first()
                    if not product:
                        product = Product.objects.filter(organization=org, name__iexact=product_name).first()

                    if not product:
                        product = Product.objects.create(
                            organization=org,
                            name=product_name,
                            sku=sku,
                            barcode=barcode,
                            category=category,
                            unit=unit,
                            unit_cost=unit_cost,
                            reorder_level=reorder_level,
                            is_active=True,
                        )
                    else:
                        # Update any missing metadata on existing product
                        fields_to_update = []
                        if not product.category and category:
                            product.category = category
                            fields_to_update.append('category')
                        if not product.barcode and barcode:
                            product.barcode = barcode
                            fields_to_update.append('barcode')
                        if not product.unit_cost and unit_cost:
                            product.unit_cost = unit_cost
                            fields_to_update.append('unit_cost')
                        if fields_to_update:
                            product.save(update_fields=fields_to_update)

                    # Batch creation
                    quantity_str = row.get('quantity')
                    if not quantity_str:
                        raise ValueError("Missing quantity")
                    quantity = Decimal(str(quantity_str).strip())

                    expiry_str = (row.get('expiry_date') or '').strip()
                    if not expiry_str:
                        raise ValueError("Missing expiry_date")
                    expiry_date = _parse_flexible_date(expiry_str)

                    received_str = (row.get('received_date') or row.get('manufacturing_date') or '').strip()
                    if received_str:
                        try:
                            received_date = _parse_flexible_date(received_str)
                        except Exception:
                            received_date = date.today()
                    else:
                        received_date = date.today()

                    batch_code = (row.get('batch_code') or '').strip()
                    if not batch_code:
                        batch_code = f"BTH-{expiry_date.strftime('%y%m%d')}-{row_num:03d}"

                    # Idempotency / retry duplicate check:
                    # Match by (organization, product, batch_code)
                    existing_batch = Batch.objects.filter(
                        organization=org,
                        product=product,
                        batch_code=batch_code,
                    ).first()

                    if existing_batch:
                        # Row already imported previously: do not create duplicate Batch or StockTransaction
                        rows_ok += 1
                    else:
                        # Location lookup if provided
                        loc_name = (row.get('storage_location') or '').strip()
                        location = None
                        if loc_name:
                            location = StorageLocation.objects.filter(organization=org, name__iexact=loc_name).first()

                        batch = Batch.objects.create(
                            organization=org,
                            product=product,
                            location=location,
                            batch_code=batch_code,
                            quantity=quantity,
                            received_date=received_date,
                            expiry_date=expiry_date,
                            status=Batch.Status.ACTIVE,
                        )

                        # Record transaction ledger entry
                        StockTransaction.objects.create(
                            organization=org,
                            batch=batch,
                            txn_type=StockTransaction.Type.RECEIVED,
                            quantity=quantity,
                            reason="CSV Bulk Import",
                            source="CSV",
                        )

                        rows_ok += 1

            except Exception as row_err:
                rows_failed += 1
                errors.append({
                    'row': row_num,
                    'data': row,
                    'error': str(row_err),
                })
            finally:
                processed_rows += 1
                if processed_rows % 25 == 0:
                    import_job.processed_rows = processed_rows
                    import_job.rows_ok = rows_ok
                    import_job.rows_failed = rows_failed
                    import_job.save(update_fields=['processed_rows', 'rows_ok', 'rows_failed'])

        import_job.status = (
            ImportJob.Status.DONE if rows_failed == 0
            else (ImportJob.Status.FAILED if rows_ok == 0 else ImportJob.Status.PARTIAL)
        )
        import_job.processed_rows = processed_rows
        import_job.rows_ok = rows_ok
        import_job.rows_failed = rows_failed
        import_job.error_report = errors
        import_job.finished_at = timezone.now()
        import_job.save()

        # Automatically evaluate expiry alerts for imported stock
        try:
            evaluate_expiry_alerts(organization=org)
        except Exception as alert_err:
            logger.warning("Could not auto-evaluate expiry alerts after CSV import: %s", alert_err)

    except Exception as fatal_err:
        import_job.status = ImportJob.Status.FAILED
        import_job.error_message = str(fatal_err)
        import_job.error_report = [{'fatal': str(fatal_err)}]
        import_job.finished_at = timezone.now()
        import_job.save()

    return import_job


def evaluate_expiry_alerts(organization=None, default_days: int = 6) -> dict:
    """
    Evaluates expiry dates for batches and generates or escalates alerts strictly for
    active batches that are less than 7 days from expiry (0 <= days_left < 7).
    - If days_left < 0: marks active batches as EXPIRED and deletes/cleans up any alerts,
      ensuring expired batches are never included in the alert section.
    - If 0 <= days_left < 7 (and <= threshold): creates or escalates an alert with:
        * CRITICAL (<= 2 days)
        * WARNING (3 to 4 days)
        * INFO (5 to 6 days)
    - If days_left >= 7: no alert is created, and any stale unacknowledged upcoming alerts
      for batches >= 7 days are cleaned up.
    Returns: {'alerts_created': int, 'alerts_updated': int, 'batches_expired': int}
    """
    today = date.today()

    # Lookahead horizon is strictly less than 7 days (< 7 days)
    MAX_LOOKAHEAD_DAYS = 6  # today + 6 days has days_left = 6 (< 7 days)
    cutoff_date = today + timedelta(days=MAX_LOOKAHEAD_DAYS)

    # Clean up any alerts for batches that are expired or expire in 7 or more days
    cleanup_qs = Alert.objects.filter(
        Q(batch__status=Batch.Status.EXPIRED) |
        Q(batch__expiry_date__lt=today) |
        Q(batch__expiry_date__gt=cutoff_date) |
        ~Q(batch__status=Batch.Status.ACTIVE)
    )
    if organization is not None:
        cleanup_qs = cleanup_qs.filter(organization=organization)
    cleanup_qs.delete()

    batches_qs = Batch.objects.filter(
        status__in=[Batch.Status.ACTIVE, Batch.Status.EXPIRED],
        expiry_date__lte=cutoff_date
    ).select_related('product', 'product__category', 'organization')

    if organization is not None:
        batches_qs = batches_qs.filter(organization=organization)

    # 1. Prefetch active unacknowledged alerts to avoid N+1 queries
    alerts_qs = Alert.objects.filter(is_acknowledged=False)
    if organization is not None:
        alerts_qs = alerts_qs.filter(organization=organization)
    existing_alerts = {a.batch_id: a for a in alerts_qs}

    # 2. Prefetch rules mapped by (organization_id, category_id)
    rules_qs = AlertRule.objects.filter(is_active=True)
    if organization is not None:
        rules_qs = rules_qs.filter(organization=organization)
    rules_by_org = {}
    for r in rules_qs:
        rules_by_org.setdefault(r.organization_id, []).append(r)

    severity_rank = {
        Alert.Severity.INFO: 1,
        Alert.Severity.WARNING: 2,
        Alert.Severity.CRITICAL: 3,
    }

    alerts_to_create = []
    alerts_to_update = []
    alerts_to_delete_ids = []
    batches_to_expire_ids = []
    batches_list = list(batches_qs)

    for batch in batches_list:
        days_left = (batch.expiry_date - today).days

        # 1. Past expiry: mark batch as EXPIRED and ensure no alert exists in the alert section
        if days_left < 0 or batch.status == Batch.Status.EXPIRED:
            if batch.status != Batch.Status.EXPIRED:
                batches_to_expire_ids.append(batch.id)

            existing_alert = existing_alerts.get(batch.id)
            if existing_alert and existing_alert.id:
                alerts_to_delete_ids.append(existing_alert.id)
            continue

        # If batch is already depleted or donated, do not alert as upcoming
        if batch.status != Batch.Status.ACTIVE:
            existing_alert = existing_alerts.get(batch.id)
            if existing_alert and existing_alert.id:
                alerts_to_delete_ids.append(existing_alert.id)
            continue

        # Strictly less than 7 days
        if days_left >= 7:
            continue

        # 2. Check rules (capped at MAX_LOOKAHEAD_DAYS)
        org_rules = rules_by_org.get(batch.organization_id, [])
        cat_id = batch.product.category_id
        matched_rule = next((r for r in org_rules if r.category_id == cat_id), None)
        if not matched_rule:
            matched_rule = next((r for r in org_rules if r.category_id is None), None)

        threshold_days = min(matched_rule.days_before_expiry, MAX_LOOKAHEAD_DAYS) if matched_rule else MAX_LOOKAHEAD_DAYS

        if days_left <= threshold_days:
            if days_left <= 2:
                severity = Alert.Severity.CRITICAL
            elif days_left <= 4:
                severity = Alert.Severity.WARNING
            else:
                severity = Alert.Severity.INFO

            msg = (
                f"Batch {batch.batch_code or batch.id} ({batch.product.name}) expires in {days_left} day(s) "
                f"on {batch.expiry_date}."
            )

            existing_alert = existing_alerts.get(batch.id)
            if not existing_alert:
                new_alert = Alert(
                    organization=batch.organization,
                    batch=batch,
                    rule=matched_rule,
                    severity=severity,
                    message=msg,
                    is_acknowledged=False,
                )
                alerts_to_create.append(new_alert)
                existing_alerts[batch.id] = new_alert
            else:
                old_rank = severity_rank.get(existing_alert.severity, 0)
                new_rank = severity_rank.get(severity, 0)
                changed = False
                if new_rank > old_rank:
                    existing_alert.severity = severity
                    changed = True
                if existing_alert.message != msg:
                    existing_alert.message = msg
                    changed = True
                if matched_rule and not existing_alert.rule_id:
                    existing_alert.rule = matched_rule
                    changed = True
                if changed:
                    alerts_to_update.append(existing_alert)

    # Execute bulk operations
    if batches_to_expire_ids:
        Batch.objects.filter(id__in=batches_to_expire_ids).update(status=Batch.Status.EXPIRED)
        Alert.objects.filter(batch_id__in=batches_to_expire_ids).delete()

    if alerts_to_delete_ids:
        Alert.objects.filter(id__in=alerts_to_delete_ids).delete()

    if alerts_to_create:
        Alert.objects.bulk_create(alerts_to_create, batch_size=1000)

    if alerts_to_update:
        Alert.objects.bulk_update(alerts_to_update, ['severity', 'message', 'rule'], batch_size=1000)

    return {
        'batches_checked': len(batches_list),
        'alerts_created': len(alerts_to_create),
        'alerts_updated': len(alerts_to_update),
        'batches_expired': len(batches_to_expire_ids),
    }



def fetch_open_food_facts(barcode: str):
    """
    Fetches product information from Open Food Facts API for a given barcode.
    Returns a dict with product information or None if not found/error.
    """
    cleaned_barcode = str(barcode).strip()
    if not cleaned_barcode:
        return None

    url = f"https://world.openfoodfacts.org/api/v0/product/{urllib.parse.quote(cleaned_barcode)}.json"
    headers = {
        "User-Agent": "SurplusSync/1.0 (dev@surplussync.local)"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if data.get('status') == 1 and 'product' in data:
                    prod = data['product']
                    product_name = (
                        prod.get('product_name')
                        or prod.get('product_name_en')
                        or prod.get('generic_name')
                        or 'Unknown Product'
                    ).strip()
                    brands = prod.get('brands', '').strip()
                    image_url = prod.get('image_url') or prod.get('image_front_url')
                    categories_str = prod.get('categories', '')

                    category_suggestion = None
                    if categories_str:
                        cats_lower = categories_str.lower()
                        keyword_rules = [
                            ("Dairy", ["dairy", "dairies", "milk", "cheese", "yogurt", "butter", "paneer", "curd", "cream", "fromage", "lait"]),
                            ("Produce & Fresh Greens", ["produce", "fruit", "vegetable", "greens", "salad", "fresh"]),
                            ("Bakery", ["bakery", "bread", "cake", "pastry", "cookie", "biscuit", "toast", "bun"]),
                            ("Meat & Poultry", ["meat", "poultry", "chicken", "beef", "pork", "fish", "seafood"]),
                            ("Prepared & Cooked Meals", ["prepared", "meal", "cooked", "sandwich", "ready-to-eat", "deli"]),
                            ("Frozen Foods", ["frozen", "ice cream", "sorbet"]),
                            ("Dry Goods & Grains", ["grain", "dry", "cereal", "flour", "rice", "pasta", "noodles", "snack", "chips", "cracker"]),
                            ("Canned Goods", ["canned", "tin", "preserve"]),
                            ("Beverages", ["beverage", "drink", "juice", "soda", "tea", "coffee", "water"]),
                        ]
                        for cat in Category.objects.all():
                            if cat.name.lower() in cats_lower:
                                category_suggestion = {
                                    "id": cat.id,
                                    "name": cat.name,
                                    "default_shelf_life_days": cat.default_shelf_life_days,
                                }
                                break
                        if not category_suggestion:
                            for target_name, keywords in keyword_rules:
                                if any(kw in cats_lower for kw in keywords):
                                    matched_cat = Category.objects.filter(name__iexact=target_name).first()
                                    if matched_cat:
                                        category_suggestion = {
                                            "id": matched_cat.id,
                                            "name": matched_cat.name,
                                            "default_shelf_life_days": matched_cat.default_shelf_life_days,
                                        }
                                        break

                    return {
                        "source": "open_food_facts",
                        "barcode": cleaned_barcode,
                        "name": product_name,
                        "brand": brands,
                        "image_url": image_url,
                        "categories_text": categories_str,
                        "suggested_category": category_suggestion,
                    }
    except Exception:
        pass

    return None


_fatsecret_cached_token = None
_fatsecret_token_expiry = 0


def get_fatsecret_token():
    """
    Obtains or reuses an OAuth 2.0 Client Credentials token from FatSecret.
    Tokens are valid for 24h (86400s), cached in-memory with a safe renewal buffer.
    """
    global _fatsecret_cached_token, _fatsecret_token_expiry
    now = time.time()
    if _fatsecret_cached_token and now < (_fatsecret_token_expiry - 300):
        return _fatsecret_cached_token

    client_id = os.getenv('FATSECRET_CLIENT_ID', '').strip()
    client_secret = os.getenv('FATSECRET_CLIENT_SECRET', '').strip()
    if not client_id or not client_secret:
        return None

    try:
        import base64
        token_url = "https://oauth.fatsecret.com/connect/token"
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
        creds = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        headers = {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "SurplusSync/1.0"
        }
        req = urllib.request.Request(token_url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as response:
            if response.status == 200:
                body = json.loads(response.read().decode("utf-8"))
                _fatsecret_cached_token = body.get("access_token")
                expires_in = body.get("expires_in", 86400)
                _fatsecret_token_expiry = now + expires_in
                return _fatsecret_cached_token
    except Exception as exc:
        logger.warning("FatSecret OAuth token request error: %s", exc)

    return None


def fetch_fatsecret_food(barcode: str):
    """
    Looks up a food item by barcode using the FatSecret Platform API.
    Returns product dictionary or None if not found or on error (e.g. IP whitelist pending).
    """
    cleaned_barcode = str(barcode).strip()
    if not cleaned_barcode:
        return None

    token = get_fatsecret_token()
    if not token:
        return None

    api_url = "https://platform.fatsecret.com/rest/server.api"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "SurplusSync/1.0"
    }

    try:
        # Step 1: Find food ID for barcode
        params = urllib.parse.urlencode({
            "method": "food.find_id_for_barcode",
            "barcode": cleaned_barcode,
            "format": "json"
        })
        req = urllib.request.Request(f"{api_url}?{params}", headers=headers)
        with urllib.request.urlopen(req, timeout=6) as response:
            if response.status != 200:
                return None
            res_json = json.loads(response.read().decode("utf-8"))

        if "error" in res_json:
            logger.info("FatSecret API note: %s", res_json["error"].get("message"))
            return None

        food_id = res_json.get("food_id", {}).get("value")
        if not food_id or food_id == "0":
            return None

        # Step 2: Retrieve full food details
        detail_params = urllib.parse.urlencode({
            "method": "food.get.v2",
            "food_id": food_id,
            "format": "json"
        })
        detail_req = urllib.request.Request(f"{api_url}?{detail_params}", headers=headers)
        with urllib.request.urlopen(detail_req, timeout=6) as detail_response:
            if detail_response.status != 200:
                return None
            detail_json = json.loads(detail_response.read().decode("utf-8"))

        food_obj = detail_json.get("food", {})
        food_name = (food_obj.get("food_name") or "").strip()
        brand_name = (food_obj.get("brand_name") or "").strip()

        # Parse servings and nutritional info if present
        servings_data = food_obj.get("servings", {}).get("serving", [])
        if isinstance(servings_data, dict):
            primary_serving = servings_data
        elif isinstance(servings_data, list) and servings_data:
            primary_serving = servings_data[0]
        else:
            primary_serving = {}

        # Suggest category match
        category_suggestion = None
        for cat in Category.objects.all():
            cat_name = cat.name.lower()
            if cat_name in food_name.lower() or (brand_name and cat_name in brand_name.lower()):
                category_suggestion = {
                    "id": cat.id,
                    "name": cat.name
                }
                break

        return {
            "source": "fatsecret",
            "barcode": cleaned_barcode,
            "name": food_name or "FatSecret Food Item",
            "brand": brand_name,
            "calories": primary_serving.get("calories"),
            "protein": primary_serving.get("protein"),
            "carbohydrate": primary_serving.get("carbohydrate"),
            "fat": primary_serving.get("fat"),
            "serving_description": primary_serving.get("serving_description"),
            "suggested_category": category_suggestion,
        }
    except Exception as exc:
        logger.warning("FatSecret lookup error for barcode %s: %s", barcode, exc)

    return None
