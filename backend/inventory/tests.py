from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase
from django.core.management import call_command
from rest_framework.test import APIClient

from accounts.models import Organization, User
from inventory.models import Category, Product, Batch, Alert, AlertRule, StorageLocation, StockTransaction, POSApiKey, ImportJob
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

    def test_alerts_strictly_less_than_7_days(self):
        from inventory.services import evaluate_expiry_alerts
        # Batch expiring in 10 days (>= 7 days) -> no alert
        b_10d = Batch.objects.create(
            organization=self.org1,
            product=self.product,
            batch_code="B-10D",
            quantity=Decimal("10"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=10),
            status=Batch.Status.ACTIVE,
        )
        # Batch expiring in 7 days (>= 7 days) -> no alert
        b_7d = Batch.objects.create(
            organization=self.org1,
            product=self.product,
            batch_code="B-7D",
            quantity=Decimal("10"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=7),
            status=Batch.Status.ACTIVE,
        )
        # Batch expiring in 6 days (< 7 days) -> creates alert
        b_6d = Batch.objects.create(
            organization=self.org1,
            product=self.product,
            batch_code="B-6D",
            quantity=Decimal("10"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=6),
            status=Batch.Status.ACTIVE,
        )

        evaluate_expiry_alerts(organization=self.org1)

        self.assertFalse(Alert.objects.filter(batch=b_10d).exists())
        self.assertFalse(Alert.objects.filter(batch=b_7d).exists())
        self.assertTrue(Alert.objects.filter(batch=b_6d).exists())


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

    @patch('inventory.services.fetch_fatsecret_food')
    def test_barcode_lookup_fatsecret(self, mock_fatsecret):
        mock_fatsecret.return_value = {
            "source": "fatsecret",
            "barcode": "8901234560000",
            "name": "Amul Pure Ghee 1L",
            "brand": "Amul",
            "calories": "900",
            "protein": "0",
            "carbohydrate": "0",
            "fat": "100",
            "serving_description": "100g",
            "suggested_category": None,
        }
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/inventory/products/barcode/8901234560000/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], "fatsecret")
        self.assertEqual(response.data['name'], "Amul Pure Ghee 1L")
        self.assertEqual(response.data['brand'], "Amul")
        self.assertEqual(response.data['calories'], "900")

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
        self.assertEqual(res.status_code, 404)

    def test_deduct_by_barcode(self):
        self.client.force_authenticate(user=self.user1)
        res = self.client.post('/api/v1/inventory/batches/deduct/', {
            "barcode": "8901234567890",
            "quantity": "5",
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['total_deducted'], "5")
        self.expiring_batch.refresh_from_db()
        self.assertEqual(self.expiring_batch.quantity, Decimal("20"))

    def test_deduct_by_sku(self):
        self.client.force_authenticate(user=self.user1)
        res = self.client.post('/api/v1/inventory/batches/deduct/', {
            "sku": "MILK-ORG-1L",
            "quantity": "5",
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['total_deducted'], "5")
        self.expiring_batch.refresh_from_db()
        self.assertEqual(self.expiring_batch.quantity, Decimal("20"))

    def test_deduct_by_id(self):
        self.client.force_authenticate(user=self.user1)
        res = self.client.post('/api/v1/inventory/batches/deduct/', {
            "product": self.product.id,
            "quantity": "5",
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['total_deducted'], "5")
        self.expiring_batch.refresh_from_db()
        self.assertEqual(self.expiring_batch.quantity, Decimal("20"))

    def test_deduct_ambiguous_identifiers_rejected(self):
        self.client.force_authenticate(user=self.user1)
        # None provided
        res_none = self.client.post('/api/v1/inventory/batches/deduct/', {
            "quantity": "5",
        }, format='json')
        self.assertEqual(res_none.status_code, 400)

        # Both product and barcode
        res_prod_bar = self.client.post('/api/v1/inventory/batches/deduct/', {
            "product": self.product.id,
            "barcode": "8901234567890",
            "quantity": "5",
        }, format='json')
        self.assertEqual(res_prod_bar.status_code, 400)

        # Both barcode and sku
        res_bar_sku = self.client.post('/api/v1/inventory/batches/deduct/', {
            "barcode": "8901234567890",
            "sku": "MILK-ORG-1L",
            "quantity": "5",
        }, format='json')
        self.assertEqual(res_bar_sku.status_code, 400)

    def test_deduct_cross_org_barcode_returns_404(self):
        Product.objects.create(
            organization=self.org2,
            name="Org2 Milk",
            barcode="7777777777",
            sku="ORG2-SKU",
            category=self.category,
        )
        self.client.force_authenticate(user=self.user1)

        res_barcode = self.client.post('/api/v1/inventory/batches/deduct/', {
            "barcode": "7777777777",
            "quantity": "5",
        }, format='json')
        self.assertEqual(res_barcode.status_code, 404)

        res_sku = self.client.post('/api/v1/inventory/batches/deduct/', {
            "sku": "ORG2-SKU",
            "quantity": "5",
        }, format='json')
        self.assertEqual(res_sku.status_code, 404)

    def test_deduct_idempotent_replay(self):
        self.client.force_authenticate(user=self.user1)
        payload = {
            "barcode": "8901234567890",
            "quantity": "5",
            "external_id": "REC-00123",
        }
        res1 = self.client.post('/api/v1/inventory/batches/deduct/', payload, format='json')
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.data['total_deducted'], "5")
        self.assertFalse(res1.data.get('idempotent_replay', False))

        self.expiring_batch.refresh_from_db()
        self.assertEqual(self.expiring_batch.quantity, Decimal("20"))

        # Replay same request
        res2 = self.client.post('/api/v1/inventory/batches/deduct/', payload, format='json')
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(Decimal(res2.data['total_deducted']), Decimal("5"))
        self.assertTrue(res2.data.get('idempotent_replay'))

        # Batch quantity was NOT deducted a second time
        self.expiring_batch.refresh_from_db()
        self.assertEqual(self.expiring_batch.quantity, Decimal("20"))

        # Only 1 transaction exists with external_id REC-00123
        txns = StockTransaction.objects.filter(organization=self.org1, external_id="REC-00123")
        self.assertEqual(txns.count(), 1)


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


class DeductConcurrencyTests(TransactionTestCase):
    def test_deduct_concurrent_replay_safety(self):
        import concurrent.futures
        from django.db import connection

        org = Organization.objects.create(name="Concurrency Org", org_type="BUSINESS")
        user = User.objects.create_user(username="conc_user", password="password123", organization=org)
        cat = Category.objects.create(name="Conc Cat", perishability_risk=Category.Risk.MEDIUM)
        prod = Product.objects.create(organization=org, name="Conc Product", category=cat)
        batch = Batch.objects.create(
            organization=org,
            product=prod,
            quantity=Decimal("25"),
            received_date=date.today() - timedelta(days=2),
            expiry_date=date.today() + timedelta(days=5),
            status=Batch.Status.ACTIVE,
        )

        payload = {
            "product": prod.id,
            "quantity": "4",
            "external_id": "CONC-REPLAY-999",
        }

        def make_request():
            c = APIClient()
            c.force_authenticate(user=user)
            res = c.post('/api/v1/inventory/batches/deduct/', payload, format='json')
            connection.close()
            return res.status_code, res.data.get('idempotent_replay')

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(make_request)
            f2 = executor.submit(make_request)
            r1 = f1.result()
            r2 = f2.result()

        # Both requests return 200 OK
        self.assertEqual(r1[0], 200)
        self.assertEqual(r2[0], 200)

        # Batch was only deducted 4 units (not 8)
        batch.refresh_from_db()
        self.assertEqual(batch.quantity, Decimal("21"))

        # Exactly 1 transaction created
        txns = StockTransaction.objects.filter(organization=org, external_id="CONC-REPLAY-999")
        self.assertEqual(txns.count(), 1)


class ScheduledExpiryCheckTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="Org A Expiry", org_type=Organization.Type.BUSINESS)
        self.org_b = Organization.objects.create(name="Org B Expiry", org_type=Organization.Type.BUSINESS)
        self.category = Category.objects.create(name="Dairy Expiry", perishability_risk=Category.Risk.HIGH)

        self.prod_a = Product.objects.create(
            organization=self.org_a,
            name="Milk A",
            category=self.category,
            unit="L",
        )
        self.prod_b = Product.objects.create(
            organization=self.org_b,
            name="Milk B",
            category=self.category,
            unit="L",
        )

    def test_marks_past_expiry_batches_expired(self):
        from inventory.tasks import run_expiry_check
        past_batch = Batch.objects.create(
            organization=self.org_a,
            product=self.prod_a,
            batch_code="PAST-1",
            quantity=Decimal("15"),
            received_date=date.today() - timedelta(days=10),
            expiry_date=date.today() - timedelta(days=2),
            status=Batch.Status.ACTIVE,
        )

        res = run_expiry_check(days=7)
        self.assertGreaterEqual(res["batches_expired"], 1)

        past_batch.refresh_from_db()
        self.assertEqual(past_batch.status, Batch.Status.EXPIRED)

        # The ones which are expired should NOT be in the alert section
        alert = Alert.objects.filter(batch=past_batch).first()
        self.assertIsNone(alert)

    def test_expired_batches_excluded_from_alert_section(self):
        from inventory.services import evaluate_expiry_alerts
        # 1. An already expired batch does not create an alert
        expired_batch = Batch.objects.create(
            organization=self.org_a,
            product=self.prod_a,
            batch_code="EXP-PAST",
            quantity=Decimal("10"),
            received_date=date.today() - timedelta(days=20),
            expiry_date=date.today() - timedelta(days=1),
            status=Batch.Status.EXPIRED,
        )
        # 2. An active batch expiring in 2 days creates an alert
        crit_batch = Batch.objects.create(
            organization=self.org_a,
            product=self.prod_a,
            batch_code="CRIT-2D",
            quantity=Decimal("10"),
            received_date=date.today() - timedelta(days=5),
            expiry_date=date.today() + timedelta(days=2),
            status=Batch.Status.ACTIVE,
        )
        evaluate_expiry_alerts(organization=self.org_a)
        self.assertFalse(Alert.objects.filter(batch=expired_batch).exists())
        self.assertTrue(Alert.objects.filter(batch=crit_batch).exists())

        # 3. When crit_batch expires, running evaluate_expiry_alerts cleans up its alert
        crit_batch.expiry_date = date.today() - timedelta(days=1)
        crit_batch.save()
        evaluate_expiry_alerts(organization=self.org_a)
        crit_batch.refresh_from_db()
        self.assertEqual(crit_batch.status, Batch.Status.EXPIRED)
        self.assertFalse(Alert.objects.filter(batch=crit_batch).exists())

    def test_creates_deduplicated_alerts(self):
        from inventory.tasks import run_expiry_check
        batch = Batch.objects.create(
            organization=self.org_a,
            product=self.prod_a,
            batch_code="EXP-2D",
            quantity=Decimal("20"),
            received_date=date.today() - timedelta(days=5),
            expiry_date=date.today() + timedelta(days=2),
            status=Batch.Status.ACTIVE,
        )

        res1 = run_expiry_check(days=7)
        self.assertEqual(Alert.objects.filter(batch=batch).count(), 1)

        res2 = run_expiry_check(days=7)
        self.assertEqual(Alert.objects.filter(batch=batch).count(), 1)
        self.assertEqual(res2["alerts_created"], 0)

    def test_idempotent_on_second_run(self):
        from inventory.tasks import run_expiry_check
        Batch.objects.create(
            organization=self.org_a,
            product=self.prod_a,
            batch_code="PAST-2",
            quantity=Decimal("5"),
            received_date=date.today() - timedelta(days=10),
            expiry_date=date.today() - timedelta(days=1),
            status=Batch.Status.ACTIVE,
        )
        Batch.objects.create(
            organization=self.org_a,
            product=self.prod_a,
            batch_code="EXP-4D",
            quantity=Decimal("8"),
            received_date=date.today() - timedelta(days=2),
            expiry_date=date.today() + timedelta(days=4),
            status=Batch.Status.ACTIVE,
        )

        res1 = run_expiry_check(days=7)
        initial_alerts_count = Alert.objects.count()

        res2 = run_expiry_check(days=7)
        self.assertEqual(res2["alerts_created"], 0)
        self.assertEqual(res2["batches_expired"], 0)
        self.assertEqual(Alert.objects.count(), initial_alerts_count)

    def test_organization_isolation(self):
        from inventory.tasks import run_expiry_check
        b_a = Batch.objects.create(
            organization=self.org_a,
            product=self.prod_a,
            batch_code="A-CRIT",
            quantity=Decimal("10"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=2),
            status=Batch.Status.ACTIVE,
        )
        b_b = Batch.objects.create(
            organization=self.org_b,
            product=self.prod_b,
            batch_code="B-SAFE",
            quantity=Decimal("10"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=20),
            status=Batch.Status.ACTIVE,
        )

        res = run_expiry_check(days=7, organization=self.org_a)
        self.assertTrue(Alert.objects.filter(organization=self.org_a, batch=b_a).exists())
        self.assertFalse(Alert.objects.filter(organization=self.org_b).exists())

    def test_setup_schedules_twice_leaves_one_schedule_per_job(self):
        from django_q.models import Schedule
        call_command("setup_schedules")
        count_exp_1 = Schedule.objects.filter(name="daily_expiry_check").count()
        count_list_1 = Schedule.objects.filter(name="expire_stale_marketplace_listings").count()
        self.assertEqual(count_exp_1, 1)
        self.assertEqual(count_list_1, 1)

        # Running again must be idempotent and not create duplicate rows
        call_command("setup_schedules")
        count_exp_2 = Schedule.objects.filter(name="daily_expiry_check").count()
        count_list_2 = Schedule.objects.filter(name="expire_stale_marketplace_listings").count()
        self.assertEqual(count_exp_2, 1)
        self.assertEqual(count_list_2, 1)

        exp_sched = Schedule.objects.get(name="daily_expiry_check")
        self.assertEqual(exp_sched.func, "inventory.tasks.run_expiry_check")
        self.assertEqual(exp_sched.schedule_type, Schedule.DAILY)
        self.assertEqual(exp_sched.repeats, -1)


class AsyncCSVImportTests(TestCase):
    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.org_a = Organization.objects.create(name="CSV Org A", org_type=Organization.Type.BUSINESS)
        self.org_b = Organization.objects.create(name="CSV Org B", org_type=Organization.Type.BUSINESS)

        self.user_a = User.objects.create_user(
            username="user_csv_a",
            password="password123",
            organization=self.org_a,
        )
        self.user_b = User.objects.create_user(
            username="user_csv_b",
            password="password123",
            organization=self.org_b,
        )

        self.client_a = APIClient()
        self.client_a.force_authenticate(user=self.user_a)

        self.client_b = APIClient()
        self.client_b.force_authenticate(user=self.user_b)

        self.valid_csv_3 = (
            "product_name,sku,barcode,quantity,unit,expiry_date\n"
            "Organic Milk,SKU-M1,890001,10,L,2026-11-01\n"
            "Whole Wheat Bread,SKU-B1,890002,15,pcs,2026-11-05\n"
            "Greek Yogurt,SKU-Y1,890003,20,kg,2026-11-10\n"
        )

    def test_small_file_runs_inline(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_file = SimpleUploadedFile("items.csv", self.valid_csv_3.encode("utf-8"), content_type="text/csv")
        response = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": csv_file}, format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "DONE")
        self.assertEqual(response.data["total_rows"], 3)
        self.assertEqual(response.data["processed_rows"], 3)
        self.assertEqual(response.data["rows_ok"], 3)
        self.assertEqual(response.data["rows_failed"], 0)

        # Products and batches created for org_a
        self.assertEqual(Product.objects.filter(organization=self.org_a).count(), 3)
        self.assertEqual(Batch.objects.filter(organization=self.org_a).count(), 3)

    def test_large_file_returns_202_and_processed_by_task(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings

        # Set limit to 2 so 3 rows counts as a large file
        with override_settings(IMPORT_SYNC_ROW_LIMIT=2):
            csv_file = SimpleUploadedFile("items_large.csv", self.valid_csv_3.encode("utf-8"), content_type="text/csv")
            response = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": csv_file}, format="multipart")

            # Must return 202 Accepted
            self.assertEqual(response.status_code, 202)
            job_id = response.data["id"]

            job = ImportJob.objects.get(id=job_id)
            # Under test synchronous execution, task completes inline
            self.assertEqual(job.status, "DONE")
            self.assertEqual(job.total_rows, 3)
            self.assertEqual(job.processed_rows, 3)
            self.assertEqual(job.rows_ok, 3)
            self.assertIsNotNone(job.started_at)
            self.assertIsNotNone(job.finished_at)

    def test_progress_fields_update(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_file = SimpleUploadedFile("items.csv", self.valid_csv_3.encode("utf-8"), content_type="text/csv")
        response = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": csv_file}, format="multipart")
        self.assertEqual(response.status_code, 201)

        job = ImportJob.objects.get(id=response.data["id"])
        self.assertGreater(job.total_rows, 0)
        self.assertEqual(job.total_rows, job.processed_rows)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.finished_at)

    def test_mixed_good_and_bad_rows_report_correctly(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        mixed_csv = (
            "product_name,sku,barcode,quantity,unit,expiry_date\n"
            "Good Item 1,SKU-G1,890010,5,kg,2026-11-20\n"
            "Bad Date Item,SKU-B2,890011,5,kg,invalid-date\n"
            ",SKU-M3,890012,5,kg,2026-11-20\n"
            "Good Item 2,SKU-G2,890013,8,kg,2026-11-25\n"
        )
        csv_file = SimpleUploadedFile("mixed.csv", mixed_csv.encode("utf-8"), content_type="text/csv")
        response = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": csv_file}, format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["rows_ok"], 2)
        self.assertEqual(response.data["rows_failed"], 2)
        self.assertEqual(response.data["total_rows"], 4)
        self.assertEqual(response.data["processed_rows"], 4)

        report = response.data["error_report"]
        self.assertEqual(len(report), 2)
        error_rows = [r["row"] for r in report]
        self.assertIn(3, error_rows)  # bad date row
        self.assertIn(4, error_rows)  # missing product name row

    def test_retry_after_crash_does_not_duplicate_batches(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from inventory.services import process_import_job

        csv_file = SimpleUploadedFile("retry.csv", self.valid_csv_3.encode("utf-8"), content_type="text/csv")
        response = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": csv_file}, format="multipart")
        self.assertEqual(response.status_code, 201)

        job = ImportJob.objects.get(id=response.data["id"])
        batches_before = Batch.objects.filter(organization=self.org_a).count()
        txns_before = StockTransaction.objects.filter(organization=self.org_a).count()
        self.assertEqual(batches_before, 3)

        # Simulate job retry while in PROCESSING state
        job.status = ImportJob.Status.PROCESSING
        job.save()
        process_import_job(job)

        batches_after = Batch.objects.filter(organization=self.org_a).count()
        txns_after = StockTransaction.objects.filter(organization=self.org_a).count()
        self.assertEqual(batches_after, batches_before)
        self.assertEqual(txns_after, txns_before)

        # When job is DONE, retry is completely a no-op
        self.assertEqual(job.status, ImportJob.Status.DONE)
        process_import_job(job)
        self.assertEqual(Batch.objects.filter(organization=self.org_a).count(), batches_before)

    def test_cross_organization_job_access_returns_404(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_file = SimpleUploadedFile("secret.csv", self.valid_csv_3.encode("utf-8"), content_type="text/csv")
        response_a = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": csv_file}, format="multipart")
        job_id = response_a.data["id"]

        # Org A user can access it
        resp_a = self.client_a.get(f"/api/v1/inventory/import-jobs/{job_id}/")
        self.assertEqual(resp_a.status_code, 200)

        # Org B user gets 404
        resp_b = self.client_b.get(f"/api/v1/inventory/import-jobs/{job_id}/")
        self.assertEqual(resp_b.status_code, 404)

    def test_invalid_files_rejected_before_queueing(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        # 1. Non-CSV extension
        txt_file = SimpleUploadedFile("items.txt", b"some text", content_type="text/plain")
        res = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": txt_file}, format="multipart")
        self.assertEqual(res.status_code, 400)

        # 2. Empty file
        empty_file = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")
        res = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": empty_file}, format="multipart")
        self.assertEqual(res.status_code, 400)

        # 3. Missing required headers
        bad_headers = SimpleUploadedFile("bad_headers.csv", b"col_a,col_b\n1,2\n", content_type="text/csv")
        res = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": bad_headers}, format="multipart")
        self.assertEqual(res.status_code, 400)

        # 4. Header-only
        header_only = SimpleUploadedFile("header_only.csv", b"product_name,quantity,expiry_date\n", content_type="text/csv")
        res = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": header_only}, format="multipart")
        self.assertEqual(res.status_code, 400)

        # None of these created ImportJob records
        self.assertEqual(ImportJob.objects.filter(organization=self.org_a).count(), 0)

    def test_file_size_limit_2mb(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        # Over 2 MB: 2 * 1024 * 1024 + 10 bytes
        big_data = b"product_name,quantity,expiry_date\n" + b"A" * (2 * 1024 * 1024 + 10)
        big_file = SimpleUploadedFile("oversized.csv", big_data, content_type="text/csv")
        res = self.client_a.post("/api/v1/inventory/import-jobs/", {"file": big_file}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertIn("exceeds the 2 MB limit", res.data["error"])

    def test_worker_may_be_down_detection(self):
        from django.utils import timezone
        job = ImportJob.objects.create(
            organization=self.org_a,
            status=ImportJob.Status.PENDING,
            total_rows=10,
        )
        # Job just created: worker_may_be_down should be False
        res = self.client_a.get(f"/api/v1/inventory/import-jobs/{job.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["worker_may_be_down"])

        # Manually age job created_at by 3 minutes
        ImportJob.objects.filter(id=job.id).update(created_at=timezone.now() - timedelta(minutes=3))
        res = self.client_a.get(f"/api/v1/inventory/import-jobs/{job.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["worker_may_be_down"])


class BatchReservationAndSellableTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Reservation Test Org", org_type="BUSINESS")
        self.user = User.objects.create_user(
            username="res_user",
            password="password123",
            organization=self.org,
        )
        self.cat = Category.objects.create(name="Test Cat", perishability_risk=Category.Risk.MEDIUM)
        self.prod = Product.objects.create(
            organization=self.org,
            name="Test Milk",
            sku="TMILK-1",
            category=self.cat,
            unit="L",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_batch_reserved_quantity_check_constraints(self):
        from django.db import IntegrityError, transaction
        # 1. Negative reserved quantity must violate constraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Batch.objects.create(
                    organization=self.org,
                    product=self.prod,
                    quantity=Decimal("10.000"),
                    reserved_quantity=Decimal("-1.000"),
                    received_date=date.today(),
                    expiry_date=date.today() + timedelta(days=5),
                )

        # 2. reserved_quantity > quantity must violate constraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Batch.objects.create(
                    organization=self.org,
                    product=self.prod,
                    quantity=Decimal("10.000"),
                    reserved_quantity=Decimal("11.000"),
                    received_date=date.today(),
                    expiry_date=date.today() + timedelta(days=5),
                )

    def test_batch_objects_sellable_queryset(self):
        # Active batch with sellable stock (10 total, 3 reserved -> 7 sellable)
        b1 = Batch.objects.create(
            organization=self.org,
            product=self.prod,
            quantity=Decimal("10.000"),
            reserved_quantity=Decimal("3.000"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=5),
            status=Batch.Status.ACTIVE,
        )
        # Fully reserved batch (5 total, 5 reserved -> 0 sellable)
        b2 = Batch.objects.create(
            organization=self.org,
            product=self.prod,
            quantity=Decimal("5.000"),
            reserved_quantity=Decimal("5.000"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=5),
            status=Batch.Status.ACTIVE,
        )
        # Expired batch
        b3 = Batch.objects.create(
            organization=self.org,
            product=self.prod,
            quantity=Decimal("10.000"),
            reserved_quantity=Decimal("0.000"),
            received_date=date.today() - timedelta(days=10),
            expiry_date=date.today() - timedelta(days=1),
            status=Batch.Status.ACTIVE,
        )
        # Depleted batch
        b4 = Batch.objects.create(
            organization=self.org,
            product=self.prod,
            quantity=Decimal("0.000"),
            reserved_quantity=Decimal("0.000"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=5),
            status=Batch.Status.DEPLETED,
        )

        sellable = list(Batch.objects.sellable().filter(organization=self.org))
        self.assertEqual(len(sellable), 1)
        self.assertEqual(sellable[0].id, b1.id)
        self.assertEqual(sellable[0].sellable_quantity, Decimal("7.000"))

    def test_fefo_deduct_and_pos_cannot_take_reserved_stock(self):
        # Batch: 10 total, 6 reserved for an approved donation (4 sellable)
        batch = Batch.objects.create(
            organization=self.org,
            product=self.prod,
            quantity=Decimal("10.000"),
            reserved_quantity=Decimal("6.000"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=5),
            status=Batch.Status.ACTIVE,
        )

        # 1. Attempting to deduct 5 via POS API should fail with 400 (only 4 available)
        payload_fail = {
            "sku": self.prod.sku,
            "quantity": "5",
            "source": "POS",
        }
        res_fail = self.client.post("/api/v1/inventory/batches/deduct/", payload_fail, format="json")
        self.assertEqual(res_fail.status_code, 400)
        self.assertIn("Insufficient", res_fail.data["error"])
        self.assertEqual(Decimal(str(res_fail.data["available_quantity"])), Decimal("4"))

        # 2. Deducting exactly 4 succeeds
        payload_ok = {
            "sku": self.prod.sku,
            "quantity": "4",
            "source": "POS",
        }
        res_ok = self.client.post("/api/v1/inventory/batches/deduct/", payload_ok, format="json")
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.data["total_deducted"], "4")

        # Refresh batch: quantity is now 6, reserved_quantity is still 6
        batch.refresh_from_db()
        self.assertEqual(batch.quantity, Decimal("6.000"))
        self.assertEqual(batch.reserved_quantity, Decimal("6.000"))
        self.assertEqual(batch.sellable_quantity, Decimal("0.000"))
        # Batch must remain ACTIVE because it still has 6 units reserved for donation
        self.assertEqual(batch.status, Batch.Status.ACTIVE)

        # 3. Subsequent deduction of even 1 unit fails
        payload_subsequent = {
            "sku": self.prod.sku,
            "quantity": "1",
            "source": "POS",
        }
        res_sub = self.client.post("/api/v1/inventory/batches/deduct/", payload_subsequent, format="json")
        self.assertEqual(res_sub.status_code, 400)

    def test_dashboard_and_batch_list_sellable_quantity(self):
        # Create a batch with 20 total, 5 reserved
        batch = Batch.objects.create(
            organization=self.org,
            product=self.prod,
            quantity=Decimal("20.000"),
            reserved_quantity=Decimal("5.000"),
            received_date=date.today(),
            expiry_date=date.today() + timedelta(days=5),
            status=Batch.Status.ACTIVE,
        )

        # 1. Batch detail/list API returns sellable_quantity
        res_batch = self.client.get(f"/api/v1/inventory/batches/{batch.id}/")
        self.assertEqual(res_batch.status_code, 200)
        self.assertEqual(Decimal(str(res_batch.data["quantity"])), Decimal("20.000"))
        self.assertEqual(Decimal(str(res_batch.data["reserved_quantity"])), Decimal("5.000"))
        self.assertEqual(Decimal(str(res_batch.data["sellable_quantity"])), Decimal("15.000"))

        # 2. Dashboard API reflects sellable stock (total_qty - total_reserved = 15)
        res_dash = self.client.get("/api/v1/inventory/dashboard/summary/")
        self.assertEqual(res_dash.status_code, 200)
        self.assertEqual(Decimal(str(res_dash.data["total_active_quantity"])), Decimal("15.000"))



