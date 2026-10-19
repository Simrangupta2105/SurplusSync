import os
import django
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SURPLUSSYNC.settings')
django.setup()

from django.utils import timezone
from accounts.models import User, Organization
from inventory.models import Category, StorageLocation, Product, Batch, Alert, AlertRule

def seed():
    print("Seeding SurplusSync database...")
    
    # 1. Organization
    org, created = Organization.objects.get_or_create(
        name="The Grand Kitchens",
        defaults={
            "org_type": Organization.Type.BUSINESS,
            "address": "Taj Vivanta, MG Road, Bengaluru, Karnataka 560001",
            "phone": "+91 80 6660 4444",
            "is_verified": True,
        }
    )
    print(f"Organization: {org.name} (id={org.id})")

    # 2. Users
    admin_user = User.objects.filter(username="admin").first()
    if admin_user:
        admin_user.organization = org
        admin_user.role = User.Role.OWNER
        admin_user.email = "admin@surplussync.com"
        admin_user.save()
        print(f"Linked existing admin to {org.name}")
    else:
        admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@surplussync.com",
            password="adminpassword123",
            organization=org,
            role=User.Role.OWNER,
        )
        print("Created admin superuser")

    priya, created = User.objects.get_or_create(
        username="priya",
        defaults={
            "email": "priya.sharma@thegrandkitchens.in",
            "organization": org,
            "role": User.Role.STAFF,
            "first_name": "Priya",
            "last_name": "Sharma",
        }
    )
    if created:
        priya.set_password("priyapassword123")
        priya.save()
        print("Created user Priya Sharma")

    # 3. Categories
    categories_data = [
        ("Cooked Meals", Category.Risk.CRITICAL, Category.Storage.AMBIENT, 1),
        ("Fresh Produce", Category.Risk.MEDIUM, Category.Storage.CHILLED, 3),
        ("Bakery & Sweets", Category.Risk.LOW, Category.Storage.AMBIENT, 2),
        ("Dairy & Chilled", Category.Risk.HIGH, Category.Storage.CHILLED, 2),
    ]
    categories = {}
    for name, risk, stype, shelf_life in categories_data:
        cat, _ = Category.objects.get_or_create(
            name=name,
            defaults={
                "perishability_risk": risk,
                "storage_type": stype,
                "default_shelf_life_days": shelf_life,
            }
        )
        categories[name] = cat
        print(f"Category: {cat.name}")

    # 4. Storage Locations
    loc_data = [
        ("Kitchen #2 Banquets", Category.Storage.AMBIENT, Decimal("500.00")),
        ("Cold Pantry", Category.Storage.CHILLED, Decimal("200.00")),
        ("Bakery Station", Category.Storage.AMBIENT, Decimal("150.00")),
        ("Walk-in Chiller", Category.Storage.CHILLED, Decimal("800.00")),
    ]
    locations = {}
    for name, stype, cap in loc_data:
        loc, _ = StorageLocation.objects.get_or_create(
            organization=org,
            name=name,
            defaults={"storage_type": stype, "capacity": cap}
        )
        locations[name] = loc
        print(f"Location: {loc.name}")

    # 5. Products & Batches
    today = timezone.localdate()

    products_data = [
        {
            "name": "Hyderabadi Dum Biryani & Mirchi Salan",
            "sku": "SKU-HYD-8821",
            "barcode": "8901234568821",
            "category_name": "Cooked Meals",
            "unit": "kg",
            "unit_cost": Decimal("120.00"),
            "reorder_level": Decimal("20.00"),
            "location_name": "Kitchen #2 Banquets",
            "qty": Decimal("60.000"),
            "expiry_days": 0,
            "status": Batch.Status.ACTIVE,
            "batch_code": "SKU-HYD-8821",
        },
        {
            "name": "Assorted Continental Salads & Cut Greens",
            "sku": "SKU-SAL-4109",
            "barcode": "8901234564109",
            "category_name": "Fresh Produce",
            "unit": "kg",
            "unit_cost": Decimal("85.00"),
            "reorder_level": Decimal("15.00"),
            "location_name": "Cold Pantry",
            "qty": Decimal("22.000"),
            "expiry_days": 0,
            "status": Batch.Status.ACTIVE,
            "batch_code": "SKU-SAL-4109",
        },
        {
            "name": "Sourdough Loaves & Danish Pastries",
            "sku": "SKU-BKR-1044",
            "barcode": "8901234561044",
            "category_name": "Bakery & Sweets",
            "unit": "kg",
            "unit_cost": Decimal("65.00"),
            "reorder_level": Decimal("10.00"),
            "location_name": "Bakery Station",
            "qty": Decimal("18.000"),
            "expiry_days": 1,
            "status": Batch.Status.ACTIVE,
            "batch_code": "SKU-BKR-1044",
        },
        {
            "name": "Fresh Pasteurised Toned Milk",
            "sku": "SKU-MLK-9902",
            "barcode": "8901234569902",
            "category_name": "Dairy & Chilled",
            "unit": "L",
            "unit_cost": Decimal("40.00"),
            "reorder_level": Decimal("25.00"),
            "location_name": "Walk-in Chiller",
            "qty": Decimal("50.000"),
            "expiry_days": 0,
            "status": Batch.Status.ACTIVE,
            "batch_code": "SKU-MLK-9902",
        },
    ]

    for item in products_data:
        cat = categories[item["category_name"]]
        prod, _ = Product.objects.get_or_create(
            organization=org,
            sku=item["sku"],
            defaults={
                "name": item["name"],
                "barcode": item["barcode"],
                "category": cat,
                "unit": item["unit"],
                "unit_cost": item["unit_cost"],
                "reorder_level": item["reorder_level"],
                "is_active": True,
            }
        )
        print(f"Product: {prod.name} (SKU: {prod.sku})")

        loc = locations[item["location_name"]]
        expiry_dt = today + timedelta(days=item["expiry_days"])

        batch, b_created = Batch.objects.get_or_create(
            organization=org,
            batch_code=item["batch_code"],
            defaults={
                "product": prod,
                "location": loc,
                "received_date": today,
                "expiry_date": expiry_dt,
                "quantity": item["qty"],
                "status": item["status"],
            }
        )
        print(f"  Batch: {batch.batch_code} ({batch.quantity} {prod.unit})")

        if item["sku"] == "SKU-HYD-8821":
            Alert.objects.get_or_create(
                organization=org,
                batch=batch,
                defaults={
                    "severity": Alert.Severity.CRITICAL,
                    "message": "Hyderabadi Dum Biryani batch expires in under 2 hours. Priority NGO broadcast active.",
                    "is_acknowledged": False,
                }
            )

    print("Seed complete successfully!")

if __name__ == '__main__':
    seed()
