import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import date
from decimal import Decimal
from django.db import connection, transaction
from .models import Category, StorageLocation, Product, Batch, StockTransaction, ImportJob


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


def process_import_job(import_job: ImportJob):
    """
    Parses an uploaded CSV file, creating Products and Batches for the tenant organization.
    Records success and failure rows into import_job.error_report.
    """
    org = import_job.organization
    errors = []
    rows_ok = 0
    rows_failed = 0

    try:
        import_job.file.open('r')
        content = import_job.file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8-sig')
        
        reader = csv.DictReader(io.StringIO(content))
        
        with transaction.atomic():
            for row_num, row in enumerate(reader, start=2):  # row 1 is header
                try:
                    product_name = (row.get('product_name') or row.get('name') or '').strip()
                    if not product_name:
                        raise ValueError("Missing product_name")

                    category_val = (row.get('category') or '').strip()
                    category = None
                    if category_val:
                        category = Category.objects.filter(name__iexact=category_val).first()
                    if not category:
                        category = Category.objects.first()  # fallback

                    sku = (row.get('sku') or '').strip()
                    barcode = (row.get('barcode') or '').strip()
                    unit = (row.get('unit') or 'kg').strip()
                    
                    unit_cost = None
                    if row.get('unit_cost'):
                        unit_cost = Decimal(str(row['unit_cost']).strip())

                    reorder_level = Decimal('0')
                    if row.get('reorder_level'):
                        reorder_level = Decimal(str(row['reorder_level']).strip())

                    # Product lookup or creation within organization
                    product, _ = Product.objects.get_or_create(
                        organization=org,
                        name=product_name,
                        defaults={
                            'sku': sku,
                            'barcode': barcode,
                            'category': category,
                            'unit': unit,
                            'unit_cost': unit_cost,
                            'reorder_level': reorder_level,
                            'is_active': True,
                        }
                    )

                    # Batch creation
                    quantity_str = row.get('quantity')
                    if not quantity_str:
                        raise ValueError("Missing quantity")
                    quantity = Decimal(str(quantity_str).strip())

                    expiry_str = (row.get('expiry_date') or '').strip()
                    if not expiry_str:
                        raise ValueError("Missing expiry_date (YYYY-MM-DD)")
                    expiry_date = date.fromisoformat(expiry_str)

                    received_str = (row.get('received_date') or '').strip()
                    received_date = date.fromisoformat(received_str) if received_str else date.today()

                    batch_code = (row.get('batch_code') or '').strip()

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

        import_job.status = 'DONE' if rows_failed == 0 else ('FAILED' if rows_ok == 0 else 'PARTIAL')
        import_job.rows_ok = rows_ok
        import_job.rows_failed = rows_failed
        import_job.error_report = errors
        import_job.save()

    except Exception as fatal_err:
        import_job.status = 'FAILED'
        import_job.error_report = [{'fatal': str(fatal_err)}]
        import_job.save()

    return import_job


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
                        for cat in Category.objects.all():
                            if cat.name.lower() in categories_str.lower():
                                category_suggestion = {
                                    "id": cat.id,
                                    "name": cat.name
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
