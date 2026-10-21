"""Unit tests for business segment mapping, promotional flag, and category taxonomy."""

from django.core.management import call_command
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from accounts.models import Organization, User
from accounts.serializers import MeSerializer, OrganizationSerializer
from inventory.models import Category


class BusinessSegmentAndTaxonomyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Load category fixture
        call_command("loaddata", "categories", verbosity=0)

    def setUp(self):
        self.business_org = Organization.objects.create(
            name="Urban Gourmet Bistro",
            org_type=Organization.Type.BUSINESS,
            business_segment=Organization.BusinessSegment.RESTAURANT,
            promotion_active=True,
            phone="+919876543210",
        )
        self.ngo_org = Organization.objects.create(
            name="Feeding Hope Food Bank",
            org_type=Organization.Type.NGO,
            phone="+919876543211",
        )
        self.user = User.objects.create_user(
            username="bistro_owner",
            email="owner@urbangourmet.test",
            password="SecurePassword456!",
            organization=self.business_org,
            role=User.Role.OWNER,
        )

    def test_business_segment_choices(self):
        """Verify all four operational business segments are supported and persist correctly."""
        segments = [
            Organization.BusinessSegment.RESTAURANT,
            Organization.BusinessSegment.SUPERMARKET,
            Organization.BusinessSegment.CAFETERIA,
            Organization.BusinessSegment.CLOUD_KITCHEN,
        ]
        for seg in segments:
            self.business_org.business_segment = seg
            self.business_org.save()
            self.business_org.refresh_from_db()
            self.assertEqual(self.business_org.business_segment, seg)

    def test_promotion_active_flag(self):
        """Verify promotion_active default and toggle."""
        fresh_org = Organization.objects.create(
            name="Default Cafe",
            org_type=Organization.Type.BUSINESS,
        )
        self.assertFalse(fresh_org.promotion_active)

        fresh_org.promotion_active = True
        fresh_org.save()
        fresh_org.refresh_from_db()
        self.assertTrue(fresh_org.promotion_active)

    def test_organization_serializer_accepts_business_segment_for_business(self):
        """Serializer allows valid segment and promotion for BUSINESS org."""
        serializer = OrganizationSerializer(
            instance=self.business_org,
            data={"business_segment": Organization.BusinessSegment.SUPERMARKET, "promotion_active": False},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.business_segment, Organization.BusinessSegment.SUPERMARKET)
        self.assertFalse(updated.promotion_active)

    def test_organization_serializer_rejects_segment_for_ngo(self):
        """Serializer forbids configuring business_segment on an NGO."""
        serializer = OrganizationSerializer(
            instance=self.ngo_org,
            data={"business_segment": Organization.BusinessSegment.RESTAURANT},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("business_segment", serializer.errors)
        self.assertIn("BUSINESS", str(serializer.errors["business_segment"]))

    def test_me_serializer_includes_segment_and_promotion(self):
        """MeSerializer provides business_segment and promotion_active in the organization block."""
        data = MeSerializer(self.user).data
        org_data = data.get("organization")
        self.assertIsNotNone(org_data)
        self.assertEqual(org_data["business_segment"], "Restaurant")
        self.assertTrue(org_data["promotion_active"])

    def test_category_hierarchy_produce_children(self):
        """Category taxonomy: Produce category contains Fruits and Vegetables as children."""
        produce = Category.objects.get(name="Produce")
        self.assertIsNone(produce.parent)

        child_names = set(produce.children.values_list("name", flat=True))
        self.assertIn("Fruits", child_names)
        self.assertIn("Vegetables", child_names)

        fruits = Category.objects.get(name="Fruits")
        self.assertEqual(fruits.parent, produce)
        self.assertEqual(fruits.storage_type, Category.Storage.CHILLED)

        vegetables = Category.objects.get(name="Vegetables")
        self.assertEqual(vegetables.parent, produce)
        self.assertEqual(vegetables.storage_type, Category.Storage.CHILLED)

    def test_category_prepared_food_exists(self):
        """Category taxonomy: Prepared Food exists as a critical chilled category."""
        prepared = Category.objects.get(name="Prepared Food")
        self.assertEqual(prepared.storage_type, Category.Storage.CHILLED)
        self.assertEqual(prepared.default_shelf_life_days, 2)
