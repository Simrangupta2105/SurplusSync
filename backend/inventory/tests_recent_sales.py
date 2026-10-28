from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import Organization, User
from inventory.models import Category, Product, Batch, StockTransaction


class RecentSalesAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # 1. Organizations
        self.org_a = Organization.objects.create(name="Supermarket A", org_type=Organization.Type.BUSINESS)
        self.org_b = Organization.objects.create(name="Supermarket B", org_type=Organization.Type.BUSINESS)

        # 2. Users
        self.user_a = User.objects.create_user(
            username="user_a",
            password="password123",
            organization=self.org_a,
        )
        self.user_b = User.objects.create_user(
            username="user_b",
            password="password123",
            organization=self.org_b,
        )
        self.user_no_org = User.objects.create_user(
            username="user_no_org",
            password="password123",
            organization=None,
        )

        # 3. Categories
        self.cat_dairy = Category.objects.create(
            name="Dairy",
            perishability_risk=Category.Risk.HIGH,
            storage_type=Category.Storage.CHILLED,
            default_shelf_life_days=7,
        )
        self.cat_bakery = Category.objects.create(
            name="Bakery",
            perishability_risk=Category.Risk.MEDIUM,
            storage_type=Category.Storage.AMBIENT,
            default_shelf_life_days=3,
        )

        # 4. Products for Org A
        self.prod_milk = Product.objects.create(
            organization=self.org_a,
            name="Whole Milk 1L",
            sku="MILK-1L",
            category=self.cat_dairy,
            unit="L",
            unit_cost=Decimal("40.00"),
        )
        self.prod_bread = Product.objects.create(
            organization=self.org_a,
            name="Sourdough Bread",
            sku="BREAD-01",
            category=self.cat_bakery,
            unit="pcs",
            unit_cost=Decimal("25.00"),
        )

        # 5. Batches for Org A
        self.batch_milk = Batch.objects.create(
            organization=self.org_a,
            product=self.prod_milk,
            batch_code="B-MILK-01",
            quantity=Decimal("100.000"),
            received_date=date.today() - timedelta(days=10),
            expiry_date=date.today() + timedelta(days=5),
        )
        self.batch_bread = Batch.objects.create(
            organization=self.org_a,
            product=self.prod_bread,
            batch_code="B-BREAD-01",
            quantity=Decimal("50.000"),
            received_date=date.today() - timedelta(days=5),
            expiry_date=date.today() + timedelta(days=2),
        )

        # 6. Products & Batches for Org B
        self.prod_b = Product.objects.create(
            organization=self.org_b,
            name="Org B Milk",
            sku="B-MILK-99",
            category=self.cat_dairy,
            unit="L",
            unit_cost=Decimal("50.00"),
        )
        self.batch_b = Batch.objects.create(
            organization=self.org_b,
            product=self.prod_b,
            batch_code="B-ORG-B-01",
            quantity=Decimal("200.000"),
            received_date=date.today() - timedelta(days=5),
            expiry_date=date.today() + timedelta(days=5),
        )

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated requests must be rejected with 401 Unauthorized."""
        response = self.client.get('/api/v1/inventory/sales/recent/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_organization_returns_403(self):
        """Authenticated users lacking organization context must be rejected with 403 Forbidden."""
        self.client.force_authenticate(user=self.user_no_org)
        response = self.client.get('/api/v1/inventory/sales/recent/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Organization context required', response.data['error'])

    def test_empty_sales_returns_zeroes_not_404(self):
        """Organizations with no sales return an unbroken sequence of zeroes, never 404."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get('/api/v1/inventory/sales/recent/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)
        for row in response.data:
            self.assertEqual(row['units_sold'], 0.0)
            self.assertEqual(row['revenue'], 0.0)
            self.assertEqual(row['category'], 'All')
            self.assertRegex(row['date'], r'^\d{4}-\d{2}-\d{2}$')

    def test_default_days_returns_7_days_unbroken_chronological(self):
        """Default request returns exactly 7 days in ascending chronological order."""
        self.client.force_authenticate(user=self.user_a)
        today = timezone.localdate()
        expected_dates = [(today - timedelta(days=6 - i)).strftime('%Y-%m-%d') for i in range(7)]

        response = self.client.get('/api/v1/inventory/sales/recent/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)
        actual_dates = [r['date'] for r in response.data]
        self.assertEqual(actual_dates, expected_dates)

    def test_tenant_isolation_excludes_other_orgs(self):
        """Org A's sales must never leak to Org B, and Org B's sales must never leak to Org A."""
        today = timezone.localdate()
        now = timezone.now()

        # Org A sale
        t_a = StockTransaction.objects.create(
            organization=self.org_a,
            batch=self.batch_milk,
            txn_type=StockTransaction.Type.SOLD,
            quantity=Decimal("15.000"),
            source="POS",
        )
        StockTransaction.objects.filter(id=t_a.id).update(created_at=now)

        # Org B sale
        t_b = StockTransaction.objects.create(
            organization=self.org_b,
            batch=self.batch_b,
            txn_type=StockTransaction.Type.SOLD,
            quantity=Decimal("50.000"),
            source="POS",
        )
        StockTransaction.objects.filter(id=t_b.id).update(created_at=now)

        # Query as Org A
        self.client.force_authenticate(user=self.user_a)
        res_a = self.client.get('/api/v1/inventory/sales/recent/')
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        today_a = [r for r in res_a.data if r['date'] == today.strftime('%Y-%m-%d')][0]
        self.assertEqual(today_a['units_sold'], 15.0)
        self.assertEqual(today_a['revenue'], 600.0)  # 15 * 40.00

        # Query as Org B
        self.client.force_authenticate(user=self.user_b)
        res_b = self.client.get('/api/v1/inventory/sales/recent/')
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)
        today_b = [r for r in res_b.data if r['date'] == today.strftime('%Y-%m-%d')][0]
        self.assertEqual(today_b['units_sold'], 50.0)
        self.assertEqual(today_b['revenue'], 2500.0)  # 50 * 50.00

    def test_only_sold_transactions_counted(self):
        """Only transactions with txn_type == SOLD contribute to units_sold and revenue."""
        self.client.force_authenticate(user=self.user_a)
        today = timezone.localdate()
        now = timezone.now()

        # Create transactions of each type
        for t_type, qty in [
            (StockTransaction.Type.RECEIVED, Decimal("100.0")),
            (StockTransaction.Type.DISCARDED, Decimal("10.0")),
            (StockTransaction.Type.DONATED, Decimal("5.0")),
            (StockTransaction.Type.ADJUSTMENT, Decimal("2.0")),
            (StockTransaction.Type.SOLD, Decimal("12.0")),
        ]:
            t = StockTransaction.objects.create(
                organization=self.org_a,
                batch=self.batch_milk,
                txn_type=t_type,
                quantity=qty,
                source="MANUAL",
            )
            StockTransaction.objects.filter(id=t.id).update(created_at=now)

        response = self.client.get('/api/v1/inventory/sales/recent/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        today_row = [r for r in response.data if r['date'] == today.strftime('%Y-%m-%d')][0]
        self.assertEqual(today_row['units_sold'], 12.0)
        self.assertEqual(today_row['revenue'], 480.0)  # 12 * 40.00

    def test_category_filter_and_breakdown(self):
        """Filter by ?category=<name> returns data for only that category."""
        self.client.force_authenticate(user=self.user_a)
        today = timezone.localdate()
        now = timezone.now()

        # Dairy sale: 10 units @ 40.00 = 400.00
        t1 = StockTransaction.objects.create(
            organization=self.org_a,
            batch=self.batch_milk,
            txn_type=StockTransaction.Type.SOLD,
            quantity=Decimal("10.000"),
            source="POS",
        )
        StockTransaction.objects.filter(id=t1.id).update(created_at=now)

        # Bakery sale: 20 units @ 25.00 = 500.00
        t2 = StockTransaction.objects.create(
            organization=self.org_a,
            batch=self.batch_bread,
            txn_type=StockTransaction.Type.SOLD,
            quantity=Decimal("20.000"),
            source="POS",
        )
        StockTransaction.objects.filter(id=t2.id).update(created_at=now)

        # 1. Filter category=Dairy
        res_dairy = self.client.get('/api/v1/inventory/sales/recent/?category=Dairy')
        self.assertEqual(res_dairy.status_code, status.HTTP_200_OK)
        today_dairy = [r for r in res_dairy.data if r['date'] == today.strftime('%Y-%m-%d')][0]
        self.assertEqual(today_dairy['units_sold'], 10.0)
        self.assertEqual(today_dairy['revenue'], 400.0)
        self.assertEqual(today_dairy['category'], 'Dairy')

        # 2. Filter category=Bakery
        res_bakery = self.client.get('/api/v1/inventory/sales/recent/?category=Bakery')
        self.assertEqual(res_bakery.status_code, status.HTTP_200_OK)
        today_bakery = [r for r in res_bakery.data if r['date'] == today.strftime('%Y-%m-%d')][0]
        self.assertEqual(today_bakery['units_sold'], 20.0)
        self.assertEqual(today_bakery['revenue'], 500.0)
        self.assertEqual(today_bakery['category'], 'Bakery')

        # 3. No category filter -> combined total
        res_all = self.client.get('/api/v1/inventory/sales/recent/')
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        today_all = [r for r in res_all.data if r['date'] == today.strftime('%Y-%m-%d')][0]
        self.assertEqual(today_all['units_sold'], 30.0)
        self.assertEqual(today_all['revenue'], 900.0)
        self.assertEqual(today_all['category'], 'All')

        # 4. Non-existent category -> zeroes, no 404
        res_none = self.client.get('/api/v1/inventory/sales/recent/?category=Seafood')
        self.assertEqual(res_none.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_none.data), 7)
        for r in res_none.data:
            self.assertEqual(r['units_sold'], 0.0)
            self.assertEqual(r['revenue'], 0.0)
            self.assertEqual(r['category'], 'Seafood')

    def test_custom_days_parameter(self):
        """Parameter ?days=14 and ?days=30 produce correct length sequences."""
        self.client.force_authenticate(user=self.user_a)

        res_14 = self.client.get('/api/v1/inventory/sales/recent/?days=14')
        self.assertEqual(res_14.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_14.data), 14)

        res_30 = self.client.get('/api/v1/inventory/sales/recent/?days=30')
        self.assertEqual(res_30.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_30.data), 30)

    def test_invalid_days_handled_cleanly(self):
        """Negative, zero, excessive, or non-integer days values return 400 Bad Request."""
        self.client.force_authenticate(user=self.user_a)

        for invalid_days in [-1, 0, 31, 1000, "abc", "1.5"]:
            response = self.client.get(f'/api/v1/inventory/sales/recent/?days={invalid_days}')
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Failed to reject days={invalid_days}",
            )
            self.assertIn('Query parameter "days" must be an integer between 1 and 30.', response.data['error'])

    def test_invalid_end_date_handled_cleanly(self):
        """Malformed end_date parameter returns 400 Bad Request."""
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get('/api/v1/inventory/sales/recent/?end_date=invalid-date')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Query parameter "end_date" must be in YYYY-MM-DD format.', response.data['error'])

    def test_zero_sales_day_fill_unbroken(self):
        """Sales occurring on non-consecutive days leave intervening days with 0s."""
        self.client.force_authenticate(user=self.user_a)
        today = timezone.localdate()
        two_days_ago = today - timedelta(days=2)
        four_days_ago = today - timedelta(days=4)

        t1 = StockTransaction.objects.create(
            organization=self.org_a,
            batch=self.batch_milk,
            txn_type=StockTransaction.Type.SOLD,
            quantity=Decimal("8.000"),
            source="POS",
        )
        StockTransaction.objects.filter(id=t1.id).update(
            created_at=timezone.make_aware(timezone.datetime.combine(four_days_ago, timezone.datetime.min.time()))
        )

        t2 = StockTransaction.objects.create(
            organization=self.org_a,
            batch=self.batch_milk,
            txn_type=StockTransaction.Type.SOLD,
            quantity=Decimal("12.000"),
            source="POS",
        )
        StockTransaction.objects.filter(id=t2.id).update(
            created_at=timezone.make_aware(timezone.datetime.combine(two_days_ago, timezone.datetime.min.time()))
        )

        response = self.client.get('/api/v1/inventory/sales/recent/?days=7')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data_by_date = {r['date']: r for r in response.data}

        # 4 days ago -> 8 units
        self.assertEqual(data_by_date[four_days_ago.strftime('%Y-%m-%d')]['units_sold'], 8.0)
        # 3 days ago -> 0 units (unbroken fill)
        three_days_ago = today - timedelta(days=3)
        self.assertEqual(data_by_date[three_days_ago.strftime('%Y-%m-%d')]['units_sold'], 0.0)
        self.assertEqual(data_by_date[three_days_ago.strftime('%Y-%m-%d')]['revenue'], 0.0)
        # 2 days ago -> 12 units
        self.assertEqual(data_by_date[two_days_ago.strftime('%Y-%m-%d')]['units_sold'], 12.0)
        # 1 day ago -> 0 units
        yesterday = today - timedelta(days=1)
        self.assertEqual(data_by_date[yesterday.strftime('%Y-%m-%d')]['units_sold'], 0.0)
