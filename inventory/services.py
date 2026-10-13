import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import date
from decimal import Decimal
from django.db import transaction
from .models import Category, StorageLocation, Product, Batch, StockTransaction, ImportJob


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
