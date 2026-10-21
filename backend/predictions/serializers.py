"""Serializers for predictions API."""

from rest_framework import serializers


class PlanInputSerializer(serializers.Serializer):
    """Validates tenant purchase planner input parameters.

    Client can only provide category, planned quantity, and optional environmental context.
    Client cannot supply organization ID, which is strictly injected from the authenticated session.
    """
    category = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Food category (e.g. 'Produce', 'Bakery', 'Dairy', 'Meat', 'Prepared Food')",
    )
    planned_quantity = serializers.FloatField(
        required=True,
        min_value=0.01,
        help_text="Tentative planned order quantity (must be strictly greater than zero)",
    )
    promotion = serializers.BooleanField(
        required=False,
        default=None,
        allow_null=True,
        help_text="Whether promotional discounts are active (defaults to organization setting if omitted)",
    )
    weather = serializers.ChoiceField(
        choices=["Sunny", "Rainy", "Cloudy", "Hot", "Unknown"],
        required=False,
        default="Sunny",
        help_text="Expected weather conditions (defaults to 'Sunny')",
    )
    date = serializers.DateField(
        required=False,
        default=None,
        allow_null=True,
        help_text="Target calendar date in YYYY-MM-DD format (defaults to today)",
    )

    def validate_category(self, value: str) -> str:
        clean = (value or "").strip()
        if not clean:
            raise serializers.ValidationError("Category cannot be blank.")
        return clean

    def validate_planned_quantity(self, value: float) -> float:
        if value <= 0:
            raise serializers.ValidationError("Planned quantity must be strictly greater than zero.")
        return value
