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
from marketplace.models import (
    DonationRequest,
    NGORequirement,
    Rating,
    SurplusListing,
)

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
        parser.add_argument(
            "--seed-matching-history",
            action="store_true",
            help="Also seed synthetic matching history records (labeled [SYNTHETIC DEMO DATA]) for the learning layer.",
        )
        parser.add_argument(
            "--matching-requests-count",
            type=int,
            default=300,
            help="Number of synthetic matching donation requests to generate (default: 300).",
        )
        parser.add_argument(
            "--from-panel",
            type=str,
            default=None,
            help="Path to synthetic panel CSV to seed from (e.g. ml_service/data/raw/synthetic_panel_full.csv).",
        )
        parser.add_argument(
            "--org",
            type=str,
            default=None,
            help="ID or Name of the target Organization to seed.",
        )
        parser.add_argument(
            "--shops",
            type=str,
            default="S01",
            help="Comma-separated Shop_IDs from panel to seed into this organization (default: S01).",
        )
        parser.add_argument(
            "--last-days",
            type=int,
            default=None,
            help="Optional: Filter to only the last N calendar days of the synthetic panel.",
        )

    def handle(self, *args, **options):
        # Panel seeding path (Track B Task 7)
        if options.get("from_panel"):
            return self._seed_from_panel(options)

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

        # 6. Optional: Seed Synthetic Matching History for Learning Layer
        if options.get("seed_matching_history"):
            self.stdout.write("Generating synthetic matching history records labeled [SYNTHETIC DEMO DATA]...")
            matching_stats = seed_synthetic_matching_history(
                donor_org=org,
                count=options.get("matching_requests_count", 300),
                seed=seed,
                days=days_to_seed,
                stdout_write=self.stdout.write,
            )
            self.stdout.write(self.style.SUCCESS(
                f"Synthetic matching history seeded: {matching_stats['total']} requests "
                f"({matching_stats['completed']} completed, {matching_stats['rejected']} rejected, "
                f"{matching_stats['no_show']} no-show, {matching_stats['expired']} expired)."
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

        # Ensure historical created_at timestamp matches batch received_date
        # (Django's auto_now_add=True stamps bulk_create with today's timestamp by default)
        for saved_b in created_batches:
            if saved_b.received_date:
                dt = timezone.make_aware(datetime.combine(saved_b.received_date, datetime.min.time().replace(hour=12)))
                StockTransaction.objects.filter(batch=saved_b).update(created_at=dt)

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

    def _seed_from_panel(self, options: Dict[str, Any]) -> None:
        """Seed demo inventory and transactions strictly from the synthetic panel dataset (Track B Task 7)."""
        import pandas as pd

        panel_path_str = options["from_panel"]
        panel_path = Path(panel_path_str)
        if not panel_path.exists():
            # Check relative to backend or workspace root
            workspace_root = Path(__file__).resolve().parents[4]
            alt_path = workspace_root / panel_path_str
            if alt_path.exists():
                panel_path = alt_path
            else:
                raise CommandError(f"Panel CSV file not found at {panel_path_str} or {alt_path}")

        org_identifier = options.get("org") or options.get("org_name")
        shops_arg = options.get("shops", "S01")
        target_shops = [s.strip() for s in shops_arg.split(",") if s.strip()]
        last_days = options.get("last_days")
        force = options.get("force", False)

        self.stdout.write(f"Loading synthetic panel from '{panel_path}' for shop(s) {target_shops}...")
        df = pd.read_csv(panel_path)
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
        df["Expiry_Date"] = pd.to_datetime(df["Expiry_Date"]).dt.date

        # Filter by shops
        df = df[df["Shop_ID"].isin(target_shops)].copy()
        if len(df) == 0:
            raise CommandError(f"No records found in panel '{panel_path.name}' for shop(s): {target_shops}")

        # Filter by last_days if specified
        max_date = df["Date"].max()
        if last_days is not None and last_days > 0:
            cutoff_date = max_date - timedelta(days=last_days)
            df = df[df["Date"] >= cutoff_date].copy()
            self.stdout.write(f"Filtered to last {last_days} days ({cutoff_date} to {max_date}): {len(df)} rows.")

        df = df.sort_values(["Date", "Shop_ID", "Food_Category"]).reset_index(drop=True)

        with transaction.atomic():
            # Resolve or create target Organization
            org = None
            if str(org_identifier).isdigit():
                org = Organization.objects.filter(pk=int(org_identifier)).first()
            if not org:
                org = Organization.objects.filter(name=org_identifier).first()

            first_row = df.iloc[0]
            lat = Decimal(str(round(first_row["Latitude"], 6)))
            lon = Decimal(str(round(first_row["Longitude"], 6)))
            note_tag = f"[DEMO DATA - SYNTHETIC PANEL] Seeded from {panel_path.name} (Shop: {shops_arg})"

            if not org:
                org = Organization.objects.create(
                    name=org_identifier,
                    org_type=Organization.Type.BUSINESS,
                    business_segment=first_row.get("Business_Type", "Supermarket"),
                    latitude=lat,
                    longitude=lon,
                    address=f"Shop {shops_arg}, Central Market",
                    verification_status=Organization.VerificationStatus.VERIFIED,
                    is_verified=True,
                    verification_note=note_tag,
                )
                self.stdout.write(f"Created demo organization '{org.name}' (ID: {org.id}).")
            else:
                org.latitude = lat
                org.longitude = lon
                if note_tag not in org.verification_note:
                    org.verification_note = f"{org.verification_note} {note_tag}".strip()
                org.save()

            # Guard against accidental overwrite without --force
            existing_txns = StockTransaction.objects.filter(organization=org).count()
            existing_batches = Batch.objects.filter(organization=org).count()

            if (existing_txns > 0 or existing_batches > 0) and not force:
                raise CommandError(
                    f"Organization '{org.name}' (ID: {org.id}) already has existing inventory data "
                    f"({existing_batches} batches, {existing_txns} transactions). "
                    "Refusing to overwrite without --force."
                )

            if force and (existing_txns > 0 or existing_batches > 0):
                self.stdout.write(self.style.WARNING(
                    f"--force provided. Purging existing batches & transactions for '{org.name}'..."
                ))
                StockTransaction.objects.filter(organization=org).delete()
                Batch.objects.filter(organization=org).delete()
                Product.objects.filter(organization=org).delete()
                StorageLocation.objects.filter(organization=org).delete()

            # Storage Locations
            loc_chilled, _ = StorageLocation.objects.get_or_create(
                organization=org,
                name="Cold Storage",
                defaults={"storage_type": Category.Storage.CHILLED, "capacity": Decimal("5000.00")},
            )
            loc_ambient, _ = StorageLocation.objects.get_or_create(
                organization=org,
                name="Ambient Warehouse",
                defaults={"storage_type": Category.Storage.AMBIENT, "capacity": Decimal("5000.00")},
            )
            loc_map = {"CHILLED": loc_chilled, "AMBIENT": loc_ambient}

            # Categories & Products mapping per (shop_id, food_category)
            cat_storage_risk = {
                "Bakery": (Category.Storage.AMBIENT, Category.Risk.CRITICAL, 3),
                "Dairy": (Category.Storage.CHILLED, Category.Risk.HIGH, 7),
                "Fruits": (Category.Storage.CHILLED, Category.Risk.HIGH, 5),
                "Meat": (Category.Storage.CHILLED, Category.Risk.CRITICAL, 4),
                "Prepared Food": (Category.Storage.CHILLED, Category.Risk.CRITICAL, 2),
                "Vegetables": (Category.Storage.CHILLED, Category.Risk.HIGH, 5),
            }

            product_map: Dict[Tuple[str, str], Product] = {}
            for s_id in target_shops:
                shop_slice = df[df["Shop_ID"] == s_id]
                for cat_name in shop_slice["Food_Category"].unique():
                    storage_t, risk_l, default_sl = cat_storage_risk.get(
                        cat_name, (Category.Storage.AMBIENT, Category.Risk.MEDIUM, 5)
                    )
                    category, _ = Category.objects.get_or_create(
                        name=cat_name,
                        defaults={
                            "perishability_risk": risk_l,
                            "storage_type": storage_t,
                            "default_shelf_life_days": default_sl,
                        },
                    )

                    cat_rows = shop_slice[shop_slice["Food_Category"] == cat_name]
                    unit_cost = Decimal(str(round(float(cat_rows["Unit_Cost_INR"].median()), 2)))
                    sku = f"SKU-{s_id}-{cat_name[:3].upper()}"

                    prod, _ = Product.objects.get_or_create(
                        organization=org,
                        sku=sku,
                        defaults={
                            "name": f"{s_id} {cat_name}",
                            "category": category,
                            "unit": "kg" if cat_name in ["Meat", "Fruits", "Vegetables"] else "pcs",
                            "unit_cost": unit_cost,
                            "is_active": True,
                        },
                    )
                    product_map[(s_id, cat_name)] = prod

            # Build Batches and Ledger Rows
            last_panel_date = max_date
            recent_expiry_cutoff = last_panel_date - timedelta(days=14)

            batches_to_create: List[Batch] = []
            txns_data: List[Tuple[Decimal, Decimal, Decimal, Decimal, Decimal, date, str]] = []

            total_received = Decimal("0")
            total_sold = Decimal("0")
            total_discarded = Decimal("0")
            total_donated = Decimal("0")
            total_adjusted = Decimal("0")
            total_remaining = Decimal("0")

            for idx, row in df.iterrows():
                s_id = row["Shop_ID"]
                cat_name = row["Food_Category"]
                prod = product_map[(s_id, cat_name)]
                rec_date = row["Date"]
                exp_date = row["Expiry_Date"]

                p_qty = Decimal(str(row["Purchase_Quantity"]))
                s_qty = Decimal(str(row["Units_Sold"]))
                d_donated = Decimal(str(row["Donated_Units"]))
                w_qty = Decimal(str(row["Waste_Quantity"]))
                d_discarded = Decimal(str(w_qty - d_donated))
                carried_qty = Decimal(str(row["Carried_Forward_Units"]))

                # Carried Forward Units handling:
                # Keep active if expiry is within last 14 days or in future relative to last panel date
                if exp_date >= recent_expiry_cutoff:
                    batch_remaining = carried_qty
                    adj_qty = Decimal("0")
                    batch_status = Batch.Status.ACTIVE if batch_remaining > 0 else Batch.Status.DEPLETED
                else:
                    batch_remaining = Decimal("0")
                    adj_qty = carried_qty
                    batch_status = Batch.Status.EXPIRED if exp_date < last_panel_date else Batch.Status.DEPLETED

                # Invariant Verification: Received == Sold + Discarded + Donated + Adjusted + Remaining
                reconciled = s_qty + d_discarded + d_donated + adj_qty + batch_remaining
                if p_qty != reconciled:
                    raise ValueError(
                        f"Reconciliation error on row {idx} ({s_id} {cat_name} {rec_date}): "
                        f"Purchase {p_qty} != {reconciled} "
                        f"(S={s_qty}, Disc={d_discarded}, Don={d_donated}, Adj={adj_qty}, Rem={batch_remaining})"
                    )

                total_received += p_qty
                total_sold += s_qty
                total_discarded += d_discarded
                total_donated += d_donated
                total_adjusted += adj_qty
                total_remaining += batch_remaining

                loc = loc_map["CHILLED"] if prod.category.storage_type == Category.Storage.CHILLED else loc_map["AMBIENT"]

                batch = Batch(
                    organization=org,
                    product=prod,
                    location=loc,
                    batch_code=f"BP-{s_id}-{cat_name[:3].upper()}-{rec_date.strftime('%Y%m%d')}",
                    quantity=batch_remaining,
                    reserved_quantity=Decimal("0.000"),
                    received_date=rec_date,
                    expiry_date=exp_date,
                    status=batch_status,
                )
                batches_to_create.append(batch)
                txns_data.append((p_qty, s_qty, d_discarded, d_donated, adj_qty, rec_date, str(row.get("Waste_Reason", "Spoilage"))))

            # Bulk create batches
            created_batches = Batch.objects.bulk_create(batches_to_create, batch_size=1000)

            # Build transactions
            txns_to_create: List[StockTransaction] = []
            for b_idx, saved_b in enumerate(created_batches):
                p_qty, s_qty, d_discarded, d_donated, adj_qty, rec_date, w_reason = txns_data[b_idx]

                # 1. RECEIVED
                txns_to_create.append(StockTransaction(
                    organization=org,
                    batch=saved_b,
                    txn_type=StockTransaction.Type.RECEIVED,
                    quantity=p_qty,
                    reason="Initial batch receipt (synthetic panel)",
                    source="CSV",
                ))

                # 2. SOLD
                if s_qty > 0:
                    txns_to_create.append(StockTransaction(
                        organization=org,
                        batch=saved_b,
                        txn_type=StockTransaction.Type.SOLD,
                        quantity=s_qty,
                        reason="Customer retail sales",
                        source="POS",
                    ))

                # 3. DISCARDED
                if d_discarded > 0:
                    txns_to_create.append(StockTransaction(
                        organization=org,
                        batch=saved_b,
                        txn_type=StockTransaction.Type.DISCARDED,
                        quantity=d_discarded,
                        reason=f"Discarded - {w_reason}",
                        source="MANUAL",
                    ))

                # 4. DONATED
                if d_donated > 0:
                    txns_to_create.append(StockTransaction(
                        organization=org,
                        batch=saved_b,
                        txn_type=StockTransaction.Type.DONATED,
                        quantity=d_donated,
                        reason="Redistributed to community food bank",
                        source="MANUAL",
                    ))

                # 5. ADJUSTMENT
                if adj_qty > 0:
                    txns_to_create.append(StockTransaction(
                        organization=org,
                        batch=saved_b,
                        txn_type=StockTransaction.Type.ADJUSTMENT,
                        quantity=adj_qty,
                        reason="carried forward, not tracked in synthetic data",
                        source="SYSTEM_ADJUSTMENT",
                    ))

            StockTransaction.objects.bulk_create(txns_to_create, batch_size=2000)

        # Output summary
        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded {len(created_batches)} batches and {len(txns_to_create)} transactions "
            f"from panel '{panel_path.name}' for organization '{org.name}' (Shop: {shops_arg}).\n"
            f"Ledger reconciliation: Received={total_received} == "
            f"Sold({total_sold}) + Discarded({total_discarded}) + Donated({total_donated}) + "
            f"Adjusted({total_adjusted}) + Remaining({total_remaining})\n"
            f"Coordinates set to: Latitude={org.latitude}, Longitude={org.longitude}."
        ))



