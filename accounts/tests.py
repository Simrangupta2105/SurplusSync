from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import Organization, User
from inventory.models import Category, Product


class AccountsModelTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Green Valley Foods",
            org_type=Organization.Type.BUSINESS,
            phone="+1234567890",
            is_verified=True,
        )
        self.user = User.objects.create_user(
            username="manager1",
            email="manager1@example.com",
            password="securepassword123",
            organization=self.org,
            role=User.Role.OWNER,
        )

    def test_organization_created(self):
        self.assertEqual(str(self.org), "Green Valley Foods")
        self.assertEqual(self.org.org_type, Organization.Type.BUSINESS)
        self.assertTrue(self.org.is_verified)

    def test_user_tenant_association(self):
        self.assertEqual(self.user.organization, self.org)
        self.assertEqual(self.user.role, User.Role.OWNER)
        self.assertIn("manager1", str(self.user))


class AccountsAPITests(APITestCase):
    def test_registration_creates_org_and_owner(self):
        payload = {
            "username": "newowner",
            "email": "owner@example.com",
            "password": "StrongPassword123!",
            "org_name": "Sunrise Bakery",
            "org_type": "BUSINESS",
            "address": "123 Main St",
            "phone": "+1987654321",
        }
        res = self.client.post("/api/v1/accounts/register/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(User.objects.count(), 1)

        org = Organization.objects.get(name="Sunrise Bakery")
        user = User.objects.get(username="newowner")

        self.assertEqual(user.organization, org)
        self.assertEqual(user.role, User.Role.OWNER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(org.is_verified)

    def test_registration_ignores_privileged_fields(self):
        payload = {
            "username": "hackeruser",
            "email": "hacker@example.com",
            "password": "StrongPassword123!",
            "org_name": "Hacker Org",
            "org_type": "NGO",
            "role": "STAFF",
            "is_staff": True,
            "is_superuser": True,
            "is_verified": True,
        }
        res = self.client.post("/api/v1/accounts/register/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="hackeruser")
        org = Organization.objects.get(name="Hacker Org")

        self.assertEqual(user.role, User.Role.OWNER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(org.is_verified)

    def test_duplicate_username_rejected(self):
        org = Organization.objects.create(name="Existing Org", org_type=Organization.Type.BUSINESS)
        User.objects.create_user(username="taken_user", email="taken@example.com", password="Password123!", organization=org)

        # Attempt to register with uppercase/mixed case duplicate
        payload = {
            "username": "TAKEN_USER",
            "email": "another@example.com",
            "password": "Password123!",
            "org_name": "Another Org",
            "org_type": "BUSINESS",
        }
        res = self.client.post("/api/v1/accounts/register/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", res.data)

    def test_login_and_me_endpoints(self):
        org = Organization.objects.create(name="Login Org", org_type=Organization.Type.BUSINESS)
        User.objects.create_user(username="loginuser", email="login@example.com", password="SecurePassword123!", organization=org)

        # 401 without auth on /me/
        unauth_res = self.client.get("/api/v1/accounts/me/")
        self.assertEqual(unauth_res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Login
        login_res = self.client.post("/api/v1/accounts/login/", {
            "username": "loginuser",
            "password": "SecurePassword123!"
        }, format="json")
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_res.data)
        self.assertIn("refresh", login_res.data)

        access_token = login_res.data["access"]

        # Call /me/ with Bearer token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        me_res = self.client.get("/api/v1/accounts/me/")
        self.assertEqual(me_res.status_code, status.HTTP_200_OK)
        self.assertEqual(me_res.data["username"], "loginuser")
        self.assertEqual(me_res.data["organization"]["name"], "Login Org")

    def test_tenant_isolation_inventory(self):
        org_a = Organization.objects.create(name="Org A", org_type=Organization.Type.BUSINESS)
        user_a = User.objects.create_user(username="user_a", password="Password123!", organization=org_a)

        org_b = Organization.objects.create(name="Org B", org_type=Organization.Type.BUSINESS)
        category = Category.objects.create(name="Produce Test", perishability_risk=Category.Risk.HIGH)
        product_b = Product.objects.create(
            organization=org_b,
            name="Org B Apples",
            category=category,
            unit="kg"
        )

        # Authenticate as user from Org A
        self.client.force_authenticate(user=user_a)

        # List products - Org B's product must NOT be returned
        list_res = self.client.get("/api/v1/inventory/products/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        results = list_res.data.get("results", list_res.data)
        self.assertEqual(len(results), 0)

        # Detail product - Org B's product must return 404
        detail_res = self.client.get(f"/api/v1/inventory/products/{product_b.id}/")
        self.assertEqual(detail_res.status_code, status.HTTP_404_NOT_FOUND)
