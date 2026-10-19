"""
Tests for core asynchronous emailing service in SurplusSync.
Tests verify:
- In-memory outbox delivery (mail.outbox)
- Task serializability
- Transient error retry with exponential backoff
- Registration welcome email dispatch
- Daily expiry digest consolidation (1 digest per organization per run)
- Respecting organization.email_alerts_enabled and global EMAIL_ALERTS_ENABLED
- Administrative decision & issue notifications async dispatch
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Organization, User
from core.emailing import (
    send_email_task,
    send_expiry_digest_for_organization,
    send_notification_email_async,
    send_registration_welcome_email,
)
from inventory.models import Alert, AlertRule, Batch, Category, Product
from inventory.tasks import run_expiry_check


class AsyncEmailingTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.org = Organization.objects.create(
            name="Green Grocer",
            org_type=Organization.Type.BUSINESS,
            email_alerts_enabled=True,
        )
        self.user = User.objects.create_user(
            username="greengrocer_owner",
            email="owner@greengrocer.com",
            password="securepassword123",
            organization=self.org,
            role=User.Role.OWNER,
        )
        self.client = APIClient()

    def test_send_email_task_direct_success(self):
        """Worker task sends email via Django mailer and records into mail.outbox."""
        sent = send_email_task(
            subject="Test Subject",
            message="Test message body",
            recipient_list=["test@example.com"],
        )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Test Subject")
        self.assertEqual(mail.outbox[0].to, ["test@example.com"])
        self.assertIn("Test message body", mail.outbox[0].body)

    def test_send_email_task_empty_recipients_skipped(self):
        """Empty or whitespace recipients do not fail and send 0 messages."""
        sent = send_email_task(
            subject="Test Empty",
            message="Body",
            recipient_list=[],
        )
        self.assertEqual(sent, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_send_email_task_retries_on_transient_failure(self):
        """Task retries with backoff and succeeds on subsequent attempts."""
        call_count = 0

        def flaky_send_mail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionResetError("Temporary network reset")
            return 1

        with patch("core.emailing.send_mail", side_effect=flaky_send_mail):
            sent = send_email_task(
                subject="Retry Test",
                message="Body",
                recipient_list=["user@test.com"],
                max_retries=3,
                retry_backoff=0.01,
            )
            self.assertEqual(sent, 1)
            self.assertEqual(call_count, 2)

    def test_send_email_task_exhausts_retries(self):
        """When all retry attempts fail, the final exception is raised."""
        with patch("core.emailing.send_mail", side_effect=ConnectionError("Persistent connection failure")):
            with self.assertRaises(ConnectionError):
                send_email_task(
                    subject="Fail Test",
                    message="Body",
                    recipient_list=["user@test.com"],
                    max_retries=2,
                    retry_backoff=0.01,
                )

    def test_send_notification_email_async_queues_and_delivers(self):
        """Enqueuing through send_notification_email_async runs under test runner and populates outbox."""
        task_id = send_notification_email_async(
            subject="Async Subject",
            message="Async Body",
            recipient_list=["async@example.com"],
        )
        self.assertIsNotNone(task_id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Async Subject")
        self.assertEqual(mail.outbox[0].to, ["async@example.com"])

    def test_registration_triggers_welcome_email(self):
        """Creating an account via the register endpoint automatically delivers a welcome email."""
        payload = {
            "username": "fresh_bakery",
            "email": "fresh@bakery.org",
            "password": "strongPassword!123",
            "org_name": "Fresh Bakery",
            "org_type": "BUSINESS",
            "address": "100 Baker Street",
            "phone": "+1234567890",
        }
        res = self.client.post("/api/v1/accounts/register/", payload, format="json")
        self.assertEqual(res.status_code, 201)

        # Welcome email should be delivered to fresh@bakery.org
        welcome_emails = [e for e in mail.outbox if "Welcome to SurplusSync" in e.subject]
        self.assertEqual(len(welcome_emails), 1)
        welcome = welcome_emails[0]
        self.assertIn("fresh@bakery.org", welcome.to)
        self.assertIn("fresh_bakery", welcome.subject)
        self.assertIn("Fresh Bakery", welcome.body)

    def test_expiry_digest_consolidates_alerts_for_organization(self):
        """run_expiry_check dispatches exactly 1 consolidated digest email per organization."""
        cat, _ = Category.objects.get_or_create(name="Dairy", defaults={"storage_type": Category.Storage.CHILLED})
        prod1 = Product.objects.create(organization=self.org, name="Whole Milk", category=cat)
        prod2 = Product.objects.create(organization=self.org, name="Cheddar Cheese", category=cat)

        today = date.today()
        # Batch 1 expires tomorrow
        Batch.objects.create(
            organization=self.org,
            product=prod1,
            batch_code="BTH-001",
            quantity=Decimal("10"),
            received_date=today - timedelta(days=5),
            expiry_date=today + timedelta(days=1),
            status=Batch.Status.ACTIVE,
        )
        # Batch 2 expires in 3 days
        Batch.objects.create(
            organization=self.org,
            product=prod2,
            batch_code="BTH-002",
            quantity=Decimal("5"),
            received_date=today - timedelta(days=5),
            expiry_date=today + timedelta(days=3),
            status=Batch.Status.ACTIVE,
        )

        mail.outbox = []
        # Run expiry check
        res = run_expiry_check(days=7, organization=self.org)
        self.assertGreaterEqual(res["alerts_created"], 2)

        # Verify exactly 1 digest email was dispatched for this organization
        digest_emails = [e for e in mail.outbox if "Daily Expiry Digest" in e.subject]
        self.assertEqual(len(digest_emails), 1)

        digest = digest_emails[0]
        self.assertIn(self.user.email, digest.to)
        self.assertIn(self.org.name, digest.subject)
        self.assertIn("Whole Milk", digest.body)
        self.assertIn("Cheddar Cheese", digest.body)

    def test_expiry_digest_respects_email_alerts_enabled_flag(self):
        """When organization.email_alerts_enabled is False, no digest email is sent."""
        self.org.email_alerts_enabled = False
        self.org.save()

        cat, _ = Category.objects.get_or_create(name="Bakery", defaults={"storage_type": Category.Storage.AMBIENT})
        prod = Product.objects.create(organization=self.org, name="Sourdough Loaf", category=cat)
        today = date.today()
        Batch.objects.create(
            organization=self.org,
            product=prod,
            batch_code="BTH-BREAD",
            quantity=Decimal("12"),
            received_date=today - timedelta(days=2),
            expiry_date=today + timedelta(days=1),
            status=Batch.Status.ACTIVE,
        )

        mail.outbox = []
        run_expiry_check(days=7, organization=self.org)

        # No emails should be sent
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_ALERTS_ENABLED=False)
    def test_expiry_digest_respects_global_setting(self):
        """When EMAIL_ALERTS_ENABLED=False in settings, no digest email is sent."""
        cat, _ = Category.objects.get_or_create(name="Produce", defaults={"storage_type": Category.Storage.AMBIENT})
        prod = Product.objects.create(organization=self.org, name="Apples", category=cat)
        today = date.today()
        Batch.objects.create(
            organization=self.org,
            product=prod,
            batch_code="BTH-APPLES",
            quantity=Decimal("20"),
            received_date=today - timedelta(days=2),
            expiry_date=today + timedelta(days=1),
            status=Batch.Status.ACTIVE,
        )

        mail.outbox = []
        run_expiry_check(days=7, organization=self.org)
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_notifications_async_delivery(self):
        """notify_organization_decision sends async email via queue to active users."""
        from administration.notifications import notify_organization_decision

        mail.outbox = []
        notify_organization_decision(self.org, action="VERIFIED", reason="Documents approved")

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("Verified", msg.subject)
        self.assertIn("owner@greengrocer.com", msg.to)
        self.assertIn("Documents approved", msg.body)