def seed_synthetic_matching_history(
    donor_org: Optional[Organization] = None,
    count: int = 300,
    seed: int = 42,
    days: int = 90,
    stdout_write: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Generates realistic synthetic matching history records (Track B & Task 1).
    All generated entities are strictly labeled [SYNTHETIC DEMO DATA] everywhere.
    Produces correlated features (distance, category, quantity, feasibility, NGO reliability,
    donor rating) with success/failure outcomes to provide ground truth benchmark data
    for the matching learning layer.
    """
    def log(msg: str):
        if stdout_write:
            stdout_write(msg)

    rng = random.Random(seed)
    now = timezone.now()

    # 1. Donors
    if donor_org is None:
        donor_org, _ = Organization.objects.get_or_create(
            name="Fresh Harvest Supermarket",
            defaults={
                "org_type": Organization.Type.BUSINESS,
                "address": "100 MG Road, Indiranagar, Bengaluru",
                "latitude": Decimal("12.971600"),
                "longitude": Decimal("77.594600"),
                "phone": "+91 98765 43210",
                "verification_status": Organization.VerificationStatus.VERIFIED,
                "is_verified": True,
                "timezone": "Asia/Kolkata",
            },
        )

    donor_org2, _ = Organization.objects.get_or_create(
        name="Sunrise Artisan Bakery",
        defaults={
            "org_type": Organization.Type.BUSINESS,
            "address": "45 Brigade Road, Ashok Nagar, Bengaluru",
            "latitude": Decimal("12.972400"),
            "longitude": Decimal("77.608000"),
            "phone": "+91 98765 12345",
            "verification_status": Organization.VerificationStatus.VERIFIED,
            "is_verified": True,
            "timezone": "Asia/Kolkata",
        },
    )

    donors = [donor_org, donor_org2]

    # 2. Verified NGOs with realistic coordinates
    ngo_configs = [
        {
            "name": "City Food Bank Trust",
            "address": "12 Residency Road, Richmond Town, Bengaluru",
            "latitude": Decimal("12.966700"),
            "longitude": Decimal("77.601200"),
            "radius": Decimal("20.00"),
            "accepts_cooked": True,
            "base_reliability": 0.90,
        },
        {
            "name": "Hope Community Kitchen",
            "address": "88 Koramangala 4th Block, Bengaluru",
            "latitude": Decimal("12.935200"),
            "longitude": Decimal("77.624500"),
            "radius": Decimal("15.00"),
            "accepts_cooked": True,
            "base_reliability": 0.78,
        },
        {
            "name": "Robin Hood Army - Bengaluru",
            "address": "55 Cunningham Road, Vasanth Nagar, Bengaluru",
            "latitude": Decimal("12.984000"),
            "longitude": Decimal("77.592000"),
            "radius": Decimal("25.00"),
            "accepts_cooked": False,
            "base_reliability": 0.85,
        },
        {
            "name": "Annakshetra Trust - Koramangala",
            "address": "14 80ft Road, Koramangala 6th Block, Bengaluru",
            "latitude": Decimal("12.934000"),
            "longitude": Decimal("77.615000"),
            "radius": Decimal("12.00"),
            "accepts_cooked": True,
            "base_reliability": 0.82,
        },
    ]

    ngos = []
    for cfg in ngo_configs:
        ngo_obj, _ = Organization.objects.get_or_create(
            name=cfg["name"],
            defaults={
                "org_type": Organization.Type.NGO,
                "address": cfg["address"],
                "latitude": cfg["latitude"],
                "longitude": cfg["longitude"],
                "phone": "+91 98000 00000",
                "verification_status": Organization.VerificationStatus.VERIFIED,
                "is_verified": True,
                "timezone": "Asia/Kolkata",
            },
        )
        ngos.append((ngo_obj, cfg))

    # 3. Categories
    cat_dairy, _ = Category.objects.get_or_create(name="Dairy", defaults={"perishability_risk": Category.Risk.HIGH})
    cat_bakery, _ = Category.objects.get_or_create(name="Bakery", defaults={"perishability_risk": Category.Risk.MEDIUM})
    cat_produce, _ = Category.objects.get_or_create(name="Produce", defaults={"perishability_risk": Category.Risk.HIGH})
    cat_meals, _ = Category.objects.get_or_create(name="Prepared Meals", defaults={"perishability_risk": Category.Risk.CRITICAL})
    categories = [cat_dairy, cat_bakery, cat_produce, cat_meals]

    # 4. Active Requirements for NGOs labeled [SYNTHETIC DEMO DATA]
    ngo_requirements = []
    for ngo_obj, cfg in ngos:
        req, _ = NGORequirement.objects.get_or_create(
            ngo=ngo_obj,
            title=f"[SYNTHETIC DEMO DATA] {ngo_obj.name} Daily Relief Feed",
            defaults={
                "min_quantity": Decimal("10.000"),
                "max_quantity": Decimal("60.000"),
                "unit": "kg",
                "radius_km": cfg["radius"],
                "accepts_cooked_food": cfg["accepts_cooked"],
                "dietary_notes": "[SYNTHETIC DEMO DATA] Balanced nutritious food relief",
                "is_active": True,
            },
        )
        if not req.categories.exists():
            req.categories.set(categories)
        ngo_requirements.append((ngo_obj, req, cfg))

    # 5. Generate historical requests over `days`
    from marketplace.matching import haversine_distance

    completed_count = 0
    rejected_count = 0
    no_show_count = 0
    expired_count = 0

    log(f"Generating {count} synthetic matching outcomes across past {days} days (seed={seed})...")

    # Clear old synthetic matching requests with this seed prefix if re-running
    DonationRequest.objects.filter(code__startswith=f"SYNTH-{seed}-").delete()

    for idx in range(count):
        # Timestamp spaced chronologically across past days
        day_offset = rng.uniform(1.0, float(days))
        req_time = now - timedelta(days=day_offset, hours=rng.uniform(0, 12))

        donor = rng.choice(donors)
        cat = rng.choice(categories)
        ngo_obj, req, cfg = rng.choice(ngo_requirements)

        # Distance
        dist_km = haversine_distance(
            float(donor.latitude or 12.9716),
            float(donor.longitude or 77.5946),
            float(ngo_obj.latitude or 12.9667),
            float(ngo_obj.longitude or 77.6012),
        )

        qty_offered = Decimal(str(round(rng.uniform(12.0, 75.0), 3)))
        window_hours = rng.uniform(3.0, 18.0)
        avail_from = req_time - timedelta(hours=rng.uniform(1.0, 3.0))
        avail_until = avail_from + timedelta(hours=window_hours)
        safe_until = avail_until + timedelta(hours=rng.uniform(2.0, 8.0))

        listing = SurplusListing.objects.create(
            donor=donor,
            title=f"[SYNTHETIC DEMO DATA] {cat.name} Surplus Batch #{seed}-{idx+1:04d}",
            description="[SYNTHETIC DEMO DATA] Surplus redistribution offer for matching re-ranker benchmark",
            category=cat,
            quantity_offered=qty_offered,
            quantity_reserved=qty_offered,
            unit="kg",
            pickup_address=donor.address or "Indiranagar, Bengaluru",
            latitude=donor.latitude,
            longitude=donor.longitude,
            available_from=avail_from,
            available_until=avail_until,
            safe_until=safe_until,
            status=SurplusListing.Status.COMPLETED,
        )

        # Correlation logic for ground truth collection probability:
        # Distance penalty, category reward, quantity fit, feasibility, NGO reliability
        fit_ratio = min(2.0, max(0.0, float(qty_offered) / float(req.min_quantity)))
        dist_penalty = 0.08 * dist_km
        fit_bonus = 0.40 * min(fit_ratio, 1.2)
        window_bonus = 0.05 * min(12.0, window_hours)
        ngo_bonus = 0.50 * (cfg["base_reliability"] - 0.80)
        noise = rng.gauss(0.0, 0.35)

        # Log-odds
        logit = 1.5 - dist_penalty + fit_bonus + window_bonus + ngo_bonus + noise
        p_success = 1.0 / (1.0 + math.exp(-logit))

        is_completed = (rng.random() < p_success)

        code_str = f"SYNTH-{seed}-{idx+1:04d}"
        qty_requested = min(qty_offered, req.max_quantity)

        pickup_start = avail_from + timedelta(hours=1)
        pickup_end = min(avail_until, pickup_start + timedelta(hours=2))
        if pickup_end <= pickup_start:
            pickup_end = pickup_start + timedelta(hours=1)

        if is_completed:
            status = DonationRequest.Status.COMPLETED
            completed_count += 1
            completed_time = req_time + timedelta(hours=rng.uniform(1.5, 3.5))
            rejection_reason = ""
        else:
            roll = rng.random()
            if roll < 0.60:
                status = DonationRequest.Status.REJECTED
                rejected_count += 1
                rejection_reason = "[SYNTHETIC DEMO DATA] Capacity limit or scheduling mismatch"
            elif roll < 0.85:
                status = DonationRequest.Status.NO_SHOW
                no_show_count += 1
                rejection_reason = "[SYNTHETIC DEMO DATA] Transport volunteer vehicle breakdown"
            else:
                status = DonationRequest.Status.EXPIRED
                expired_count += 1
                rejection_reason = "[SYNTHETIC DEMO DATA] Available pickup window elapsed"
            completed_time = None

        dr = DonationRequest(
            code=code_str,
            listing=listing,
            ngo=ngo_obj,
            quantity_requested=qty_requested,
            quantity_approved=qty_requested if is_completed else None,
            quantity_collected=qty_requested if is_completed else None,
            status=status,
            proposed_pickup_start=pickup_start,
            proposed_pickup_end=pickup_end,
            confirmed_pickup_start=pickup_start if is_completed else None,
            confirmed_pickup_end=pickup_end if is_completed else None,
            note="[SYNTHETIC DEMO DATA] Generated matching history record",
            rejection_reason=rejection_reason,
            contact_name="Demo Coordinator",
            contact_phone="+91 99999 88888",
        )
        dr.save()

        # Update timestamps to preserve historical distribution
        DonationRequest.objects.filter(id=dr.id).update(
            requested_at=req_time,
            approved_at=req_time + timedelta(minutes=30) if is_completed else None,
            completed_at=completed_time,
            no_show_at=avail_until + timedelta(hours=1) if status == DonationRequest.Status.NO_SHOW else None,
            rejected_at=req_time + timedelta(hours=1) if status == DonationRequest.Status.REJECTED else None,
            expired_at=avail_until if status == DonationRequest.Status.EXPIRED else None,
        )

        # Rating on completed request
        if is_completed and rng.random() < 0.70:
            stars = rng.choice([4, 5, 5, 4, 3])
            Rating.objects.create(
                request=dr,
                business=donor,
                ngo=ngo_obj,
                stars=stars,
                comment=f"[SYNTHETIC DEMO DATA] Reliable collection and high quality food ({stars} stars)",
                is_hidden=False,
            )

    log(
        f"Synthetic matching history completed: {count} requests "
        f"(Completed={completed_count}, Rejected={rejected_count}, NoShow={no_show_count}, Expired={expired_count})"
    )
    return {
        "total": count,
        "completed": completed_count,
        "rejected": rejected_count,
        "no_show": no_show_count,
        "expired": expired_count,
    }
