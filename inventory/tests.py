from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.core.management import call_command
from rest_framework.test import APIClient

from accounts.models import Organization, User
from inventory.models import Category, Product, Batch, Alert, AlertRule, StorageLocation, StockTransaction, POSApiKey
from inventory.authentication import create_pos_key


class InventoryWorkflowTests(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Supermarket Alpha", org_type="BUSINESS")
        self.org2 = Organization.objects.create(name="City Food Bank", org_type="NGO")

        self.user1 = User.objects.create_user(
            username="user_alpha",
            password="password123",
            organization=self.org1,
        )

        self.category = Category.objects.create(
            name="Dairy",
            perishability_risk=Category.Risk.HIGH,
            storage_type=Category.Storage.CHILLED,
            default_shelf_life_days=7,
        )

        self.product = Product.objects.create(
            organization=self.org1,
            name="Organic Whole Milk 1L",
            sku="MILK-ORG-1L",
            barcode="8901234567890",
            category=self.category,
            unit="L",
            unit_cost=Decimal("2.50"),
            reorder_level=Decimal("10"),
        )

        # Batch expiring in 2 days
        self.expiring_batch = Batch.objects.create(
            organization=self.org1,
            product=self.product,
            batch_code="B-001",
            quantity=Decimal("25"),
            received_date=date.today() - timedelta(days=5),
            expiry_date=date.today() + timedelta(days=2),
            status=Batch.Status.ACTIVE,
        )

        self.client = APIClient()

    def test_expiry_check_command(self):
        call_command('check_expiry', days=5)
        # Should create an alert for expiring batch
        alert = Alert.objects.filter(batch=self.expiring_batch).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, Alert.Severity.CRITICAL)

    def test_barcode_lookup_api(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/inventory/products/barcode/8901234567890/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], "Organic Whole Milk 1L")
        self.assertEqual(response.data['source'], "local")

    @patch('inventory.services.fetch_open_food_facts')
    def test_barcode_lookup_open_food_facts_fallback(self, mock_off):
        mock_off.return_value = {
            "source": "open_food_facts",
            "barcode": "737628064502",
            "name": "Thai peanut noodle kit",
            "brand": "Simply Asia",
            "image_url": "https://images.openfoodfacts.org/test.jpg",
            "suggested_category": None,
        }
        self.client.force_authenticate(user=self.user1)
        # Barcode not in local DB
        response = self.client.get('/api/v1/inventory/products/barcode/737628064502/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], "open_food_facts")
        self.assertEqual(response.data['name'], "Thai peanut noodle kit")
        self.assertEqual(response.data['brand'], "Simply Asia")

    @patch('inventory.services.fetch_open_food_facts')
    def test_barcode_lookup_not_found_anywhere(self, mock_off):
        mock_off.return_value = None
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/inventory/products/barcode/0000000000000/')
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found locally or in Open Food Facts", response.data['detail'])

    def test_tenant_isolation(self):
        # Create product for org2
        Product.objects.create(
            organization=self.org2,
            name="Canned Beans",
            category=self.category,
            barcode="9999999999999",
        )
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/inventory/products/')
        self.assertEqual(response.status_code, 200)
        # User 1 should only see products from org 1
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], "Organic Whole Milk 1L")

    def test_batch_cross_org_foreign_key_rejected(self):
        # Create Product and Location belonging to org2
        product_org2 = Product.objects.create(
            organization=self.org2,
            name="Org2 Bread",
            category=self.category,
        )
        location_org2 = StorageLocation.objects.create(
            organization=self.org2,
            name="Org2 Pantry",
            storage_type=Category.Storage.AMBIENT,
        )

        self.client.force_authenticate(user=self.user1)

        # 1. Try to create batch with Org2's product
        payload_bad_product = {
            "product": product_org2.id,
            "quantity": "10",
            "received_date": str(date.today()),
            "expiry_date": str(date.today() + timedelta(days=5)),
        }
        res = self.client.post('/api/v1/inventory/batches/', payload_bad_product, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn("product", res.data)

        # 2. Try to create batch with Org2's storage location
        payload_bad_location = {
            "product": self.product.id,
            "location": location_org2.id,
            "quantity": "10",
            "received_date": str(date.today()),
            "expiry_date": str(date.today() + timedelta(days=5)),
        }
        res2 = self.client.post('/api/v1/inventory/batches/', payload_bad_location, format='json')
        self.assertEqual(res2.status_code, 400)
        self.assertIn("location", res2.data)

    def test_stock_transaction_cross_org_batch_rejected(self):
        # Create a batch in org2
        product_org2 = Product.objects.create(organization=self.org2, name="Org2 Juice", category=self.category)
        batch_org2 = Batch.objects.create(
            organization=self.org2,
            product=product_org2,
            quantity=Decimal("50"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=10),
        )

        self.client.force_authenticate(user=self.user1)

        payload = {
            "batch": batch_org2.id,
            "txn_type": StockTransaction.Type.SOLD,
            "quantity": "5",
        }
        res = self.client.post('/api/v1/inventory/transactions/', payload, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn("batch", res.data)

    def test_pos_api_key_valid_authenticates(self):
        raw_key = create_pos_key(self.org1, "Register 1")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")

        res = client.get('/api/v1/inventory/products/')
        self.assertEqual(res.status_code, 200)
        results = res.data.get('results', res.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], "Organic Whole Milk 1L")

    def test_pos_api_key_invalid_or_inactive_returns_401(self):
        client = APIClient()
        # Invalid key
        client.credentials(HTTP_AUTHORIZATION="Api-Key invalid_key_12345")
        res_invalid = client.get('/api/v1/inventory/products/')
        self.assertEqual(res_invalid.status_code, 401)

        # Inactive key
        raw_key = create_pos_key(self.org1, "Register 2")
        pos_key_obj = POSApiKey.objects.get(label="Register 2")
        pos_key_obj.is_active = False
        pos_key_obj.save()

        client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
        res_inactive = client.get('/api/v1/inventory/products/')
        self.assertEqual(res_inactive.status_code, 401)

    def test_pos_api_key_tenant_isolation(self):
        # Key belongs to org2
        raw_key_org2 = create_pos_key(self.org2, "Org 2 Terminal")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key_org2}")

        # List products - should not see Org1's product
        res = client.get('/api/v1/inventory/products/')
        self.assertEqual(res.status_code, 200)
        results = res.data.get('results', res.data)
        self.assertEqual(len(results), 0)

        # Detail product - Org1's product returns 404
        detail_res = client.get(f'/api/v1/inventory/products/{self.product.id}/')
        self.assertEqual(detail_res.status_code, 404)

    def test_deduct_single_batch(self):
        self.client.force_authenticate(user=self.user1)
        payload = {
            "product": self.product.id,
            "quantity": "10",
            "reason": "POS Sale",
            "txn_type": "SOLD",
        }
        res = self.client.post('/api/v1/inventory/batches/deduct/', payload, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['total_deducted'], "10")

        self.expiring_batch.refresh_from_db()
        self.assertEqual(self.expiring_batch.quantity, Decimal("15"))
        self.assertEqual(self.expiring_batch.status, Batch.Status.ACTIVE)

        txn = StockTransaction.objects.filter(batch=self.expiring_batch, txn_type="SOLD").first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.quantity, Decimal("10"))
        self.assertEqual(txn.source, "MANUAL")
        self.assertEqual(txn.created_by, self.user1)

    def test_deduct_multi_batch_fefo_order(self):
        # Create a second batch expiring LATER than self.expiring_batch
        later_batch = Batch.objects.create(
            organization=self.org1,
            product=self.product,
            batch_code="B-LATER",
            quantity=Decimal("20"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=10),
            status=Batch.Status.ACTIVE,
        )

        # self.expiring_batch has 25 qty and expires in 2 days.
        # Deduct 30 units: should take 25 from expiring_batch and 5 from later_batch.
        self.client.force_authenticate(user=self.user1)
        payload = {
            "product": self.product.id,
            "quantity": "30",
            "txn_type": "SOLD",
        }
        res = self.client.post('/api/v1/inventory/batches/deduct/', payload, format='json')
        self.assertEqual(res.status_code, 200)

        self.expiring_batch.refresh_from_db()
        later_batch.refresh_from_db()

        self.assertEqual(self.expiring_batch.quantity, Decimal("0"))
        self.assertEqual(self.expiring_batch.status, Batch.Status.DEPLETED)

        self.assertEqual(later_batch.quantity, Decimal("15"))
        self.assertEqual(later_batch.status, Batch.Status.ACTIVE)

        # Verify two transactions created
        txns = StockTransaction.objects.filter(batch__product=self.product, txn_type="SOLD")
        self.assertEqual(txns.count(), 2)

    def test_deduct_insufficient_stock_rolls_back(self):
        self.client.force_authenticate(user=self.user1)
        payload = {
            "product": self.product.id,
            "quantity": "500",  # Only 25 available
            "txn_type": "SOLD",
        }
        res = self.client.post('/api/v1/inventory/batches/deduct/', payload, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.data)
        self.assertEqual(res.data['available_quantity'], "25.000")

        # Confirm rollback: batch quantity untouched
        self.expiring_batch.refresh_from_db()
        self.assertEqual(self.expiring_batch.quantity, Decimal("25"))
        self.assertEqual(StockTransaction.objects.filter(batch=self.expiring_batch).count(), 0)

    def test_deduct_skips_expired_batches(self):
        # Create an expired batch
        Batch.objects.create(
            organization=self.org1,
            product=self.product,
            quantity=Decimal("10"),
            received_date=date.today() - timedelta(days=20),
            expiry_date=date.today() - timedelta(days=1),
            status=Batch.Status.ACTIVE,
        )

        self.client.force_authenticate(user=self.user1)
        # Request 30 (only self.expiring_batch with 25 is active and non-expired)
        res = self.client.post('/api/v1/inventory/batches/deduct/', {
            "product": self.product.id,
            "quantity": "30",
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['available_quantity'], "25.000")

    def test_deduct_cross_org_product_rejected(self):
        product_org2 = Product.objects.create(organization=self.org2, name="Org2 Item", category=self.category)
        self.client.force_authenticate(user=self.user1)

        res = self.client.post('/api/v1/inventory/batches/deduct/', {
            "product": product_org2.id,
            "quantity": "5",
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_dashboard_summary(self):
        # Create unacknowledged critical alert
        Alert.objects.create(
            organization=self.org1,
            batch=self.expiring_batch,
            severity=Alert.Severity.CRITICAL,
            message="Critical test alert",
            is_acknowledged=False,
        )

        # Create product with NO unit cost (to test missing_cost_items handling)
        no_cost_prod = Product.objects.create(
            organization=self.org1,
            name="No Cost Item",
            category=self.category,
            unit_cost=None,
        )
        no_cost_batch = Batch.objects.create(
            organization=self.org1,
            product=no_cost_prod,
            quantity=Decimal("5"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=1),
            status=Batch.Status.ACTIVE,
        )

        # Create transactions: DISCARDED (with unit_cost $2.50)
        StockTransaction.objects.create(
            organization=self.org1,
            batch=self.expiring_batch,
            txn_type="DISCARDED",
            quantity=Decimal("4"),  # 4 * 2.50 = 10.00
        )
        # Create transaction: DONATED (with unit_cost $2.50)
        StockTransaction.objects.create(
            organization=self.org1,
            batch=self.expiring_batch,
            txn_type="DONATED",
            quantity=Decimal("6"),  # 6 * 2.50 = 15.00
        )
        # Create transaction on no_cost_prod: DISCARDED
        StockTransaction.objects.create(
            organization=self.org1,
            batch=no_cost_batch,
            txn_type="DISCARDED",
            quantity=Decimal("2"),  # no unit cost -> missing_cost_items += 1
        )

        self.client.force_authenticate(user=self.user1)
        res = self.client.get('/api/v1/inventory/dashboard/summary/')
        self.assertEqual(res.status_code, 200)

        data = res.data
        self.assertEqual(data['total_active_batches'], 2)  # expiring_batch + no_cost_batch
        self.assertEqual(Decimal(data['total_active_quantity']), Decimal("30.000"))
        self.assertEqual(data['critical_alerts_unacknowledged'], 1)
        self.assertEqual(Decimal(data['wasted_value_30d']), Decimal("10.00"))
        self.assertEqual(Decimal(data['donated_value_30d']), Decimal("15.00"))
        self.assertEqual(data['missing_cost_items'], 1)
