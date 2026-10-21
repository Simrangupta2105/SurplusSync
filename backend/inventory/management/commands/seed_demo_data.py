"""Management command to seed realistic synthetic inventory ledgers (Track B).

Calibrated against empirical parameters in ml_service/config/calibration.yaml:
- Demand scale by business type (Supermarket, Restaurant, Cafeteria, Cloud Kitchen)
- Promotion lift and weather multipliers
- Category-level waste rates and waste reason mix
- Donation probability given waste (and strictly zero donation without waste)
- Shelf-life and storage temperature parameters
- Purchase/demand ratios

Includes:
- Day-of-week seasonality (weekend retail peaks)
- Festival and seasonal event multipliers (Diwali, New Year, Pongal)
- Mild secular trend and log-normal noise
- Strict ledger reconciliation:
  Received = Sold + Discarded + Donated + Remaining
- Safety guard: Refuses to overwrite existing data without --force
- Reproducibility via configurable random seed
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Organization
from inventory.models import Batch, Category, Product, StockTransaction, StorageLocation

try:
    import yaml
except ImportError:
    yaml = None


DEFAULT_CALIBRATION_FILE = Path(__file__).resolve().parents[4] / "ml_service" / "config" / "calibration.yaml"

# Festival date offsets (month, day, multiplier)
INDIAN_FESTIVALS = [
    (1, 14, 1.35),   # Pongal / Makar Sankranti
    (3, 14, 1.30),   # Holi
    (8, 15, 1.25),   # Independence Day
    (10, 20, 1.45),  # Dussehra / Navratri peak
    (11, 1, 1.50),   # Diwali peak
    (12, 25, 1.40),  # Christmas
    (12, 31, 1.50),  # New Year Eve
]


class Command(BaseCommand):
    help = "Seed calibrated demo inventory ledger data (Track B) reconciled to received = sold + discarded + donated + remaining."

    def add_arguments(self, parser):
        parser.add_argument(
            "--org-name",
            type=str,
            default="Fresh Harvest Supermarket",
            help="Name of the demo organization to seed (default: Fresh Harvest Supermarket).",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Number of historical days to generate (default: 90).",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducibility (default: 42).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force overwrite existing inventory data for the specified organization.",
        )
        parser.add_argument(
            "--calibration-file",
            type=str,
            default=str(DEFAULT_CALIBRATION_FILE),
            help="Path to calibration.yaml configuration file.",
        )

    def handle(self, *args, **options):
        org_name = options["org_name"]
        days_to_seed = options["days"]
        seed = options["seed"]
        force = options["force"]
        calib_path = Path(options["calibration_file"])

        self.stdout.write(f"Starting synthetic ledger generation for '{org_name}' ({days_to_seed} days, seed={seed})...")

        # 1. Load Calibration Configuration
        calib = self._load_calibration(calib_path)

        # 2. Organization Check & Guard
        with transaction.atomic():
            org, created = Organization.objects.get_or_create(
                name=org_name,
                defaults={
                    "org_type": Organization.Type.BUSINESS,
                    "address": "100 MG Road, Indiranagar, Bengaluru",
                    "latitude": Decimal("12.971600"),
                    "longitude": Decimal("77.594600"),
                    "phone": "+91 98765 43210",
                    "verification_status": Organization.VerificationStatus.VERIFIED,
                    "is_verified": True,
                    "timezone": "Asia/Kolkata",
                    "max_concurrent_pickups": 3,
                },
            )

            existing_products_count = Product.objects.filter(organization=org).count()
            existing_batches_count = Batch.objects.filter(organization=org).count()

            if (existing_products_count > 0 or existing_batches_count > 0) and not force:
                raise CommandError(
                    f"Existing inventory data found for organization '{org_name}' "
                    f"({existing_products_count} products, {existing_batches_count} batches). "
                    "Refusing to overwrite. Pass --force to replace demo data."
                )

            if force and (existing_products_count > 0 or existing_batches_count > 0):
                self.stdout.write(self.style.WARNING(f"Force flag detected. Purging existing inventory data for '{org_name}'..."))
                StockTransaction.objects.filter(organization=org).delete()
                Batch.objects.filter(organization=org).delete()
                Product.objects.filter(organization=org).delete()
                StorageLocation.objects.filter(organization=org).delete()

            # 3. Setup Storage Locations
            locations = self._setup_storage_locations(org)

            # 4. Setup Categories & Products
            products = self._setup_products(org, locations, calib)

            # 5. Generate Reconciled Ledger
            stats = self._generate_ledger(
                org=org,
                products=products,
                days=days_to_seed,
                seed=seed,
                calibration=calib,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded {stats['batches_created']} batches and {stats['txns_created']} transactions "
            f"across {len(products)} products.\n"
            f"Ledger reconciliation: Received={stats['total_received']} == "
            f"Sold({stats['total_sold']}) + Discarded({stats['total_discarded']}) + "
            f"Donated({stats['total_donated']}) + Remaining({stats['total_remaining']}) "
            f"[Discrepancy: {stats['reconciliation_discrepancy']}]"
        ))

    def _load_calibration(self, path: Path) -> Dict[str, Any]:
        """Load calibration YAML if present, otherwise fallback to empirical defaults."""
        if path.exists() and yaml is not None:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    calib = yaml.safe_load(f)
                self.stdout.write(f"Loaded empirical calibration from {path}")
                return calib
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed to parse {path} ({e}). Using built-in empirical defaults."))

        self.stdout.write(self.style.WARNING("Calibration YAML not found or PyYAML unavailable. Using empirical defaults."))
        return self._get_default_calibration()

    def _get_default_calibration(self) -> Dict[str, Any]:
        """Built-in empirical defaults computed directly from food_waste_dataset.csv."""
        return {
            "business_types": {
                "Supermarket": {"relative_scale": 1.4853, "mean_demand": 156.1},
                "Restaurant": {"relative_scale": 0.7938, "mean_demand": 83.43},
                "Cafeteria": {"relative_scale": 0.5981, "mean_demand": 62.86},
                "Cloud Kitchen": {"relative_scale": 0.9855, "mean_demand": 103.58},
            },
            "promotion": {"lift_multiplier": 1.3306},
            "weather": {
                "Sunny": {"multiplier": 1.0926},
                "Rainy": {"multiplier": 0.7302},
                "Cloudy": {"multiplier": 0.9747},
                "Hot": {"multiplier": 1.1347},
            },
            "categories": {
                "Bakery": {"waste_rate_of_remaining": 0.2817, "shelf_life_days": {"median": 3.0, "mean": 3.08}},
                "Dairy": {"waste_rate_of_remaining": 0.2114, "shelf_life_days": {"median": 7.0, "mean": 6.88}},
                "Fruits": {"waste_rate_of_remaining": 0.2398, "shelf_life_days": {"median": 5.0, "mean": 5.10}},
                "Meat": {"waste_rate_of_remaining": 0.2533, "shelf_life_days": {"median": 4.0, "mean": 4.12}},
                "Prepared Food": {"waste_rate_of_remaining": 0.3875, "shelf_life_days": {"median": 2.0, "mean": 2.15}},
                "Vegetables": {"waste_rate_of_remaining": 0.2223, "shelf_life_days": {"median": 5.0, "mean": 5.18}},
            },
            "donation": {"p_donation_given_waste": 0.2303, "p_donation_given_zero_waste": 0.0},
            "purchase_demand_ratio": {"mean": 1.205, "std": 0.264, "median": 1.143},
        }

    def _setup_storage_locations(self, org: Organization) -> Dict[str, StorageLocation]:
        """Create standard storage locations."""
        loc_fridge, _ = StorageLocation.objects.get_or_create(
            organization=org,
            name="Walk-in Chiller A",
            defaults={"storage_type": Category.Storage.CHILLED, "capacity": Decimal("1500.00")},
        )
        loc_shelf, _ = StorageLocation.objects.get_or_create(
            organization=org,
            name="Ambient Dry Shelf 1",
            defaults={"storage_type": Category.Storage.AMBIENT, "capacity": Decimal("2000.00")},
        )
        loc_freezer, _ = StorageLocation.objects.get_or_create(
            organization=org,
            name="Deep Freeze B",
            defaults={"storage_type": Category.Storage.FROZEN, "capacity": Decimal("800.00")},
        )
        return {"CHILLED": loc_fridge, "AMBIENT": loc_shelf, "FROZEN": loc_freezer}

    def _setup_products(
        self,
        org: Organization,
        locations: Dict[str, StorageLocation],
        calibration: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Create or match categories and products calibrated to dataset categories."""
        # Category taxonomy mapping
        cat_definitions = [
            ("Dairy", Category.Risk.HIGH, Category.Storage.CHILLED, 7, [
                ("Pasteurized Fresh Milk 1L", "MK-101", Decimal("65.00"), "L", locations["CHILLED"]),
                ("Greek Yogurt 400g", "YG-102", Decimal("120.00"), "pcs", locations["CHILLED"]),
                ("Artisan Cheddar Cheese", "CH-103", Decimal("350.00"), "kg", locations["CHILLED"]),
            ]),
            ("Bakery", Category.Risk.CRITICAL, Category.Storage.AMBIENT, 3, [
                ("Whole Wheat Sourdough Loaf", "BK-201", Decimal("80.00"), "pcs", locations["AMBIENT"]),
                ("Butter Croissant (Pack of 2)", "BK-202", Decimal("110.00"), "pcs", locations["AMBIENT"]),
            ]),
            ("Fruits", Category.Risk.HIGH, Category.Storage.CHILLED, 5, [
                ("Fresh Strawberries 250g", "FR-301", Decimal("140.00"), "pcs", locations["CHILLED"]),
                ("Organic Gala Apples", "FR-302", Decimal("180.00"), "kg", locations["CHILLED"]),
            ]),
            ("Vegetables", Category.Risk.HIGH, Category.Storage.CHILLED, 5, [
                ("Crisp Baby Spinach 200g", "VG-401", Decimal("50.00"), "pcs", locations["CHILLED"]),
                ("Vine Ripe Tomatoes", "VG-402", Decimal("40.00"), "kg", locations["CHILLED"]),
            ]),
            ("Meat", Category.Risk.CRITICAL, Category.Storage.CHILLED, 4, [
                ("Boneless Chicken Breast", "MT-501", Decimal("280.00"), "kg", locations["CHILLED"]),
                ("Fresh Lean Mutton Mince", "MT-502", Decimal("650.00"), "kg", locations["CHILLED"]),
            ]),
            ("Prepared Food", Category.Risk.CRITICAL, Category.Storage.CHILLED, 2, [
                ("Classic Caesar Salad Bowl", "PF-601", Decimal("190.00"), "pcs", locations["CHILLED"]),
                ("Paneer Butter Masala Meal Box", "PF-602", Decimal("220.00"), "pcs", locations["CHILLED"]),
            ]),
        ]

        product_items: List[Dict[str, Any]] = []

        for cat_name, risk_level, storage_type, default_shelf_life, prods in cat_definitions:
            category, _ = Category.objects.get_or_create(
                name=cat_name,
                defaults={
                    "perishability_risk": risk_level,
                    "storage_type": storage_type,
                    "default_shelf_life_days": default_shelf_life,
                },
            )

            # Extract calibrated shelf life
            cat_calib = calibration.get("categories", {}).get(cat_name, {})
            calib_shelf_life = int(round(cat_calib.get("shelf_life_days", {}).get("median", default_shelf_life)))
            waste_remaining_rate = float(cat_calib.get("waste_rate_of_remaining", 0.25))
            reason_mix = cat_calib.get("waste_reason_mix", {
                "Expired": 0.25,
                "Overproduction": 0.25,
                "Low Demand": 0.20,
                "Storage Issue": 0.05,
                "No Waste": 0.25,
            })

            for prod_name, sku, unit_cost, unit, loc in prods:
                product, _ = Product.objects.get_or_create(
                    organization=org,
                    sku=sku,
                    defaults={
                        "name": prod_name,
                        "category": category,
                        "unit": unit,
                        "unit_cost": unit_cost,
                        "reorder_level": Decimal("20.00"),
                        "is_active": True,
                    },
                )
                product_items.append({
                    "product": product,
                    "category_name": cat_name,
                    "location": loc,
                    "shelf_life_days": calib_shelf_life,
                    "waste_rate_remaining": waste_remaining_rate,
                    "waste_reason_mix": reason_mix,
                })

        return product_items

    def _generate_ledger(
        self,
        org: Organization,
        products: List[Dict[str, Any]],
        days: int,
        seed: int,
        calibration: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate timeline of batches and stock transactions with perfect reconciliation."""
        rng = random.Random(seed)
        today = date.today()
        start_date = today - timedelta(days=days)

        # Baseline business demand scale (Supermarket relative scale ~1.485)
        biz_scale = float(calibration.get("business_types", {}).get("Supermarket", {}).get("relative_scale", 1.485))
        promo_lift = float(calibration.get("promotion", {}).get("lift_multiplier", 1.33))
        p_donation_given_waste = float(calibration.get("donation", {}).get("p_donation_given_waste", 0.2303))

        total_received = Decimal("0")
        total_sold = Decimal("0")
        total_discarded = Decimal("0")
        total_donated = Decimal("0")
        total_remaining = Decimal("0")

        batches_to_create = []
        txns_to_create = []

        batch_counter = 1

        # Precompute day parameters
        date_list = [start_date + timedelta(days=d) for d in range(days)]

        for d_idx, current_date in enumerate(date_list):
            day_of_week = current_date.weekday()  # 0=Mon, 6=Sun
            month, day_of_month = current_date.month, current_date.day

            # 1. Weekday multiplier (Weekend retail lift: Fri=1.10, Sat=1.25, Sun=1.20)
            weekday_multiplier = {
                0: 0.90,  # Monday
                1: 0.92,  # Tuesday
                2: 0.95,  # Wednesday
                3: 0.98,  # Thursday
                4: 1.12,  # Friday
                5: 1.25,  # Saturday
                6: 1.18,  # Sunday
            }[day_of_week]

            # 2. Festival / Event multiplier
            festival_mult = 1.0
            for f_month, f_day, f_mult in INDIAN_FESTIVALS:
                if month == f_month and abs(day_of_month - f_day) <= 1:
                    festival_mult = max(festival_mult, f_mult)

            # 3. Weather multiplier
            weather_choice = rng.choices(["Sunny", "Rainy", "Cloudy", "Hot"], weights=[0.40, 0.20, 0.25, 0.15], k=1)[0]
            weather_mult = float(calibration.get("weather", {}).get(weather_choice, {}).get("multiplier", 1.0))

            # 4. Mild secular trend (+0.05% per day)
            trend_mult = 1.0 + (0.0005 * d_idx)

            for prod_info in products:
                prod = prod_info["product"]
                shelf_life = prod_info["shelf_life_days"]
                expiry_date = current_date + timedelta(days=shelf_life)
                waste_rem_rate = prod_info["waste_rate_remaining"]

                # Promotion flag (~18% probability)
                is_promo = bool(rng.random() < 0.18)
                promo_mult = promo_lift if is_promo else 1.0

                # Base demand: 25 to 50 base units * biz_scale * multipliers * noise
                base_demand = rng.uniform(25.0, 50.0) * biz_scale
                effective_demand = base_demand * weekday_multiplier * festival_mult * weather_mult * promo_mult * trend_mult
                # Mild log-normal noise
                noise = math.exp(rng.gauss(0.0, 0.12))
                effective_demand = max(5.0, effective_demand * noise)
                demand_units = round(effective_demand)

                # Purchase quantity: draw purchase/demand ratio from empirical distribution
                pd_ratio = rng.gauss(1.20, 0.15)
                pd_ratio = max(0.85, min(2.0, pd_ratio))
                purchase_qty = max(demand_units, round(demand_units * pd_ratio))

                # Sales cannot exceed purchase
                sold_qty = min(purchase_qty, demand_units)
                rem_stock = purchase_qty - sold_qty

                # Waste quantity from remaining stock
                if rem_stock > 0:
                    waste_ratio = max(0.05, min(0.95, rng.gauss(waste_rem_rate, 0.06)))
                    waste_qty = min(rem_stock, max(1, round(rem_stock * waste_ratio)))
                else:
                    waste_qty = 0

                # Donation given waste
                if waste_qty > 0 and (rng.random() < p_donation_given_waste):
                    # Between 40% and 100% of waste units are donated
                    donated_qty = max(1, round(waste_qty * rng.uniform(0.40, 1.0)))
                    donated_qty = min(donated_qty, waste_qty)
                    discarded_qty = waste_qty - donated_qty
                else:
                    donated_qty = 0
                    discarded_qty = waste_qty

                # Reconcile shelf remaining:
                # remaining_on_shelf = purchase_qty - sold_qty - discarded_qty - donated_qty
                remaining_on_shelf = purchase_qty - sold_qty - discarded_qty - donated_qty
                assert remaining_on_shelf >= 0

                # Check if batch has expired relative to today
                is_expired = bool(expiry_date < today)
                if is_expired:
                    # If expired in the past, remaining stock was discarded on expiry
                    if remaining_on_shelf > 0:
                        discarded_qty += remaining_on_shelf
                        remaining_on_shelf = 0
                    batch_status = Batch.Status.DEPLETED
                else:
                    batch_status = Batch.Status.ACTIVE if remaining_on_shelf > 0 else Batch.Status.DEPLETED

                # Convert to Decimal for exact ledger tracking
                d_purchase = Decimal(str(purchase_qty))
                d_sold = Decimal(str(sold_qty))
                d_discarded = Decimal(str(discarded_qty))
                d_donated = Decimal(str(donated_qty))
                d_remaining = Decimal(str(remaining_on_shelf))

                # Invariant Verification: Received == Sold + Discarded + Donated + Remaining
                reconciled_sum = d_sold + d_discarded + d_donated + d_remaining
                if d_purchase != reconciled_sum:
                    raise ValueError(
                        f"RECONCILIATION VIOLATION for batch {batch_counter}: "
                        f"Purchase ({d_purchase}) != Sold ({d_sold}) + Discarded ({d_discarded}) + "
                        f"Donated ({d_donated}) + Remaining ({d_remaining})"
                    )

                total_received += d_purchase
                total_sold += d_sold
                total_discarded += d_discarded
                total_donated += d_donated
                total_remaining += d_remaining

                batch = Batch(
                    organization=org,
                    product=prod,
                    location=prod_info["location"],
                    batch_code=f"B-{current_date.strftime('%Y%m%d')}-{prod.sku}",
                    quantity=d_remaining,
                    reserved_quantity=Decimal("0.000"),
                    received_date=current_date,
                    expiry_date=expiry_date,
                    status=batch_status,
                )
                batches_to_create.append((batch, d_purchase, d_sold, d_discarded, d_donated, current_date))
                batch_counter += 1

        # Bulk create batches
        created_batches = Batch.objects.bulk_create([b[0] for b in batches_to_create], batch_size=500)

        # Create transactions for each batch
        for idx, (batch_info, d_purchase, d_sold, d_discarded, d_donated, txn_date) in enumerate(batches_to_create):
            saved_batch = created_batches[idx]

            # 1. RECEIVED txn
            txns_to_create.append(StockTransaction(
                organization=org,
                batch=saved_batch,
                txn_type=StockTransaction.Type.RECEIVED,
                quantity=d_purchase,
                reason="Initial calibrated stock receipt",
                source="SYSTEM_DEMO",
            ))

            # 2. SOLD txn
            if d_sold > 0:
                txns_to_create.append(StockTransaction(
                    organization=org,
                    batch=saved_batch,
                    txn_type=StockTransaction.Type.SOLD,
                    quantity=d_sold,
                    reason="Daily point-of-sale customer sales",
                    source="POS",
                ))

            # 3. DISCARDED txn
            if d_discarded > 0:
                reasons = list(prod_info["waste_reason_mix"].keys())
                probs = list(prod_info["waste_reason_mix"].values())
                # Filter out 'No Waste' for actual discard reason
                valid_reasons = [r for r in reasons if r != "No Waste"]
                valid_probs = [probs[reasons.index(r)] for r in valid_reasons]
                chosen_reason = rng.choices(valid_reasons, weights=valid_probs, k=1)[0]

                txns_to_create.append(StockTransaction(
                    organization=org,
                    batch=saved_batch,
                    txn_type=StockTransaction.Type.DISCARDED,
                    quantity=d_discarded,
                    reason=f"Waste: {chosen_reason}",
                    source="AUDIT",
                ))

            # 4. DONATED txn
            if d_donated > 0:
                txns_to_create.append(StockTransaction(
                    organization=org,
                    batch=saved_batch,
                    txn_type=StockTransaction.Type.DONATED,
                    quantity=d_donated,
                    reason="Surplus redistribution donation to NGO partner",
                    source="MARKETPLACE",
                ))

        created_txns = StockTransaction.objects.bulk_create(txns_to_create, batch_size=1000)

        reconciliation_discrepancy = total_received - (total_sold + total_discarded + total_donated + total_remaining)

        return {
            "batches_created": len(created_batches),
            "txns_created": len(created_txns),
            "total_received": float(total_received),
            "total_sold": float(total_sold),
            "total_discarded": float(total_discarded),
            "total_donated": float(total_donated),
            "total_remaining": float(total_remaining),
            "reconciliation_discrepancy": float(reconciliation_discrepancy),
        }
