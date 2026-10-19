from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import Organization, User
from administration.models import AdminAuditLog, Issue, log_admin_action
from inventory.models import Category, Product, Batch, StockTransaction
from marketplace.models import Listing, Claim, Rating


class AdminIdentityAndSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # 1. Platform Admin: is_staff=True, organization=None
        self.platform_admin = User.objects.create_user(
            username="admin_sys",
            email="admin@surplussync.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=False,
            organization=None,
        )

        # 2. Business Tenant & Owner
        self.business_org = Organization.objects.create(
            name="Grand Gateway Hotel",
            org_type=Organization.Type.BUSINESS,
            address="Bengaluru",
            is_verified=True,
        )
        self.business_owner = User.objects.create_user(
            username="biz_owner",
            email="biz_owner@hotel.com",
            password="BizPassword123!",
            organization=self.business_org,
            role=User.Role.OWNER,
            is_staff=False,
        )
        self.business_staff = User.objects.create_user(
            username="biz_staff",
            email="biz_staff@hotel.com",
            password="StaffPassword123!",
            organization=self.business_org,
            role=User.Role.STAFF,
            is_staff=False,
        )

        # 3. NGO Tenant & Owner
        self.ngo_org = Organization.objects.create(
            name="Feeding India",
            org_type=Organization.Type.NGO,
            address="Bengaluru",
            is_verified=False,
        )
        self.ngo_owner = User.objects.create_user(
            username="ngo_owner",
            email="ngo_owner@feedingindia.org",
            password="NgoPassword123!",
            organization=self.ngo_org,
            role=User.Role.OWNER,
            is_staff=False,
        )

        # 4. Competing Business Tenant
        self.other_biz_org = Organization.objects.create(
            name="Competitor Bistro",
            org_type=Organization.Type.BUSINESS,
            address="Bengaluru",
            is_verified=True,
        )

    # --- 1. Admin Endpoint Access Controls ---

    def test_unauthenticated_gets_401_on_admin_endpoint(self):
        """Unauthenticated requests to /api/v1/admin/ endpoints must return 401."""
        res_ping = self.client.get("/api/v1/admin/ping/")
        self.assertEqual(res_ping.status_code, status.HTTP_401_UNAUTHORIZED)

        res_logs = self.client.get("/api/v1/admin/audit-logs/")
        self.assertEqual(res_logs.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_gets_403_on_admin_endpoint(self):
        """Business and NGO users (even OWNERs) get 403 on /api/v1/admin/ endpoints."""
        for user in [self.business_owner, self.business_staff, self.ngo_owner]:
            self.client.force_authenticate(user=user)
            res = self.client.get("/api/v1/admin/ping/")
            self.assertEqual(
                res.status_code,
                status.HTTP_403_FORBIDDEN,
                f"User {user.username} should have received 403 on /api/v1/admin/ping/",
            )

    def test_staff_with_organization_cannot_access_admin_endpoint(self):
        """A user with is_staff=True but belonging to an organization is NOT a platform admin."""
        rogue_user = User.objects.create_user(
            username="rogue_staff",
            email="rogue@hotel.com",
            password="RoguePassword123!",
            organization=self.business_org,
            role=User.Role.OWNER,
            is_staff=True,  # Tampered or set, but has organization
        )
        self.assertFalse(rogue_user.is_platform_admin)

        self.client.force_authenticate(user=rogue_user)
        res = self.client.get("/api/v1/admin/ping/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_can_access_admin_endpoint(self):
        """A platform admin (is_staff=True, organization=None) receives 200 on /api/v1/admin/."""
        self.assertTrue(self.platform_admin.is_platform_admin)
        self.client.force_authenticate(user=self.platform_admin)

        res = self.client.get("/api/v1/admin/ping/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data.get("is_platform_admin"), True)
        self.assertEqual(res.data.get("admin"), "admin_sys")

    def test_me_serializer_exposes_is_platform_admin(self):
        """GET /api/v1/accounts/me/ must expose is_platform_admin boolean."""
        # Platform admin
        self.client.force_authenticate(user=self.platform_admin)
        res_admin = self.client.get("/api/v1/accounts/me/")
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        self.assertEqual(res_admin.data["is_platform_admin"], True)
        self.assertIsNone(res_admin.data["organization"])

        # Business user
        self.client.force_authenticate(user=self.business_owner)
        res_biz = self.client.get("/api/v1/accounts/me/")
        self.assertEqual(res_biz.status_code, status.HTTP_200_OK)
        self.assertEqual(res_biz.data["is_platform_admin"], False)
        self.assertIsNotNone(res_biz.data["organization"])

    # --- 2. Organization Leaks and Escalation Fixes ---

    def test_unauthenticated_user_cannot_list_organizations(self):
        """GET /api/v1/accounts/organizations/ without auth must return 401, not leak all orgs."""
        res = self.client.get("/api/v1/accounts/organizations/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_normal_user_cannot_list_other_organizations(self):
        """A tenant user only sees their own organization, never others."""
        self.client.force_authenticate(user=self.business_owner)
        res = self.client.get("/api/v1/accounts/organizations/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Handle pagination or list
        results = res.data.get("results", res.data) if isinstance(res.data, dict) else res.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.business_org.id)

        # Trying to retrieve competitor organization returns 404
        res_other = self.client.get(f"/api/v1/accounts/organizations/{self.other_biz_org.id}/")
        self.assertEqual(res_other.status_code, status.HTTP_404_NOT_FOUND)

    def test_org_owner_cannot_edit_is_verified(self):
        """An organization owner cannot set is_verified=True on their own organization."""
        self.assertFalse(self.ngo_org.is_verified)
        self.client.force_authenticate(user=self.ngo_owner)

        res = self.client.patch(
            f"/api/v1/accounts/organizations/{self.ngo_org.id}/",
            {"is_verified": True, "name": "Feeding India Updated"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.ngo_org.refresh_from_db()
        self.assertFalse(self.ngo_org.is_verified, "is_verified must remain False!")
        self.assertEqual(self.ngo_org.name, "Feeding India Updated")

    def test_normal_user_cannot_create_arbitrary_organizations(self):
        """POST /api/v1/accounts/organizations/ by a normal user must be forbidden (403)."""
        self.client.force_authenticate(user=self.business_owner)
        res = self.client.post(
            "/api/v1/accounts/organizations/",
            {"name": "Illegal Org", "org_type": "BUSINESS"},
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # --- 3. User Leaks and Cross-Tenant Creation Fixes ---

    def test_normal_user_cannot_create_user_in_another_tenant(self):
        """POST /api/v1/accounts/users/ must ignore client-sent organization and lock to requester's org."""
        self.client.force_authenticate(user=self.business_owner)

        payload = {
            "username": "new_hire_user",
            "email": "newhire@hotel.com",
            "first_name": "New",
            "last_name": "Hire",
            "organization": self.other_biz_org.id,  # Trying to insert into competitor
            "role": "STAFF",
        }
        res = self.client.post("/api/v1/accounts/users/", payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        created_user = User.objects.get(username="new_hire_user")
        # Must be bound to business_org, NOT other_biz_org
        self.assertEqual(created_user.organization_id, self.business_org.id)
        self.assertFalse(created_user.is_staff)
        self.assertFalse(created_user.is_superuser)

    def test_org_owner_cannot_escalate_themselves_to_is_staff(self):
        """PATCH /api/v1/accounts/users/<id>/ must ignore is_staff and is_superuser."""
        self.client.force_authenticate(user=self.business_owner)

        res = self.client.patch(
            f"/api/v1/accounts/users/{self.business_owner.id}/",
            {"is_staff": True, "is_superuser": True},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.business_owner.refresh_from_db()
        self.assertFalse(self.business_owner.is_staff)
        self.assertFalse(self.business_owner.is_superuser)

    def test_registration_ignores_privilege_escalation_payloads(self):
        """Registering with is_staff, is_superuser, role, or is_verified in the payload ignores them."""
        payload = {
            "username": "escalated_user",
            "email": "escalated@test.com",
            "password": "SecurePassword123!",
            "org_name": "Exploit Bakery",
            "org_type": "BUSINESS",
            "is_staff": True,
            "is_superuser": True,
            "is_verified": True,
            "role": "PLATFORM_ADMIN",
        }
        res = self.client.post("/api/v1/accounts/register/", payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        new_user = User.objects.get(username="escalated_user")
        self.assertFalse(new_user.is_staff)
        self.assertFalse(new_user.is_superuser)
        self.assertEqual(new_user.role, User.Role.OWNER)
        self.assertFalse(new_user.organization.is_verified)
        self.assertFalse(new_user.is_platform_admin)

    # --- 4. AdminAuditLog Append-Only Invariants ---

    def test_admin_audit_log_records_write_action(self):
        """log_admin_action records an audit log row that platform admins can list."""
        log_entry = log_admin_action(
            admin_user=self.platform_admin,
            action="VERIFY_ORG",
            target_type="Organization",
            target_id=self.ngo_org.id,
            details={"note": "Official 80G tax registration verified."},
        )
        self.assertIsNotNone(log_entry.id)
        self.assertEqual(log_entry.admin_user, self.platform_admin)
        self.assertEqual(log_entry.action, "VERIFY_ORG")

        # Admin can view logs
        self.client.force_authenticate(user=self.platform_admin)
        res = self.client.get("/api/v1/admin/audit-logs/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get("results", res.data) if isinstance(res.data, dict) else res.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "VERIFY_ORG")
        self.assertEqual(results[0]["admin_username"], "admin_sys")

    def test_admin_audit_log_is_append_only(self):
        """AdminAuditLog rows cannot be updated or deleted."""
        log_entry = log_admin_action(
            admin_user=self.platform_admin,
            action="SUSPEND_ORG",
            target_type="Organization",
            target_id=self.business_org.id,
            details={"reason": "Food safety audit violation."},
        )

        # Attempting save/edit raises PermissionError
        log_entry.action = "TAMPERED_ACTION"
        with self.assertRaises(PermissionError):
            log_entry.save()

        # Attempting delete raises PermissionError
        with self.assertRaises(PermissionError):
            log_entry.delete()


class NgoVerificationAndOrganizationAdminTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Admin user
        self.platform_admin = User.objects.create_user(
            username="admin_kiran",
            email="kiran@surplussync.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=False,
            organization=None,
        )

        # Business Org & Users
        self.biz_org = Organization.objects.create(
            name="Taj West End",
            org_type=Organization.Type.BUSINESS,
            address="Race Course Rd, Bengaluru",
            phone="+918012345678",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.biz_owner = User.objects.create_user(
            username="taj_chef",
            email="chef@tajwestend.com",
            password="BizPassword123!",
            organization=self.biz_org,
            role=User.Role.OWNER,
        )

        # NGO Org & Users (Pending)
        self.ngo_org = Organization.objects.create(
            name="Robin Hood Army Bengaluru",
            org_type=Organization.Type.NGO,
            address="Koramangala, Bengaluru",
            phone="+919876543210",
            is_verified=False,
            verification_status=Organization.VerificationStatus.PENDING,
        )
        self.ngo_owner = User.objects.create_user(
            username="rha_lead",
            email="lead@robinhoodarmy.org",
            password="NgoPassword123!",
            organization=self.ngo_org,
            role=User.Role.OWNER,
        )

        # Clear test outbox
        mail.outbox = []

    def test_admin_organizations_list_and_filters(self):
        self.client.force_authenticate(user=self.platform_admin)

        # List all
        res = self.client.get("/api/v1/admin/organizations/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 2)

        # Filter by org_type=NGO
        res = self.client.get("/api/v1/admin/organizations/?org_type=NGO")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["name"], "Robin Hood Army Bengaluru")
        self.assertEqual(res.data["results"][0]["users_count"], 1)

        # Filter by is_verified=false
        res = self.client.get("/api/v1/admin/organizations/?is_verified=false")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)

        # Filter by verification_status=PENDING
        res = self.client.get("/api/v1/admin/organizations/?verification_status=PENDING")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)

        # Search by name
        res = self.client.get("/api/v1/admin/organizations/?search=Robin")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)

    def test_admin_organization_detail_and_recent_activity(self):
        self.client.force_authenticate(user=self.platform_admin)
        res = self.client.get(f"/api/v1/admin/organizations/{self.ngo_org.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], self.ngo_org.id)
        self.assertEqual(res.data["name"], "Robin Hood Army Bengaluru")
        self.assertIn("users", res.data)
        self.assertEqual(len(res.data["users"]), 1)
        self.assertEqual(res.data["users"][0]["username"], "rha_lead")
        self.assertIn("recent_activity", res.data)
        self.assertIn("claims", res.data["recent_activity"])
        self.assertIn("audit_logs", res.data["recent_activity"])

    def test_verify_organization_lifecycle(self):
        self.client.force_authenticate(user=self.platform_admin)
        res = self.client.post(
            f"/api/v1/admin/organizations/{self.ngo_org.id}/verify/",
            {"note": "Govt trust deed and 80G verified."},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.ngo_org.refresh_from_db()
        self.assertEqual(self.ngo_org.verification_status, Organization.VerificationStatus.VERIFIED)
        self.assertTrue(self.ngo_org.is_verified)
        self.assertIsNotNone(self.ngo_org.verified_at)
        self.assertEqual(self.ngo_org.verification_note, "Govt trust deed and 80G verified.")

        # Check Audit Log
        audit = AdminAuditLog.objects.filter(target_type="Organization", target_id=str(self.ngo_org.id)).latest("created_at")
        self.assertEqual(audit.action, "ORGANIZATION_VERIFY")
        self.assertEqual(audit.admin_user, self.platform_admin)

        # Check Email Notification
        self.assertGreaterEqual(len(mail.outbox), 1)
        email = mail.outbox[-1]
        self.assertIn("Verified", email.subject)
        self.assertIn("lead@robinhoodarmy.org", email.to)

    def test_reject_organization_requires_reason(self):
        self.client.force_authenticate(user=self.platform_admin)
        # Without reason -> 400
        res = self.client.post(
            f"/api/v1/admin/organizations/{self.ngo_org.id}/reject/",
            {},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", res.data)

        # With reason -> 200
        res = self.client.post(
            f"/api/v1/admin/organizations/{self.ngo_org.id}/reject/",
            {"reason": "Document registration number mismatch."},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.ngo_org.refresh_from_db()
        self.assertEqual(self.ngo_org.verification_status, Organization.VerificationStatus.REJECTED)
        self.assertFalse(self.ngo_org.is_verified)
        self.assertEqual(self.ngo_org.verification_note, "Document registration number mismatch.")

        # Check Audit Log
        audit = AdminAuditLog.objects.filter(target_type="Organization", target_id=str(self.ngo_org.id)).latest("created_at")
        self.assertEqual(audit.action, "ORGANIZATION_REJECT")

        # Check Email Notification
        self.assertGreaterEqual(len(mail.outbox), 1)
        email = mail.outbox[-1]
        self.assertIn("Rejected", email.subject)
        self.assertIn("Document registration number mismatch", email.body)

    def test_suspend_and_reinstate_organization(self):
        self.client.force_authenticate(user=self.platform_admin)

        # Suspend
        res = self.client.post(
            f"/api/v1/admin/organizations/{self.biz_org.id}/suspend/",
            {"reason": "Repeated hygiene safety warning."},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.biz_org.refresh_from_db()
        self.assertEqual(self.biz_org.verification_status, Organization.VerificationStatus.SUSPENDED)
        self.assertFalse(self.biz_org.is_verified)

        audit_suspend = AdminAuditLog.objects.filter(target_type="Organization", target_id=str(self.biz_org.id)).latest("created_at")
        self.assertEqual(audit_suspend.action, "ORGANIZATION_SUSPEND")

        # Reinstate
        res = self.client.post(
            f"/api/v1/admin/organizations/{self.biz_org.id}/reinstate/",
            {"reason": "Passed health inspection reinspection."},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.biz_org.refresh_from_db()
        self.assertEqual(self.biz_org.verification_status, Organization.VerificationStatus.VERIFIED)
        self.assertTrue(self.biz_org.is_verified)

        audit_reinstate = AdminAuditLog.objects.filter(target_type="Organization", target_id=str(self.biz_org.id)).latest("created_at")
        self.assertEqual(audit_reinstate.action, "ORGANIZATION_REINSTATE")

    def test_suspended_organization_cannot_login(self):
        self.biz_org.verification_status = Organization.VerificationStatus.SUSPENDED
        self.biz_org.save()

        # Login attempt
        res = self.client.post(
            "/api/v1/accounts/login/",
            {"username": "taj_chef", "password": "BizPassword123!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("suspended", str(res.data).lower())

    def test_suspended_organization_cannot_list_or_claim_food(self):
        # 1. Suspended business cannot list food
        self.biz_org.verification_status = Organization.VerificationStatus.SUSPENDED
        self.biz_org.save()

        self.client.force_authenticate(user=self.biz_owner)
        res = self.client.post(
            "/api/v1/marketplace/listings/",
            {
                "title": "Fresh surplus biryani",
                "quantity": "25.000",
                "pickup_window_start": timezone.now().isoformat(),
                "pickup_window_end": (timezone.now() + timezone.timedelta(hours=4)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("suspended", str(res.data).lower())

        # 2. Suspended NGO cannot claim food
        # Create an open listing first
        self.biz_org.verification_status = Organization.VerificationStatus.VERIFIED
        self.biz_org.save()
        listing = Listing.objects.create(
            donor=self.biz_org,
            title="Rice & curry",
            quantity=10,
            pickup_window_start=timezone.now(),
            pickup_window_end=timezone.now() + timezone.timedelta(hours=2),
            status=Listing.Status.OPEN,
        )

        self.ngo_org.verification_status = Organization.VerificationStatus.SUSPENDED
        self.ngo_org.save()

        self.client.force_authenticate(user=self.ngo_owner)
        res = self.client.post(
            "/api/v1/marketplace/claims/",
            {"listing": listing.id, "notes": "Picking up in 30 mins"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("suspended", str(res.data).lower())

    def test_non_admin_cannot_execute_verification_actions(self):
        # NGO owner attempts to verify themselves
        self.client.force_authenticate(user=self.ngo_owner)
        res = self.client.post(f"/api/v1/admin/organizations/{self.ngo_org.id}/verify/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Unauthenticated receives 401
        self.client.force_authenticate(user=None)
        res = self.client.post(f"/api/v1/admin/organizations/{self.ngo_org.id}/verify/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class IssueAndReportsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Platform Admin
        self.platform_admin = User.objects.create_user(
            username="admin_suresh",
            email="suresh@surplussync.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=False,
            organization=None,
        )

        # Business Org & Owner
        self.biz_org = Organization.objects.create(
            name="ITC Windsor",
            org_type=Organization.Type.BUSINESS,
            address="Sankey Rd, Bengaluru",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.biz_owner = User.objects.create_user(
            username="itc_manager",
            email="manager@itcwindsor.com",
            password="BizPassword123!",
            organization=self.biz_org,
            role=User.Role.OWNER,
        )

        # NGO Org & Owner
        self.ngo_org = Organization.objects.create(
            name="Feeding Bengaluru",
            org_type=Organization.Type.NGO,
            address="Indiranagar, Bengaluru",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.ngo_owner = User.objects.create_user(
            username="ngo_kavya",
            email="kavya@feedingbengaluru.org",
            password="NgoPassword123!",
            organization=self.ngo_org,
            role=User.Role.OWNER,
        )

        # Other Business (for tenant isolation check)
        self.other_biz_org = Organization.objects.create(
            name="Other Cafe",
            org_type=Organization.Type.BUSINESS,
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.other_biz_user = User.objects.create_user(
            username="other_cafe_user",
            email="user@othercafe.com",
            password="OtherPassword123!",
            organization=self.other_biz_org,
            role=User.Role.OWNER,
        )

        # A claim connecting biz_org and ngo_org
        self.listing = Listing.objects.create(
            donor=self.biz_org,
            title="15kg Cooked Rice & Dal",
            quantity=15,
            pickup_window_start=timezone.now(),
            pickup_window_end=timezone.now() + timezone.timedelta(hours=3),
            status=Listing.Status.COMPLETED,
        )
        self.claim = Claim.objects.create(
            listing=self.listing,
            ngo=self.ngo_org,
            status=Claim.Status.PICKED_UP,
        )

        mail.outbox = []

    def test_tenant_can_report_issue(self):
        self.client.force_authenticate(user=self.ngo_owner)

        res = self.client.post(
            "/api/v1/issues/",
            {
                "category": "FOOD_QUALITY",
                "description": "Food packaging was open and spoiled.",
                "claim": self.claim.id,
                # Try to spoof fields
                "reporter": self.platform_admin.id,
                "reporter_org": self.other_biz_org.id,
                "status": "RESOLVED",
                "priority": "HIGH",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.data
        self.assertEqual(data["category"], "FOOD_QUALITY")
        self.assertEqual(data["status"], "OPEN")  # forced OPEN
        self.assertEqual(data["reporter"], self.ngo_owner.id)  # forced authenticated user
        self.assertEqual(data["reporter_org"], self.ngo_org.id)  # forced authenticated user org
        self.assertEqual(data["target_org"], self.biz_org.id)  # auto-inferred from claim!

    def test_tenant_cannot_reference_unrelated_claim(self):
        # Create unrelated listing & claim
        unrelated_listing = Listing.objects.create(
            donor=self.other_biz_org,
            title="Unrelated bread",
            quantity=5,
            pickup_window_start=timezone.now(),
            pickup_window_end=timezone.now() + timezone.timedelta(hours=2),
        )
        unrelated_claim = Claim.objects.create(
            listing=unrelated_listing,
            ngo=self.ngo_org,  # Wait, let's make claim have a different NGO
        )
        other_ngo = Organization.objects.create(name="Third Party NGO", org_type=Organization.Type.NGO)
        unrelated_claim.ngo = other_ngo
        unrelated_claim.save()

        # self.biz_owner tries to claim issue on unrelated_claim
        self.client.force_authenticate(user=self.biz_owner)
        res = self.client.post(
            "/api/v1/issues/",
            {
                "category": "OTHER",
                "description": "Snooping on other claim",
                "claim": unrelated_claim.id,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("claim", res.data)

    def test_tenant_isolation_only_sees_own_issues(self):
        # NGO creates issue 1
        issue_ngo = Issue.objects.create(
            reporter=self.ngo_owner,
            reporter_org=self.ngo_org,
            target_org=self.biz_org,
            category=Issue.Category.NO_SHOW,
            description="Donor venue was locked on arrival.",
            status=Issue.Status.OPEN,
        )

        # Business creates issue 2
        issue_biz = Issue.objects.create(
            reporter=self.biz_owner,
            reporter_org=self.biz_org,
            target_org=self.ngo_org,
            category=Issue.Category.WRONG_QUANTITY,
            description="NGO claimed 50kg but vehicle only fit 10kg.",
            status=Issue.Status.OPEN,
        )

        # 1. NGO lists issues
        self.client.force_authenticate(user=self.ngo_owner)
        res = self.client.get("/api/v1/issues/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get("results", res.data) if isinstance(res.data, dict) else res.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], issue_ngo.id)

        # NGO tries to retrieve Business issue directly -> 404
        res = self.client.get(f"/api/v1/issues/{issue_biz.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # 2. Business lists issues
        self.client.force_authenticate(user=self.biz_owner)
        res = self.client.get("/api/v1/issues/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get("results", res.data) if isinstance(res.data, dict) else res.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], issue_biz.id)

        # Business tries to retrieve NGO issue directly -> 404
        res = self.client.get(f"/api/v1/issues/{issue_ngo.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_list_and_filters_issues(self):
        # Create diverse issues
        Issue.objects.create(
            reporter=self.ngo_owner,
            reporter_org=self.ngo_org,
            category=Issue.Category.FOOD_QUALITY,
            description="Quality issue in milk",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.HIGH,
        )
        Issue.objects.create(
            reporter=self.biz_owner,
            reporter_org=self.biz_org,
            category=Issue.Category.TECHNICAL,
            description="App crashed during scan",
            status=Issue.Status.RESOLVED,
            priority=Issue.Priority.LOW,
        )

        self.client.force_authenticate(user=self.platform_admin)

        # List all
        res = self.client.get("/api/v1/admin/issues/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 2)

        # Filter status=OPEN
        res = self.client.get("/api/v1/admin/issues/?status=OPEN")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["category"], "FOOD_QUALITY")

        # Filter category=TECHNICAL
        res = self.client.get("/api/v1/admin/issues/?category=TECHNICAL")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)

        # Filter priority=HIGH
        res = self.client.get("/api/v1/admin/issues/?priority=HIGH")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)

    def test_admin_patch_workflow_audit_log_and_notification(self):
        issue = Issue.objects.create(
            reporter=self.ngo_owner,
            reporter_org=self.ngo_org,
            target_org=self.biz_org,
            category=Issue.Category.FOOD_QUALITY,
            description="Cold chain broken",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.MEDIUM,
        )

        self.client.force_authenticate(user=self.platform_admin)

        # 1. Update to IN_REVIEW with admin notes
        res = self.client.patch(
            f"/api/v1/admin/issues/{issue.id}/",
            {
                "status": "IN_REVIEW",
                "priority": "HIGH",
                "admin_notes": "Contacting ITC Windsor kitchen supervisor.",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.IN_REVIEW)
        self.assertEqual(issue.priority, Issue.Priority.HIGH)
        self.assertEqual(issue.admin_notes, "Contacting ITC Windsor kitchen supervisor.")

        # Check Audit Log
        audit = AdminAuditLog.objects.filter(target_type="Issue", target_id=str(issue.id)).latest("created_at")
        self.assertEqual(audit.action, "ISSUE_UPDATE")
        self.assertEqual(audit.details["new_status"], "IN_REVIEW")

        # Check notification sent to reporter
        self.assertGreaterEqual(len(mail.outbox), 1)
        email = mail.outbox[-1]
        self.assertIn("IN_REVIEW", email.subject)
        self.assertIn("kavya@feedingbengaluru.org", email.to)

        # 2. Resolve issue
        mail.outbox.clear()
        res = self.client.patch(
            f"/api/v1/admin/issues/{issue.id}/",
            {
                "status": "RESOLVED",
                "admin_notes": "Supervisor confirmed replacement batch provided.",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.RESOLVED)
        self.assertEqual(issue.resolved_by, self.platform_admin)
        self.assertIsNotNone(issue.resolved_at)

        # Check resolution notification sent to reporter
        self.assertGreaterEqual(len(mail.outbox), 1)
        email2 = mail.outbox[-1]
        self.assertIn("RESOLVED", email2.subject)
        self.assertIn("kavya@feedingbengaluru.org", email2.to)

    def test_non_admin_cannot_access_admin_issues_endpoint(self):
        issue = Issue.objects.create(
            reporter=self.ngo_owner,
            reporter_org=self.ngo_org,
            category=Issue.Category.OTHER,
            description="General inquiry",
            status=Issue.Status.OPEN,
        )

        # Normal user gets 403 on GET /admin/issues/
        self.client.force_authenticate(user=self.ngo_owner)
        res = self.client.get("/api/v1/admin/issues/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Normal user gets 403 on PATCH /admin/issues/<id>/
        res = self.client.patch(f"/api/v1/admin/issues/{issue.id}/", {"status": "RESOLVED"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Unauthenticated gets 401
        self.client.force_authenticate(user=None)
        res = self.client.get("/api/v1/admin/issues/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class RatingModerationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # 1. Platform Admin
        self.platform_admin = User.objects.create_user(
            username="admin_meera",
            email="meera@surplussync.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=False,
            organization=None,
        )

        # 2. Business Organization & Owner
        self.biz_org = Organization.objects.create(
            name="Taj West End Bengaluru",
            org_type=Organization.Type.BUSINESS,
            address="Race Course Rd, Bengaluru",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.biz_owner = User.objects.create_user(
            username="taj_admin_user",
            email="manager@tajwestend.com",
            password="BizPassword123!",
            organization=self.biz_org,
            role=User.Role.OWNER,
        )

        # 3. Other Business (no ratings yet)
        self.other_biz_org = Organization.objects.create(
            name="The Oberoi Bengaluru",
            org_type=Organization.Type.BUSINESS,
            address="MG Road, Bengaluru",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )

        # 4. NGOs
        self.ngo_1 = Organization.objects.create(
            name="Akshaya Patra Foundation",
            org_type=Organization.Type.NGO,
            address="Rajajinagar, Bengaluru",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.ngo_1_user = User.objects.create_user(
            username="akshaya_lead",
            email="lead@akshayapatra.org",
            password="NgoPassword123!",
            organization=self.ngo_1,
            role=User.Role.OWNER,
        )

        self.ngo_2 = Organization.objects.create(
            name="Robin Hood Army",
            org_type=Organization.Type.NGO,
            address="Indiranagar, Bengaluru",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )

        self.ngo_3 = Organization.objects.create(
            name="Goonj Bengaluru",
            org_type=Organization.Type.NGO,
            address="HSR Layout, Bengaluru",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )

        # Create Listings & Picked-up Claims for Ratings
        self.listing_1 = Listing.objects.create(
            donor=self.biz_org,
            title="40 Meals - Dal & Rice",
            quantity=40,
            pickup_window_start=timezone.now(),
            pickup_window_end=timezone.now() + timezone.timedelta(hours=2),
            status=Listing.Status.COMPLETED,
        )
        self.claim_1 = Claim.objects.create(
            listing=self.listing_1,
            ngo=self.ngo_1,
            status=Claim.Status.PICKED_UP,
        )
        self.rating_1 = Rating.objects.create(
            claim=self.claim_1,
            stars=5,
            comment="Outstanding food quality and hot packaging.",
            is_hidden=False,
        )

        self.listing_2 = Listing.objects.create(
            donor=self.biz_org,
            title="25 Meals - Sandwiches",
            quantity=25,
            pickup_window_start=timezone.now(),
            pickup_window_end=timezone.now() + timezone.timedelta(hours=2),
            status=Listing.Status.COMPLETED,
        )
        self.claim_2 = Claim.objects.create(
            listing=self.listing_2,
            ngo=self.ngo_2,
            status=Claim.Status.PICKED_UP,
        )
        self.rating_2 = Rating.objects.create(
            claim=self.claim_2,
            stars=3,
            comment="Decent sandwiches, slight pickup delay.",
            is_hidden=False,
        )

        self.listing_3 = Listing.objects.create(
            donor=self.biz_org,
            title="15kg Fresh Bakery Rolls",
            quantity=15,
            pickup_window_start=timezone.now(),
            pickup_window_end=timezone.now() + timezone.timedelta(hours=2),
            status=Listing.Status.COMPLETED,
        )
        self.claim_3 = Claim.objects.create(
            listing=self.listing_3,
            ngo=self.ngo_3,
            status=Claim.Status.PICKED_UP,
        )
        self.rating_3 = Rating.objects.create(
            claim=self.claim_3,
            stars=1,
            comment="Abusive language used by delivery guard.",
            is_hidden=True,
            hidden_reason="Investigating reported abuse claim.",
        )

    def test_admin_ratings_list_and_filters(self):
        self.client.force_authenticate(user=self.platform_admin)

        # 1. List all ratings
        res = self.client.get("/api/v1/admin/ratings/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 3)

        # 2. Filter by stars=5
        res = self.client.get("/api/v1/admin/ratings/?stars=5")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], self.rating_1.id)

        # 3. Filter by business
        res = self.client.get(f"/api/v1/admin/ratings/?business={self.biz_org.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 3)

        res = self.client.get(f"/api/v1/admin/ratings/?business={self.other_biz_org.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 0)

        # 4. Filter by ngo
        res = self.client.get(f"/api/v1/admin/ratings/?ngo={self.ngo_1.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["ngo_name"], "Akshaya Patra Foundation")

        # 5. Filter by is_hidden=true
        res = self.client.get("/api/v1/admin/ratings/?is_hidden=true")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], self.rating_3.id)
        self.assertTrue(res.data["results"][0]["is_hidden"])

        # 6. Filter by is_hidden=false
        res = self.client.get("/api/v1/admin/ratings/?is_hidden=false")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 2)

        # 7. Search query
        res = self.client.get("/api/v1/admin/ratings/?search=sandwiches")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], self.rating_2.id)

    def test_admin_hide_rating_requires_reason(self):
        self.client.force_authenticate(user=self.platform_admin)

        # Missing reason
        res = self.client.post(f"/api/v1/admin/ratings/{self.rating_1.id}/hide/", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", res.data)

        # Empty whitespace reason
        res = self.client.post(
            f"/api/v1/admin/ratings/{self.rating_1.id}/hide/",
            {"reason": "   "},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", res.data)

    def test_admin_hide_rating_success_and_audit_log(self):
        self.client.force_authenticate(user=self.platform_admin)

        reason_text = "Profanity detected in review."
        res = self.client.post(
            f"/api/v1/admin/ratings/{self.rating_1.id}/hide/",
            {"reason": reason_text},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_hidden"])
        self.assertEqual(res.data["hidden_reason"], reason_text)

        self.rating_1.refresh_from_db()
        self.assertTrue(self.rating_1.is_hidden)
        self.assertEqual(self.rating_1.hidden_reason, reason_text)

        # Verify Audit Log
        audit = AdminAuditLog.objects.filter(
            target_type="Rating",
            target_id=str(self.rating_1.id),
        ).latest("created_at")
        self.assertEqual(audit.action, "RATING_HIDE")
        self.assertEqual(audit.admin_user, self.platform_admin)
        self.assertEqual(audit.details["reason"], reason_text)
        self.assertEqual(audit.details["stars"], 5)

    def test_admin_unhide_rating_requires_reason(self):
        self.client.force_authenticate(user=self.platform_admin)

        # Missing reason
        res = self.client.post(f"/api/v1/admin/ratings/{self.rating_3.id}/unhide/", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", res.data)

    def test_admin_unhide_rating_success_and_audit_log(self):
        self.client.force_authenticate(user=self.platform_admin)

        unhide_reason = "Review verified as legitimate upon NGO dispute review."
        res = self.client.post(
            f"/api/v1/admin/ratings/{self.rating_3.id}/unhide/",
            {"reason": unhide_reason},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["is_hidden"])
        self.assertEqual(res.data["hidden_reason"], unhide_reason)

        self.rating_3.refresh_from_db()
        self.assertFalse(self.rating_3.is_hidden)
        self.assertEqual(self.rating_3.hidden_reason, unhide_reason)

        # Verify Audit Log
        audit = AdminAuditLog.objects.filter(
            target_type="Rating",
            target_id=str(self.rating_3.id),
        ).latest("created_at")
        self.assertEqual(audit.action, "RATING_UNHIDE")
        self.assertEqual(audit.admin_user, self.platform_admin)
        self.assertEqual(audit.details["reason"], unhide_reason)

    def test_admin_business_rating_summary_aggregates(self):
        self.client.force_authenticate(user=self.platform_admin)

        res = self.client.get(f"/api/v1/admin/businesses/{self.biz_org.id}/rating-summary/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        # self.biz_org has 3 ratings:
        # rating_1: 5 stars (active)
        # rating_2: 3 stars (active)
        # rating_3: 1 stars (hidden)
        # Non-hidden count: 2 (stars 5 and 3) -> avg = (5 + 3) / 2 = 4.0
        self.assertEqual(data["business_id"], self.biz_org.id)
        self.assertEqual(data["business_name"], "Taj West End Bengaluru")
        self.assertEqual(data["rating_avg"], 4.0)
        self.assertEqual(data["rating_count"], 2)
        self.assertEqual(data["total_count"], 3)
        self.assertEqual(data["hidden_count"], 1)

        # Breakdown checks
        breakdown = data["breakdown"]
        self.assertEqual(breakdown["5"], 1)
        self.assertEqual(breakdown["4"], 0)
        self.assertEqual(breakdown["3"], 1)
        self.assertEqual(breakdown["2"], 0)
        self.assertEqual(breakdown["1"], 0)  # 1-star was hidden, excluded from active breakdown

    def test_admin_business_rating_summary_zero_ratings(self):
        self.client.force_authenticate(user=self.platform_admin)

        res = self.client.get(f"/api/v1/admin/businesses/{self.other_biz_org.id}/rating-summary/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertEqual(data["business_id"], self.other_biz_org.id)
        self.assertIsNone(data["rating_avg"])
        self.assertEqual(data["rating_count"], 0)
        self.assertEqual(data["total_count"], 0)
        self.assertEqual(data["hidden_count"], 0)
        self.assertEqual(data["breakdown"]["5"], 0)

    def test_non_admin_cannot_access_rating_moderation_endpoints(self):
        # 1. Business user attempts access -> 403
        self.client.force_authenticate(user=self.biz_owner)

        res = self.client.get("/api/v1/admin/ratings/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.post(
            f"/api/v1/admin/ratings/{self.rating_1.id}/hide/",
            {"reason": "Attempted tamper"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.post(
            f"/api/v1/admin/ratings/{self.rating_3.id}/unhide/",
            {"reason": "Attempted tamper"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.get(f"/api/v1/admin/businesses/{self.biz_org.id}/rating-summary/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 2. NGO user attempts access -> 403
        self.client.force_authenticate(user=self.ngo_1_user)
        res = self.client.get("/api/v1/admin/ratings/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Unauthenticated -> 401
        self.client.force_authenticate(user=None)
        res = self.client.get("/api/v1/admin/ratings/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        res = self.client.get(f"/api/v1/admin/businesses/{self.biz_org.id}/rating-summary/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PlatformStatsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Platform Admin
        self.platform_admin = User.objects.create_user(
            username="admin_stats_user",
            email="statsadmin@surplussync.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=False,
            organization=None,
        )

        # 2 Businesses
        self.biz_1 = Organization.objects.create(
            name="ITC Gardenia",
            org_type=Organization.Type.BUSINESS,
            address="Residency Rd, Bengaluru",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.biz_1_user = User.objects.create_user(
            username="itc_chef",
            email="chef@itcgardenia.com",
            password="BizPassword123!",
            organization=self.biz_1,
            role=User.Role.OWNER,
        )

        self.biz_2 = Organization.objects.create(
            name="Daily Bread Bistro",
            org_type=Organization.Type.BUSINESS,
            address="Indiranagar, Bengaluru",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )

        # 2 NGOs: 1 VERIFIED, 1 PENDING
        self.ngo_verified = Organization.objects.create(
            name="Feeding India Bengaluru",
            org_type=Organization.Type.NGO,
            address="Koramangala, Bengaluru",
            is_verified=True,
            verification_status=Organization.VerificationStatus.VERIFIED,
        )
        self.ngo_user = User.objects.create_user(
            username="feeding_lead",
            email="lead@feedingindia.org",
            password="NgoPassword123!",
            organization=self.ngo_verified,
            role=User.Role.OWNER,
        )

        self.ngo_pending = Organization.objects.create(
            name="Hope Food Bank",
            org_type=Organization.Type.NGO,
            address="Whitefield, Bengaluru",
            phone="+919876543210",
            is_verified=False,
            verification_status=Organization.VerificationStatus.PENDING,
        )

        # Issues: 1 OPEN, 1 RESOLVED
        self.open_issue = Issue.objects.create(
            reporter=self.ngo_user,
            reporter_org=self.ngo_verified,
            target_org=self.biz_1,
            category=Issue.Category.FOOD_QUALITY,
            description="Chilling container broken during transport.",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.HIGH,
        )
        self.resolved_issue = Issue.objects.create(
            reporter=self.biz_1_user,
            reporter_org=self.biz_1,
            target_org=self.ngo_verified,
            category=Issue.Category.TECHNICAL,
            description="Resolved sync issue.",
            status=Issue.Status.RESOLVED,
            priority=Issue.Priority.LOW,
        )

        # Listings: 1 OPEN (active), 1 COMPLETED (35kg donated)
        self.active_listing = Listing.objects.create(
            donor=self.biz_1,
            title="Surplus Veg Biryani",
            quantity=20,
            pickup_window_start=timezone.now(),
            pickup_window_end=timezone.now() + timezone.timedelta(hours=2),
            status=Listing.Status.OPEN,
        )
        self.completed_listing = Listing.objects.create(
            donor=self.biz_1,
            title="Fresh Cut Fruit Platters",
            quantity=35,
            pickup_window_start=timezone.now(),
            pickup_window_end=timezone.now() + timezone.timedelta(hours=2),
            status=Listing.Status.COMPLETED,
        )

        # Inventory DONATED transaction: 15kg
        category = Category.objects.create(name="Produce", perishability_risk=Category.Risk.HIGH)
        product = Product.objects.create(organization=self.biz_1, name="Tomatoes", category=category)
        batch = Batch.objects.create(
            organization=self.biz_1,
            product=product,
            quantity=50,
            received_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timezone.timedelta(days=5),
        )
        StockTransaction.objects.create(
            organization=self.biz_1,
            batch=batch,
            txn_type=StockTransaction.Type.DONATED,
            quantity=15,
        )
        # Total kg donated = 35 + 15 = 50.0

        # Ratings: 5-star, 4-star (active) -> avg 4.5; 1-star (hidden)
        claim_1 = Claim.objects.create(
            listing=self.completed_listing,
            ngo=self.ngo_verified,
            status=Claim.Status.PICKED_UP,
        )
        Rating.objects.create(
            claim=claim_1,
            stars=5,
            comment="Excellent donations!",
            is_hidden=False,
        )

        claim_2 = Claim.objects.create(
            listing=self.active_listing,
            ngo=self.ngo_verified,
            status=Claim.Status.PICKED_UP,
        )
        Rating.objects.create(
            claim=claim_2,
            stars=4,
            comment="Very good food.",
            is_hidden=False,
        )

        claim_3 = Claim.objects.create(
            listing=Listing.objects.create(
                donor=self.biz_2,
                title="Baguettes",
                quantity=10,
                pickup_window_start=timezone.now(),
                pickup_window_end=timezone.now() + timezone.timedelta(hours=1),
                status=Listing.Status.COMPLETED,
            ),
            ngo=self.ngo_verified,
            status=Claim.Status.PICKED_UP,
        )
        Rating.objects.create(
            claim=claim_3,
            stars=1,
            comment="Spam review",
            is_hidden=True,
            hidden_reason="Spam",
        )

    def test_admin_stats_aggregations(self):
        self.client.force_authenticate(user=self.platform_admin)

        res = self.client.get("/api/v1/admin/stats/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        # 1. Total businesses: 2
        self.assertEqual(data["total_businesses"], 2)

        # 2. Total NGOs: 2
        self.assertEqual(data["total_ngos"], 2)

        # 3. Pending NGO verifications: 1
        self.assertEqual(data["pending_verifications"], 1)
        self.assertEqual(data["pending_ngo_verifications"], 1)

        # 4. Open issues: 1
        self.assertEqual(data["open_issues"], 1)

        # 5. Total kg donated: 35 (listing 1) + 10 (listing 3) + 15 (inventory transaction) = 60.0
        self.assertEqual(data["total_kg_donated"], 60.0)

        # 6. Active listings: 1
        self.assertEqual(data["active_listings"], 1)

        # 7. Average platform rating: (5 + 4) / 2 = 4.5 (excluding 1-star hidden)
        self.assertEqual(data["average_platform_rating"], 4.5)
        self.assertEqual(data["average_rating"], 4.5)
        self.assertEqual(data["total_ratings"], 2)

        # 8. Signups per week chart series
        self.assertIn("signups_per_week", data)
        self.assertIsInstance(data["signups_per_week"], list)
        self.assertGreaterEqual(len(data["signups_per_week"]), 1)
        first_bucket = data["signups_per_week"][0]
        self.assertIn("week", first_bucket)
        self.assertIn("label", first_bucket)
        self.assertIn("signups", first_bucket)
        self.assertIn("businesses", first_bucket)
        self.assertIn("ngos", first_bucket)

        # 9. Queues for Overview UI
        self.assertIn("needs_approval_queue", data)
        self.assertEqual(len(data["needs_approval_queue"]), 1)
        self.assertEqual(data["needs_approval_queue"][0]["name"], "Hope Food Bank")

        self.assertIn("open_issues_queue", data)
        self.assertEqual(len(data["open_issues_queue"]), 1)
        self.assertEqual(data["open_issues_queue"][0]["id"], self.open_issue.id)

    def test_admin_stats_zero_state(self):
        # Create an isolated admin with no other orgs
        fresh_admin = User.objects.create_user(
            username="fresh_admin",
            email="fresh@surplussync.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=False,
            organization=None,
        )
        # Clear other objects
        Rating.objects.all().delete()
        Claim.objects.all().delete()
        Listing.objects.all().delete()
        StockTransaction.objects.all().delete()
        Issue.objects.all().delete()
        Organization.objects.all().delete()

        self.client.force_authenticate(user=fresh_admin)
        res = self.client.get("/api/v1/admin/stats/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertEqual(data["total_businesses"], 0)
        self.assertEqual(data["total_ngos"], 0)
        self.assertEqual(data["pending_verifications"], 0)
        self.assertEqual(data["open_issues"], 0)
        self.assertEqual(data["active_listings"], 0)
        self.assertEqual(data["total_kg_donated"], 0.0)
        self.assertIsNone(data["average_platform_rating"])
        self.assertEqual(data["needs_approval_queue"], [])
        self.assertEqual(data["open_issues_queue"], [])

    def test_non_admin_cannot_access_stats(self):
        # 1. Business user -> 403
        self.client.force_authenticate(user=self.biz_1_user)
        res = self.client.get("/api/v1/admin/stats/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 2. NGO user -> 403
        self.client.force_authenticate(user=self.ngo_user)
        res = self.client.get("/api/v1/admin/stats/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Unauthenticated -> 401
        self.client.force_authenticate(user=None)
        res = self.client.get("/api/v1/admin/stats/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)




