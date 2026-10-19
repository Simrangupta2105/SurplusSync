import type {
  DataSource,
  FeatureKey,
  RegisterPayload,
} from './dataSource';
import { storeTokens, clearAuthSession, setAccessToken } from './auth';
import type {
  User,
  MeResponse,
  Category,
  StorageLocation,
  Product,
  Batch,
  BatchWithProduct,
  StockTransaction,
  AlertRule,
  Alert,
  ImportJob,
  POSApiKey,
  DashboardSummary,
  DeductStockRequest,
  DeductStockResponse,
  BarcodeLookupResult,
  DonationListing,
  DonationClaim,
  DonorPartner,
  NGOPartner,
  NotificationItem,
  ImpactMetrics,
  ClaimStatus,
  PendingRating,
  Rating,
  RatingCreatePayload,
  RatingUpdatePayload,
  BusinessRatingSummary,
  PaginatedResponse,
  AdminOrganization,
  AdminIssue,
  IssueReportPayload,
  AdminRating,
  AdminAuditLog,
  PlatformStats,
  IssueStatus,
  IssuePriority,
} from '../types';

// Deterministic PRNG (Mulberry32)
function createPRNG(seed: number) {
  let s = seed;
  return function () {
    s |= 0;
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const FIXED_SEED = 20261014;

export class DemoSource implements DataSource {
  readonly mode = 'demo' as const;

  // In-memory data tables
  private currentUser: User;
  private categories: Category[] = [];
  private locations: StorageLocation[] = [];
  private products: Product[] = [];
  private batches: Batch[] = [];
  private transactions: StockTransaction[] = [];
  private alertRules: AlertRule[] = [];
  private alerts: Alert[] = [];
  private importJobs: ImportJob[] = [];
  private posKeys: POSApiKey[] = [];
  private listings: DonationListing[] = [];
  private claims: DonationClaim[] = [];
  private ratings: Rating[] = [];
  private donors: DonorPartner[] = [];
  private ngos: NGOPartner[] = [];
  private notifications: NotificationItem[] = [];

  // Admin Tables
  private adminOrganizations: AdminOrganization[] = [];
  private adminIssues: AdminIssue[] = [];
  private adminRatings: AdminRating[] = [];
  private adminAuditLogs: AdminAuditLog[] = [];

  // Config
  private enableLatency = true;
  private simulateErrors = false; // Enabled selectively for stress testing

  constructor() {
    const savedPersona = typeof window !== 'undefined' ? localStorage.getItem('surplussync_demo_persona') : null;
    const urlPersona = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('persona')?.toUpperCase() : null;
    const effectivePersona = (urlPersona === 'NGO' || urlPersona === 'NGO_UNVERIFIED' || urlPersona === 'BUSINESS' || urlPersona === 'ADMIN')
      ? urlPersona
      : savedPersona;

    if (effectivePersona === 'ADMIN') {
      this.currentUser = {
        id: 99,
        username: 'admin_sys',
        email: 'admin@surplussync.com',
        first_name: 'Platform',
        last_name: 'Administrator',
        role: 'OWNER',
        is_platform_admin: true,
        organization: null,
      };
    } else if (effectivePersona === 'NGO') {
      this.currentUser = {
        id: 2,
        username: 'demo_ngo',
        email: 'ngo@surplussync.com',
        first_name: 'NGO',
        last_name: 'Coordinator',
        role: 'OWNER',
        organization: {
          id: 2,
          name: 'Surplus Relief Foundation',
          type: 'NGO',
          is_verified: true,
        },
      };
    } else if (effectivePersona === 'NGO_UNVERIFIED') {
      this.currentUser = {
        id: 3,
        username: 'robinhood_mysore',
        email: 'mysore@robinhoodarmy.org',
        first_name: 'Kavitha',
        last_name: 'Rao',
        role: 'OWNER',
        organization: {
          id: 3,
          name: 'Robin Hood Army (Mysore Chapter)',
          type: 'NGO',
          is_verified: false,
        },
      };
    } else {
      this.currentUser = {
        id: 1,
        username: 'demo_business',
        email: 'business@surplussync.com',
        first_name: 'Business',
        last_name: 'Admin',
        role: 'OWNER',
        organization: {
          id: 1,
          name: 'SurplusSync Partner Kitchen',
          type: 'BUSINESS',
          is_verified: true,
        },
      };
    }
    this.seedDeterministicData();
  }

  isFeatureLive(_feature: FeatureKey): boolean {
    // In demo mode, all features are simulated and active!
    return true;
  }

  setEnableLatency(enable: boolean): void {
    this.enableLatency = enable;
  }

  private async sleep(minMs = 200, maxMs = 500): Promise<void> {
    if (!this.enableLatency) return;
    const ms = Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
    await new Promise((resolve) => setTimeout(resolve, ms));
  }

  private maybeThrowError(rate = 0.03): void {
    if (this.simulateErrors && Math.random() < rate) {
      throw new Error('Simulated network transient error (3% test rate).');
    }
  }

  public seedDeterministicData(): void {
    const rng = createPRNG(FIXED_SEED);

    // 1. Categories (Food taxonomy)
    this.categories = [
      { id: 1, name: 'Dairy & Eggs', parent: null, perishability_risk: 4, storage_type: 'CHILLED', default_shelf_life_days: 7 },
      { id: 2, name: 'Fresh Produce', parent: null, perishability_risk: 4, storage_type: 'CHILLED', default_shelf_life_days: 5 },
      { id: 3, name: 'Bakery & Prepared', parent: null, perishability_risk: 3, storage_type: 'AMBIENT', default_shelf_life_days: 3 },
      { id: 4, name: 'Meat & Poultry', parent: null, perishability_risk: 4, storage_type: 'FROZEN', default_shelf_life_days: 14 },
      { id: 5, name: 'Grains & Staples', parent: null, perishability_risk: 1, storage_type: 'AMBIENT', default_shelf_life_days: 180 },
      { id: 6, name: 'Beverages & Juices', parent: null, perishability_risk: 2, storage_type: 'CHILLED', default_shelf_life_days: 30 },
      { id: 7, name: 'Cooked Meals / Buffet Surplus', parent: null, perishability_risk: 4, storage_type: 'CHILLED', default_shelf_life_days: 1 },
    ];

    // 2. Storage Locations
    this.locations = [
      { id: 1, organization: 1, name: 'Cold Room Alpha (Dairy)', storage_type: 'CHILLED', capacity: '1500' },
      { id: 2, organization: 1, name: 'Cold Room Beta (Produce)', storage_type: 'CHILLED', capacity: '2000' },
      { id: 3, organization: 1, name: 'Deep Freeze -18C', storage_type: 'FROZEN', capacity: '1000' },
      { id: 4, organization: 1, name: 'Dry Pantry Rack 1-4', storage_type: 'AMBIENT', capacity: '5000' },
      { id: 5, organization: 1, name: 'Banquet Dispatch Holding Bay', storage_type: 'CHILLED', capacity: '800' },
    ];

    // 3. Indian Context Products (~30 items)
    const productSeeds = [
      { name: 'Nandini Toned Fresh Milk 500ml', sku: 'NAN-MILK-500', barcode: '890123456701', cat: 1, unit: 'pcs', cost: '24.00' },
      { name: 'Amul Taaza Homogenised Toned Milk 1L', sku: 'AMUL-TZ-1L', barcode: '890123456702', cat: 1, unit: 'pcs', cost: '54.00' },
      { name: 'Milky Mist Paneer Fresh 200g', sku: 'MM-PAN-200', barcode: '890123456703', cat: 1, unit: 'pcs', cost: '95.00' },
      { name: 'Mother Dairy Classic Dahi 400g', sku: 'MD-DAHI-400', barcode: '890123456704', cat: 1, unit: 'pcs', cost: '40.00' },
      { name: 'ID Fresh Idli & Dosa Batter 1kg', sku: 'ID-BAT-1KG', barcode: '890123456705', cat: 3, unit: 'pcs', cost: '85.00' },
      { name: 'Britannia 100% Whole Wheat Bread 400g', sku: 'BRIT-WHT-400', barcode: '890123456706', cat: 3, unit: 'pcs', cost: '48.00' },
      { name: 'Fresh Shimla Royal Delicious Apples', sku: 'PROD-APL-KG', barcode: '890123456707', cat: 2, unit: 'kg', cost: '140.00' },
      { name: 'Fresh Robusta Bananas Bunch', sku: 'PROD-BAN-KG', barcode: '890123456708', cat: 2, unit: 'kg', cost: '45.00' },
      { name: 'Organic Palak (Spinach) Cleaned 250g', sku: 'PROD-SPN-250', barcode: '890123456709', cat: 2, unit: 'pcs', cost: '28.00' },
      { name: 'Hybrid Tomatoes Grade A', sku: 'PROD-TOM-KG', barcode: '890123456710', cat: 2, unit: 'kg', cost: '32.00' },
      { name: 'Nashik Red Onions Mesh Bag 5kg', sku: 'PROD-ONN-5KG', barcode: '890123456711', cat: 2, unit: 'pcs', cost: '175.00' },
      { name: 'Alphonso Mangoes Devgad Box (6 pcs)', sku: 'PROD-MNG-BOX', barcode: '890123456712', cat: 2, unit: 'pcs', cost: '650.00' },
      { name: 'Fresh Coriander & Mint Herbs Bundle', sku: 'PROD-HRB-BUN', barcode: '890123456713', cat: 2, unit: 'pcs', cost: '15.00' },
      { name: 'Aashirvaad Superior MP Sharbati Atta 5kg', sku: 'AASH-ATTA-5KG', barcode: '890123456714', cat: 5, unit: 'pcs', cost: '290.00' },
      { name: 'Daawat Rozana Super Basmati Rice 5kg', sku: 'DAAW-BAS-5KG', barcode: '890123456715', cat: 5, unit: 'pcs', cost: '380.00' },
      { name: 'Tata Sampann Unpolished Toor Dal 1kg', sku: 'TATA-TOOR-1KG', barcode: '890123456716', cat: 5, unit: 'pcs', cost: '165.00' },
      { name: 'Fortune Sunlite Refined Sunflower Oil 1L', sku: 'FORT-OIL-1L', barcode: '890123456717', cat: 5, unit: 'pcs', cost: '135.00' },
      { name: 'Everest Shahi Biryani Masala 100g', sku: 'EVR-BIRY-100', barcode: '890123456718', cat: 5, unit: 'pcs', cost: '78.00' },
      { name: 'Licious Chicken Breast Boneless 450g', sku: 'LIC-CHK-450', barcode: '890123456719', cat: 4, unit: 'pcs', cost: '245.00' },
      { name: 'Fresh Atlantic Salmon Fillet Portion', sku: 'FISH-SALM-KG', barcode: '890123456720', cat: 4, unit: 'kg', cost: '1450.00' },
      { name: 'Raw Mutton Curry Cut Fresh 500g', sku: 'MUT-CUT-500', barcode: '890123456721', cat: 4, unit: 'pcs', cost: '460.00' },
      { name: 'Raw Pressery Cold Pressed Valencia Orange 1L', sku: 'RAW-ORG-1L', barcode: '890123456722', cat: 6, unit: 'pcs', cost: '190.00' },
      { name: 'Paper Boat Tender Coconut Water 200ml', sku: 'PB-COCO-200', barcode: '890123456723', cat: 6, unit: 'pcs', cost: '50.00' },
      { name: 'Banquet Dal Makhani & Jeera Rice Trays', sku: 'BNQ-DAL-TRY', barcode: '890123456724', cat: 7, unit: 'kg', cost: '180.00' },
      { name: 'Banquet Paneer Butter Masala Catering Tub', sku: 'BNQ-PBM-TUB', barcode: '890123456725', cat: 7, unit: 'kg', cost: '320.00' },
      { name: 'Assorted Gourmet Bread Rolls Basket', sku: 'BNQ-ROLL-BSK', barcode: '890123456726', cat: 3, unit: 'pcs', cost: '120.00' },
      { name: 'Gulab Jamun Banquet Hot Desserts Tray', sku: 'BNQ-GUL-TRY', barcode: '890123456727', cat: 7, unit: 'kg', cost: '250.00' },
      { name: 'Fresh Cut Mixed Fruit Salad Bowl 1kg', sku: 'PROD-FRT-1KG', barcode: '890123456728', cat: 2, unit: 'pcs', cost: '180.00' },
      { name: 'Epigamia Greek Yogurt Strawberry 120g', sku: 'EPI-YOG-120', barcode: '890123456729', cat: 1, unit: 'pcs', cost: '60.00' },
      { name: 'Haldiram Minute Khana Methi Paratha (Pack of 4)', sku: 'HALD-PAR-4PK', barcode: '890123456730', cat: 3, unit: 'pcs', cost: '90.00' },
    ];

    this.products = productSeeds.map((p, idx) => ({
      id: idx + 1,
      organization: 1,
      name: p.name,
      sku: p.sku,
      barcode: p.barcode,
      category: p.cat,
      unit: p.unit,
      unit_cost: p.cost,
      reorder_level: '20.00',
      is_active: true,
    }));

    // 4. Batches (~80 batches with varied expiry dates)
    const baseDate = new Date();
    baseDate.setHours(0, 0, 0, 0);

    this.batches = [];

    let batchCounter = 1;
    for (let pIdx = 0; pIdx < this.products.length; pIdx++) {
      const prod = this.products[pIdx];
      // Generate 2 to 4 batches per product
      const count = 2 + Math.floor(rng() * 3);
      for (let b = 0; b < count; b++) {
        // Expiry offsets: some expired (-5 to -1), some critical (1 to 2 days), some medium (3 to 14 days), some long (20 to 120 days)
        let expiryOffsetDays: number;
        if (b === 0 && pIdx < 6) {
          expiryOffsetDays = 1 + Math.floor(rng() * 2); // 1-2 days (Critical!)
        } else if (b === 1 && pIdx < 10) {
          expiryOffsetDays = 3 + Math.floor(rng() * 5); // 3-7 days (Warning)
        } else if (rng() < 0.1) {
          expiryOffsetDays = -(1 + Math.floor(rng() * 6)); // Expired
        } else {
          expiryOffsetDays = 8 + Math.floor(rng() * 60); // Stable
        }

        const expDate = new Date(baseDate);
        expDate.setDate(expDate.getDate() + expiryOffsetDays);

        const rcvDate = new Date(expDate);
        rcvDate.setDate(rcvDate.getDate() - (5 + Math.floor(rng() * 20)));

        const qty = (10 + Math.floor(rng() * 85)).toFixed(1);
        let bStatus: 'ACTIVE' | 'EXPIRED' | 'DEPLETED' | 'DONATED' = 'ACTIVE';

        if (expiryOffsetDays < 0) {
          bStatus = rng() > 0.5 ? 'EXPIRED' : 'DISCARDED' as unknown as 'DEPLETED';
        }

        const batchCode = `BTH-${expDate.getFullYear()}${String(expDate.getMonth() + 1).padStart(2, '0')}-${String(batchCounter).padStart(3, '0')}`;

        this.batches.push({
          id: batchCounter,
          organization: 1,
          product: prod.id,
          location: 1 + Math.floor(rng() * this.locations.length),
          batch_code: batchCode,
          quantity: qty,
          received_date: rcvDate.toISOString().split('T')[0],
          expiry_date: expDate.toISOString().split('T')[0],
          status: bStatus,
          created_at: rcvDate.toISOString(),
        });
        batchCounter++;
      }
    }

    // 5. Stock Transactions (90 days history)
    this.transactions = [];
    let txnId = 1;
    for (let day = 90; day >= 0; day--) {
      const d = new Date(baseDate);
      d.setDate(d.getDate() - day);
      const dayStr = d.toISOString();

      // Sold transactions (POS)
      const soldCount = 2 + Math.floor(rng() * 4);
      for (let s = 0; s < soldCount; s++) {
        const randBatch = this.batches[Math.floor(rng() * this.batches.length)];
        this.transactions.push({
          id: txnId++,
          organization: 1,
          batch: randBatch.id,
          txn_type: 'SOLD',
          quantity: (1 + Math.floor(rng() * 8)).toString(),
          reason: 'Daily POS Sale',
          source: 'POS',
          created_by: 1,
          created_at: dayStr,
          external_id: `POS-TXN-${day}-${s}-${txnId}`,
        });
      }

      // Occasional Donated or Discarded
      if (day % 3 === 0) {
        const randBatch = this.batches[Math.floor(rng() * this.batches.length)];
        this.transactions.push({
          id: txnId++,
          organization: 1,
          batch: randBatch.id,
          txn_type: 'DONATED',
          quantity: (5 + Math.floor(rng() * 20)).toString(),
          reason: 'Surplus food rescue dispatch to NGO partner',
          source: 'MANUAL',
          created_by: 1,
          created_at: dayStr,
          external_id: `DON-TXN-${day}-${txnId}`,
        });
      }

      if (day % 7 === 0) {
        const randBatch = this.batches[Math.floor(rng() * this.batches.length)];
        this.transactions.push({
          id: txnId++,
          organization: 1,
          batch: randBatch.id,
          txn_type: 'DISCARDED',
          quantity: (2 + Math.floor(rng() * 6)).toString(),
          reason: 'Cold-chain seal compromised',
          source: 'MANUAL',
          created_by: 1,
          created_at: dayStr,
          external_id: `DISC-TXN-${day}-${txnId}`,
        });
      }
    }

    // 6. Alert Rules
    this.alertRules = [
      { id: 1, organization: 1, category: 1, days_before_expiry: 2, is_active: true }, // Dairy
      { id: 2, organization: 1, category: 2, days_before_expiry: 2, is_active: true }, // Produce
      { id: 3, organization: 1, category: 7, days_before_expiry: 1, is_active: true }, // Cooked buffet
      { id: 4, organization: 1, category: null, days_before_expiry: 3, is_active: true }, // Global
    ];

    // 7. Active Alerts
    this.alerts = [
      {
        id: 1,
        organization: 1,
        batch: 1,
        rule: 1,
        severity: 'CRITICAL',
        message: 'Batch BTH-202610-001 (Nandini Milk) expires in 18 hours. FEFO priority dispatch required.',
        is_acknowledged: false,
        created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
      },
      {
        id: 2,
        organization: 1,
        batch: 3,
        rule: 2,
        severity: 'CRITICAL',
        message: 'Batch BTH-202610-003 (Milky Mist Paneer) has 32 units expiring tomorrow morning.',
        is_acknowledged: false,
        created_at: new Date(Date.now() - 3600000 * 5).toISOString(),
      },
      {
        id: 3,
        organization: 1,
        batch: 7,
        rule: 3,
        severity: 'WARNING',
        message: 'Banquet Dal Makhani & Rice surplus listed for NGO pickup window ending at 23:00.',
        is_acknowledged: false,
        created_at: new Date(Date.now() - 3600000 * 8).toISOString(),
      },
      {
        id: 4,
        organization: 1,
        batch: 9,
        rule: 4,
        severity: 'INFO',
        message: 'Organic Spinach 250g reaching 48h shelf horizon. Ready for markdown or donation.',
        is_acknowledged: true,
        created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
      },
    ];

    // 8. 12 Verified Indian NGOs
    this.ngos = [
      { id: 1, name: 'Surplus Relief Foundation', verified: true, address: 'HK Hill, West of Chord Road, Bengaluru', phone: '+91 80 2356 1234', latitude: 13.0098, longitude: 77.5511, total_rescued_kg: 8450 },
      { id: 2, name: 'Robin Hood Army (Central BLR)', verified: true, address: 'Indiranagar 100ft Road, Bengaluru', phone: '+91 98450 11223', latitude: 12.9784, longitude: 77.6408, total_rescued_kg: 4210 },
      { id: 3, name: 'Feeding India by Zomato', verified: true, address: 'Koramangala 4th Block, Bengaluru', phone: '+91 99001 88776', latitude: 12.9345, longitude: 77.6265, total_rescued_kg: 6890 },
      { id: 4, name: 'Bangalore Roti Bank', verified: true, address: 'Shivajinagar Bus Station Road, Bengaluru', phone: '+91 80 2286 5432', latitude: 12.9856, longitude: 77.6054, total_rescued_kg: 3120 },
      { id: 5, name: 'Goonj Urban Relief Centre', verified: true, address: 'Hosur Main Road, Kudlu Gate, Bengaluru', phone: '+91 96200 45456', latitude: 12.8897, longitude: 77.6492, total_rescued_kg: 2900 },
      { id: 6, name: 'Hasiru Dala Community Kitchen', verified: true, address: 'Nayandahalli, Mysore Road, Bengaluru', phone: '+91 98860 77112', latitude: 12.9431, longitude: 77.5218, total_rescued_kg: 1850 },
      { id: 7, name: 'Smile Foundation Outreach', verified: true, address: 'Jayanagar 4th Block, Bengaluru', phone: '+91 80 4120 9090', latitude: 12.9250, longitude: 77.5938, total_rescued_kg: 2400 },
      { id: 8, name: 'Uday Foundation Relief Cell', verified: true, address: 'HSR Layout Sector 2, Bengaluru', phone: '+91 97110 33445', latitude: 12.9116, longitude: 77.6473, total_rescued_kg: 3750 },
      { id: 9, name: 'Rise Against Hunger India', verified: true, address: 'Whitefield Main Road, Bengaluru', phone: '+91 80 6721 3300', latitude: 12.9698, longitude: 77.7499, total_rescued_kg: 5600 },
      { id: 10, name: 'Seva Sahayog Foundation', verified: true, address: 'Malleshwaram 8th Cross, Bengaluru', phone: '+91 94480 22119', latitude: 13.0033, longitude: 77.5702, total_rescued_kg: 1980 },
      { id: 11, name: 'Annakshetra Surplus Rescue', verified: true, address: 'Rajajinagar 1st Block, Bengaluru', phone: '+91 80 2315 8899', latitude: 13.0012, longitude: 77.5540, total_rescued_kg: 1420 },
      { id: 12, name: 'Yuva Bengaluru Food Rescue Guild', verified: true, address: 'Basavanagudi Bull Temple Road, Bengaluru', phone: '+91 98440 66778', latitude: 12.9422, longitude: 77.5681, total_rescued_kg: 2150 },
    ];

    // 9. 8 Verified Donors with Ratings
    this.donors = [
      { id: 1, name: 'The Grand Gateway Bengaluru', rating: 4.9, rating_count: 142, verified: true, address: 'MG Road, Bengaluru', phone: '+91 80 6660 4444', latitude: 12.9754, longitude: 77.6190 },
      { id: 2, name: 'The Oberoi Luxury Banquets', rating: 4.8, rating_count: 98, verified: true, address: '37-39 MG Road, Bengaluru', phone: '+91 80 2558 5858', latitude: 12.9733, longitude: 77.6185 },
      { id: 3, name: 'BigBasket Fulfilment Centre #4', rating: 4.7, rating_count: 310, verified: true, address: 'Hosur Road, Bommanahalli, Bengaluru', phone: '+91 80 4344 5500', latitude: 12.9038, longitude: 77.6256 },
      { id: 4, name: 'Metro Cash & Carry Wholesale', rating: 4.6, rating_count: 215, verified: true, address: 'Yeshwantpur Industrial Suburb, Bengaluru', phone: '+91 80 4116 8000', latitude: 13.0248, longitude: 77.5451 },
      { id: 5, name: "Haldiram's Sweets & Savouries", rating: 4.9, rating_count: 85, verified: true, address: 'Indiranagar 12th Main, Bengaluru', phone: '+91 80 4151 7777', latitude: 12.9712, longitude: 77.6412 },
      { id: 6, name: 'ITC Gardenia Convention Center', rating: 4.9, rating_count: 164, verified: true, address: 'Residency Road, Bengaluru', phone: '+91 80 2211 9898', latitude: 12.9669, longitude: 77.5997 },
      { id: 7, name: 'More Megastore Hypermarket', rating: 4.5, rating_count: 178, verified: true, address: 'Koramangala Inner Ring Road, Bengaluru', phone: '+91 80 2552 1100', latitude: 12.9388, longitude: 77.6298 },
      { id: 8, name: 'Blinkit Dark Store #12', rating: 4.6, rating_count: 92, verified: true, address: 'HSR Sector 1, Bengaluru', phone: '+91 98800 44112', latitude: 12.9165, longitude: 77.6512 },
    ];

    // 10. Donation Listings & Claims
    this.listings = [
      {
        id: 1,
        business_id: 1,
        business_name: 'The Grand Gateway Bengaluru',
        business_rating: 4.9,
        batch_id: 7,
        product_name: 'Banquet Dal Makhani & Jeera Rice Trays',
        category: 'Cooked Meals / Buffet Surplus',
        quantity: 35,
        unit: 'kg',
        expiry_date: new Date(Date.now() + 3600000 * 14).toISOString().split('T')[0],
        pickup_window_start: '20:30',
        pickup_window_end: '23:00',
        status: 'AVAILABLE',
        address: 'Service Gate 3, The Grand Gateway, MG Road, Bengaluru',
        latitude: 12.9754,
        longitude: 77.6190,
        distance_km: 1.8,
        created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
      },
      {
        id: 2,
        business_id: 2,
        business_name: 'The Oberoi Luxury Banquets',
        business_rating: 4.8,
        batch_id: 25,
        product_name: 'Banquet Paneer Butter Masala Catering Tub',
        category: 'Cooked Meals / Buffet Surplus',
        quantity: 28,
        unit: 'kg',
        expiry_date: new Date(Date.now() + 3600000 * 16).toISOString().split('T')[0],
        pickup_window_start: '21:00',
        pickup_window_end: '23:30',
        status: 'CLAIMED',
        address: 'Banquet Loading Dock, Oberoi MG Road, Bengaluru',
        latitude: 12.9733,
        longitude: 77.6185,
        distance_km: 2.1,
        created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
      },
      {
        id: 3,
        business_id: 3,
        business_name: 'BigBasket Fulfilment Centre #4',
        business_rating: 4.7,
        batch_id: 1,
        product_name: 'Nandini Toned Fresh Milk 500ml',
        category: 'Dairy & Eggs',
        quantity: 45,
        unit: 'pcs',
        expiry_date: new Date(Date.now() + 3600000 * 28).toISOString().split('T')[0],
        pickup_window_start: '18:00',
        pickup_window_end: '22:00',
        status: 'AVAILABLE',
        address: 'Gate 2, Hosur Road DC, Bommanahalli, Bengaluru',
        latitude: 12.9038,
        longitude: 77.6256,
        distance_km: 5.4,
        created_at: new Date(Date.now() - 3600000 * 1).toISOString(),
      },
      {
        id: 4,
        business_id: 5,
        business_name: "Haldiram's Sweets & Savouries",
        business_rating: 4.9,
        batch_id: 27,
        product_name: 'Gulab Jamun Banquet Hot Desserts Tray',
        category: 'Cooked Meals / Buffet Surplus',
        quantity: 18,
        unit: 'kg',
        expiry_date: new Date(Date.now() + 3600000 * 12).toISOString().split('T')[0],
        pickup_window_start: '21:30',
        pickup_window_end: '23:00',
        status: 'PICKED_UP',
        address: 'Dispatch Bay, 12th Main Indiranagar, Bengaluru',
        latitude: 12.9712,
        longitude: 77.6412,
        distance_km: 3.2,
        created_at: new Date(Date.now() - 3600000 * 12).toISOString(),
      },
    ];

    this.claims = [
      {
        id: 1,
        listing_id: 2,
        listing: this.listings[1],
        ngo_id: 2,
        ngo_name: 'Surplus Relief Foundation',
        status: 'CONFIRMED',
        pickup_eta: '21:45',
        notes: 'Electric insulated van arriving with 2 volunteers.',
        created_at: new Date(Date.now() - 3600000 * 3).toISOString(),
        updated_at: new Date(Date.now() - 3600000 * 1).toISOString(),
      },
      {
        id: 2,
        listing_id: 4,
        listing: this.listings[3],
        ngo_id: 3,
        ngo_name: 'Robin Hood Army (Mysore Chapter)',
        status: 'PICKED_UP',
        pickup_eta: '22:15',
        notes: 'Distributed to 95 shelter residents near Cantonment.',
        donor_rating: 4,
        donor_feedback: 'Pristine hygiene condition, thermally intact packaging!',
        created_at: new Date(Date.now() - 3600000 * 48).toISOString(),
        updated_at: new Date(Date.now() - 3600000 * 48).toISOString(),
      },
      {
        id: 3,
        listing_id: 1,
        listing: this.listings[0],
        ngo_id: 2,
        ngo_name: 'Surplus Relief Foundation',
        status: 'PICKED_UP',
        pickup_eta: '20:15',
        notes: '15kg Paneer Butter Masala rescued in thermal containers.',
        created_at: new Date(Date.now() - 3600000 * 12).toISOString(),
        updated_at: new Date(Date.now() - 3600000 * 4).toISOString(),
      },
      {
        id: 4,
        listing_id: 3,
        listing: this.listings[2],
        ngo_id: 2,
        ngo_name: 'Surplus Relief Foundation',
        status: 'PICKED_UP',
        pickup_eta: '19:30',
        notes: '30 portions of biryani delivered to community kitchen.',
        donor_rating: 5,
        donor_feedback: 'Freshly packed, hot buffet surplus in pristine food-grade containers.',
        created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
        updated_at: new Date(Date.now() - 3600000 * 24).toISOString(),
      },
    ];

    // Ratings
    this.ratings = [
      {
        id: 1,
        claim: 4,
        ngo: 2,
        ngo_name: 'Surplus Relief Foundation',
        business: 1,
        business_name: 'The Grand Gateway Hotel',
        stars: 5,
        comment: 'Freshly packed, hot buffet surplus in pristine food-grade containers.',
        is_hidden: false,
        is_editable: true,
        edit_deadline: new Date(Date.now() + 6 * 86400000).toISOString(),
        created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
        updated_at: new Date(Date.now() - 3600000 * 24).toISOString(),
      },
      {
        id: 2,
        claim: 2,
        ngo: 3,
        ngo_name: 'Robin Hood Army (Mysore Chapter)',
        business: 1,
        business_name: 'The Grand Gateway Hotel',
        stars: 4,
        comment: 'Pristine hygiene condition, thermally intact packaging!',
        is_hidden: false,
        is_editable: true,
        edit_deadline: new Date(Date.now() + 5 * 86400000).toISOString(),
        created_at: new Date(Date.now() - 3600000 * 48).toISOString(),
        updated_at: new Date(Date.now() - 3600000 * 48).toISOString(),
      },
    ];

    // 11. Notifications
    this.notifications = [
      {
        id: 'notif-1',
        type: 'CLAIM',
        title: 'New NGO Claim Confirmed',
        message: 'Surplus Relief Foundation claimed 28kg Paneer Butter Masala. ETA 21:45.',
        timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
        is_read: false,
      },
      {
        id: 'notif-2',
        type: 'ALERT',
        title: 'Critical Expiry Horizon (18h)',
        message: 'Batch BTH-202610-001 (Nandini Milk) is in danger of spoilage.',
        timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
        is_read: false,
      },
      {
        id: 'notif-3',
        type: 'SYSTEM',
        title: 'POS Nightly Sync Reconciled',
        message: '100% of transactions reconciled across 80 active batches.',
        timestamp: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
        is_read: true,
      },
    ];

    // 12. POS Keys
    this.posKeys = [
      { id: 1, organization: 1, label: 'Front Desk Micros Opera POS', is_active: true, key_prefix: 'sps_live_a1...9f8b' },
      { id: 2, organization: 1, label: 'Banquet Kitchen Scanner POS', is_active: true, key_prefix: 'sps_live_f4...2e10' },
    ];

    // 13. Import Jobs
    this.importJobs = [
      {
        id: 1,
        organization: 1,
        file: 'inventory_manifest_oct.csv',
        status: 'DONE',
        total_rows: 48,
        processed_rows: 48,
        rows_ok: 48,
        rows_failed: 0,
        started_at: new Date(Date.now() - 3600000 * 2).toISOString(),
        finished_at: new Date(Date.now() - 3600000 * 2 + 5000).toISOString(),
        error_report: [],
        created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
      },
      {
        id: 2,
        organization: 1,
        file: 'produce_restock_v2.csv',
        status: 'PARTIAL',
        total_rows: 35,
        processed_rows: 35,
        rows_ok: 33,
        rows_failed: 2,
        started_at: new Date(Date.now() - 86400000).toISOString(),
        finished_at: new Date(Date.now() - 86400000 + 4000).toISOString(),
        error_report: [
          { row: 14, error: "Invalid date format '2026/99/99'", data: { product_name: 'Organic Bananas' } },
          { row: 29, error: 'Missing product_name', data: { quantity: '10' } },
        ],
        created_at: new Date(Date.now() - 86400000).toISOString(),
      },
    ];

    // 10. Admin Organizations
    this.adminOrganizations = [
      {
        id: 1,
        name: 'SurplusSync Partner Kitchen',
        org_type: 'BUSINESS',
        address: '12th Main Indiranagar, Bengaluru',
        latitude: 12.9716,
        longitude: 77.6412,
        phone: '+91 80 4123 4567',
        is_verified: true,
        verification_status: 'VERIFIED',
        verification_note: 'Food safety license FSSAI #1122334455 verified.',
        verified_at: '2026-08-10T10:00:00Z',
        created_at: '2026-08-01T09:30:00Z',
        users_count: 3,
        batches_count: 8,
        listings_count: 6,
        claims_count: 0,
        users: [
          {
            id: 1,
            username: 'demo_business',
            email: 'business@surplussync.com',
            first_name: 'Business',
            last_name: 'Admin',
            role: 'OWNER',
            is_active: true,
            date_joined: '2026-08-01T09:30:00Z',
            last_login: '2026-10-16T12:00:00Z',
          },
        ],
        recent_activity: {
          listings: [
            { id: 101, title: 'Fresh Veg Biryani Portions', quantity: 35, status: 'OPEN', created_at: '2026-10-16T11:00:00Z' },
          ],
          batches: [
            { id: 201, product__name: 'Basmati Rice Batch', quantity: 50, status: 'ACTIVE', expiry_date: '2026-10-24', created_at: '2026-10-10T08:00:00Z' },
          ],
          claims: [],
          ratings: [
            { id: 1, stars: 5, comment: 'Exceptional food rescue partner. Hot containers, courteous team.', created_at: '2026-10-15T15:00:00Z' },
          ],
          audit_logs: [
            { id: 1, action: 'ORGANIZATION_VERIFY', admin_user__username: 'admin_sys', details: { note: 'Initial verification on onboarding' }, created_at: '2026-08-10T10:00:00Z' },
          ],
        },
      },
      {
        id: 4,
        name: 'ITC Windsor Banquet Central',
        org_type: 'BUSINESS',
        address: '25 Golf Course Rd, Bengaluru',
        latitude: 12.9892,
        longitude: 77.5855,
        phone: '+91 80 2226 9898',
        is_verified: true,
        verification_status: 'VERIFIED',
        verification_note: 'Five-star hotel sustainability certified.',
        verified_at: '2026-08-15T14:20:00Z',
        created_at: '2026-08-12T11:00:00Z',
        users_count: 5,
        batches_count: 14,
        listings_count: 10,
        claims_count: 0,
      },
      {
        id: 5,
        name: 'Daily Bread Artisanal Bakery',
        org_type: 'BUSINESS',
        address: '100ft Road Koramangala, Bengaluru',
        latitude: 12.9345,
        longitude: 77.6189,
        phone: '+91 80 6789 0123',
        is_verified: true,
        verification_status: 'VERIFIED',
        verification_note: 'Daily evening surplus collection protocol approved.',
        verified_at: '2026-08-20T16:00:00Z',
        created_at: '2026-08-18T10:15:00Z',
        users_count: 2,
        batches_count: 4,
        listings_count: 3,
        claims_count: 0,
      },
      {
        id: 6,
        name: 'The Grand Gateway Bistro',
        org_type: 'BUSINESS',
        address: 'MG Road Metro Station Area, Bengaluru',
        latitude: 12.9755,
        longitude: 77.6066,
        phone: '+91 80 4321 8765',
        is_verified: false,
        verification_status: 'SUSPENDED',
        verification_note: 'Repeated cold chain temperature compliance breach during inspection.',
        verified_at: null,
        created_at: '2026-08-25T14:40:00Z',
        users_count: 2,
        batches_count: 0,
        listings_count: 0,
        claims_count: 0,
      },
      {
        id: 2,
        name: 'Surplus Relief Foundation',
        org_type: 'NGO',
        address: '14 Koramangala 4th Block, Bengaluru',
        latitude: 12.9322,
        longitude: 77.6255,
        phone: '+91 98450 11223',
        is_verified: true,
        verification_status: 'VERIFIED',
        verification_note: 'Darpan NITI Aayog registration and 80G verified.',
        verified_at: '2026-08-10T12:00:00Z',
        created_at: '2026-08-02T10:00:00Z',
        users_count: 4,
        batches_count: 0,
        listings_count: 0,
        claims_count: 14,
      },
      {
        id: 3,
        name: 'Robin Hood Army (Mysore Chapter)',
        org_type: 'NGO',
        address: '45 Nazarbad Main Rd, Mysuru',
        latitude: 12.3051,
        longitude: 76.6552,
        phone: '+91 98800 22334',
        is_verified: false,
        verification_status: 'PENDING',
        verification_note: 'Government 80G tax registration document uploaded, awaiting platform verification.',
        verified_at: null,
        created_at: '2026-10-12T15:20:00Z',
        users_count: 2,
        batches_count: 0,
        listings_count: 0,
        claims_count: 0,
      },
      {
        id: 7,
        name: 'Akshaya Patra Relief Hub',
        org_type: 'NGO',
        address: 'Rajajinagar Industrial Area, Bengaluru',
        latitude: 12.9912,
        longitude: 77.5533,
        phone: '+91 80 2314 5566',
        is_verified: true,
        verification_status: 'VERIFIED',
        verification_note: 'National centralized kitchen partner.',
        verified_at: '2026-08-14T09:30:00Z',
        created_at: '2026-08-05T08:00:00Z',
        users_count: 6,
        batches_count: 0,
        listings_count: 0,
        claims_count: 28,
      },
      {
        id: 8,
        name: 'Hope Community Food Care',
        org_type: 'NGO',
        address: 'Whitefield Outer Circle, Bengaluru',
        latitude: 12.9698,
        longitude: 77.7499,
        phone: '+91 99001 33445',
        is_verified: false,
        verification_status: 'REJECTED',
        verification_note: 'Expired NGO trust deed and mismatched registration number.',
        verified_at: null,
        created_at: '2026-09-01T12:00:00Z',
        users_count: 1,
        batches_count: 0,
        listings_count: 0,
        claims_count: 0,
      },
    ];

    // 11. Admin Issues
    this.adminIssues = [
      {
        id: 101,
        reporter: 2,
        reporter_name: 'demo_ngo',
        reporter_email: 'ngo@surplussync.com',
        reporter_org: 2,
        reporter_org_name: 'Surplus Relief Foundation',
        reporter_org_type: 'NGO',
        target_org: 1,
        target_org_name: 'SurplusSync Partner Kitchen',
        target_org_type: 'BUSINESS',
        claim: 1,
        claim_title: 'Chilled Milk & Dairy Crates',
        claim_status: 'PICKED_UP',
        category: 'FOOD_QUALITY',
        description: 'Chilled dairy items were collected at 14°C instead of mandated <=4°C cold chain.',
        status: 'OPEN',
        priority: 'HIGH',
        admin_notes: 'Supervisor requested transit temperature telemetry from donor dispatch bay.',
        assigned_to: 99,
        assigned_to_name: 'admin_sys',
        created_at: '2026-10-15T14:30:00Z',
        updated_at: '2026-10-15T14:30:00Z',
      },
      {
        id: 102,
        reporter: 4,
        reporter_name: 'itc_manager',
        reporter_email: 'chef@itcwindsor.com',
        reporter_org: 4,
        reporter_org_name: 'ITC Windsor Banquet Central',
        reporter_org_type: 'BUSINESS',
        target_org: 7,
        target_org_name: 'Akshaya Patra Relief Hub',
        target_org_type: 'NGO',
        claim: 2,
        claim_title: 'Buffet Main Course Surplus',
        claim_status: 'CONFIRMED',
        category: 'NO_SHOW',
        description: 'NGO collection vehicle did not arrive before 22:30 kitchen sanitation closing.',
        status: 'IN_REVIEW',
        priority: 'MEDIUM',
        admin_notes: 'NGO fleet manager confirmed transport breakdown; substitute vehicle was rerouted.',
        created_at: '2026-10-14T23:15:00Z',
        updated_at: '2026-10-15T09:00:00Z',
      },
      {
        id: 103,
        reporter: 2,
        reporter_name: 'demo_ngo',
        reporter_email: 'ngo@surplussync.com',
        reporter_org: 2,
        reporter_org_name: 'Surplus Relief Foundation',
        reporter_org_type: 'NGO',
        target_org: 1,
        target_org_name: 'SurplusSync Partner Kitchen',
        target_org_type: 'BUSINESS',
        claim: null,
        claim_title: null,
        category: 'TECHNICAL',
        description: 'QR handover scan failed on Android client; batch reconciled with secondary code.',
        status: 'RESOLVED',
        priority: 'LOW',
        admin_notes: 'Manual handover verification logged and accepted by platform support.',
        resolved_by: 99,
        resolved_by_name: 'admin_sys',
        resolved_at: '2026-10-15T16:00:00Z',
        created_at: '2026-10-14T10:00:00Z',
        updated_at: '2026-10-15T16:00:00Z',
      },
      {
        id: 104,
        reporter: 7,
        reporter_name: 'akshaya_lead',
        reporter_email: 'lead@akshayapatra.org',
        reporter_org: 7,
        reporter_org_name: 'Akshaya Patra Relief Hub',
        reporter_org_type: 'NGO',
        target_org: 5,
        target_org_name: 'Daily Bread Artisanal Bakery',
        target_org_type: 'BUSINESS',
        claim: 3,
        claim_title: 'Evening Baguette Surplus',
        claim_status: 'PICKED_UP',
        category: 'WRONG_QUANTITY',
        description: 'Manifest specified 50 units but actual count received in warehouse was 28 units.',
        status: 'OPEN',
        priority: 'MEDIUM',
        admin_notes: '',
        created_at: '2026-10-16T08:00:00Z',
        updated_at: '2026-10-16T08:00:00Z',
      },
    ];

    // 12. Admin Ratings
    this.adminRatings = [
      {
        id: 1,
        stars: 5,
        comment: 'Exceptional food rescue partner. Hot containers, courteous team.',
        is_hidden: false,
        hidden_reason: '',
        business: 1,
        business_name: 'SurplusSync Partner Kitchen',
        ngo: 2,
        ngo_name: 'Surplus Relief Foundation',
        claim: 1,
        claim_title: 'Surplus Meals - Dal & Rice',
        created_at: '2026-10-14T15:00:00Z',
        updated_at: '2026-10-14T15:00:00Z',
      },
      {
        id: 2,
        stars: 4,
        comment: 'High quality bakery items, slightly delayed handoff at loading dock.',
        is_hidden: false,
        hidden_reason: '',
        business: 1,
        business_name: 'SurplusSync Partner Kitchen',
        ngo: 7,
        ngo_name: 'Akshaya Patra Relief Hub',
        claim: 2,
        claim_title: 'Sandwich Trays & Salads',
        created_at: '2026-10-15T11:30:00Z',
        updated_at: '2026-10-15T11:30:00Z',
      },
      {
        id: 3,
        stars: 1,
        comment: 'Unacceptable behavior by warehouse dock guard and spoiled items.',
        is_hidden: true,
        hidden_reason: 'Flagged for offensive language and unverified allegations under dispute review.',
        business: 4,
        business_name: 'ITC Windsor Banquet Central',
        ngo: 2,
        ngo_name: 'Surplus Relief Foundation',
        claim: 3,
        claim_title: 'Banquet Surplus Rice & Curry',
        created_at: '2026-10-15T18:00:00Z',
        updated_at: '2026-10-16T09:30:00Z',
      },
      {
        id: 4,
        stars: 5,
        comment: 'Well labeled nutritional allergen breakdown. Seamless and fast pickup.',
        is_hidden: false,
        hidden_reason: '',
        business: 4,
        business_name: 'ITC Windsor Banquet Central',
        ngo: 7,
        ngo_name: 'Akshaya Patra Relief Hub',
        claim: 4,
        claim_title: 'Fresh Bakery Rolls',
        created_at: '2026-10-16T10:00:00Z',
        updated_at: '2026-10-16T10:00:00Z',
      },
    ];

    // 13. Admin Audit Logs
    this.adminAuditLogs = [
      {
        id: 1,
        admin_user: 99,
        admin_username: 'admin_sys',
        admin_email: 'admin@surplussync.com',
        action: 'ORGANIZATION_VERIFY',
        target_type: 'Organization',
        target_id: '2',
        details: { note: 'Verified 80G certificate and Darpan trust deed.' },
        created_at: '2026-08-10T12:00:00Z',
      },
      {
        id: 2,
        admin_user: 99,
        admin_username: 'admin_sys',
        admin_email: 'admin@surplussync.com',
        action: 'ORGANIZATION_REJECT',
        target_type: 'Organization',
        target_id: '8',
        details: { reason: 'Expired registration certificate and mismatched number.' },
        created_at: '2026-09-01T12:00:00Z',
      },
      {
        id: 3,
        admin_user: 99,
        admin_username: 'admin_sys',
        admin_email: 'admin@surplussync.com',
        action: 'RATING_HIDE',
        target_type: 'Rating',
        target_id: '3',
        details: { reason: 'Flagged for moderation due to hostile remarks.' },
        created_at: '2026-10-16T09:30:00Z',
      },
      {
        id: 4,
        admin_user: 99,
        admin_username: 'admin_sys',
        admin_email: 'admin@surplussync.com',
        action: 'ORGANIZATION_SUSPEND',
        target_type: 'Organization',
        target_id: '6',
        details: { reason: 'Repeated cold chain temperature compliance breach.' },
        created_at: '2026-08-25T14:40:00Z',
      },
    ];

    this.loadCustomData();
  }

  // --- DataSource Methods ---

  async login(username: string, _password: string, rememberMe = false): Promise<{ user: User; token: string }> {
    await this.sleep(250, 450);
    this.maybeThrowError();

    const isAdmin = username.toLowerCase().includes('admin');
    const isNGO = !isAdmin && (username.toLowerCase().includes('ngo') || username.toLowerCase().includes('relief'));

    if (isAdmin) {
      this.currentUser = {
        id: 99,
        username: username || 'admin_sys',
        email: 'admin@surplussync.com',
        first_name: 'Platform',
        last_name: 'Administrator',
        role: 'OWNER',
        is_platform_admin: true,
        organization: null,
      };
    } else {
      this.currentUser = {
        id: isNGO ? 2 : 1,
        username: username || (isNGO ? 'demo_ngo' : 'demo_business'),
        email: isNGO ? 'ngo@surplussync.com' : 'business@surplussync.com',
        first_name: isNGO ? 'NGO' : 'Business',
        last_name: isNGO ? 'Coordinator' : 'Admin',
        role: 'OWNER',
        is_platform_admin: false,
        organization: {
          id: isNGO ? 2 : 1,
          name: isNGO ? 'Surplus Relief Foundation' : 'SurplusSync Partner Kitchen',
          type: isNGO ? 'NGO' : 'BUSINESS',
          is_verified: true,
        },
      };
    }

    const dummyToken = `demo_jwt_token_${Date.now()}`;
    const dummyRefresh = `demo_refresh_token_${Date.now()}`;
    storeTokens(dummyToken, dummyRefresh, rememberMe);

    return { user: this.currentUser, token: dummyToken };
  }

  async logout(): Promise<void> {
    clearAuthSession();
    setAccessToken(null);
  }

  async register(payload: RegisterPayload): Promise<MeResponse> {
    await this.sleep(350, 550);
    this.maybeThrowError();

    this.currentUser = {
      id: Math.floor(Math.random() * 1000) + 10,
      username: payload.username,
      email: payload.email,
      first_name: payload.username,
      last_name: '',
      role: 'OWNER',
      organization: {
        id: Math.floor(Math.random() * 1000) + 10,
        name: payload.org_name,
        type: payload.org_type,
        is_verified: payload.org_type === 'BUSINESS', // NGOs require admin verification
      },
    };

    const dummyToken = `demo_jwt_token_${Date.now()}`;
    const dummyRefresh = `demo_refresh_token_${Date.now()}`;
    storeTokens(dummyToken, dummyRefresh, true);

    return this.getMe();
  }

  async getMe(): Promise<MeResponse> {
    await this.sleep(100, 200);
    return {
      id: this.currentUser.id,
      username: this.currentUser.username,
      email: this.currentUser.email,
      role: this.currentUser.role,
      is_platform_admin: this.currentUser.is_platform_admin,
      organization: this.currentUser.organization,
    };
  }

  setDemoUser(persona: 'BUSINESS' | 'NGO' | 'NGO_UNVERIFIED' | 'ADMIN'): User {
    if (typeof window !== 'undefined') {
      localStorage.setItem('surplussync_demo_persona', persona);
    }
    if (persona === 'ADMIN') {
      this.currentUser = {
        id: 99,
        username: 'admin_sys',
        email: 'admin@surplussync.com',
        first_name: 'Platform',
        last_name: 'Administrator',
        role: 'OWNER',
        is_platform_admin: true,
        organization: null,
      };
    } else if (persona === 'NGO') {
      this.currentUser = {
        id: 2,
        username: 'demo_ngo',
        email: 'ngo@surplussync.com',
        first_name: 'NGO',
        last_name: 'Coordinator',
        role: 'OWNER',
        is_platform_admin: false,
        organization: {
          id: 2,
          name: 'Surplus Relief Foundation',
          type: 'NGO',
          is_verified: true,
        },
      };
    } else if (persona === 'NGO_UNVERIFIED') {
      this.currentUser = {
        id: 3,
        username: 'robinhood_mysore',
        email: 'mysore@robinhoodarmy.org',
        first_name: 'Kavitha',
        last_name: 'Rao',
        role: 'OWNER',
        is_platform_admin: false,
        organization: {
          id: 3,
          name: 'Robin Hood Army (Mysore Chapter)',
          type: 'NGO',
          is_verified: false,
        },
      };
    } else {
      this.currentUser = {
        id: 1,
        username: 'demo_business',
        email: 'business@surplussync.com',
        first_name: 'Business',
        last_name: 'Admin',
        role: 'OWNER',
        is_platform_admin: false,
        organization: {
          id: 1,
          name: 'SurplusSync Partner Kitchen',
          type: 'BUSINESS',
          is_verified: true,
        },
      };
    }
    const dummyToken = `demo_jwt_token_${Date.now()}`;
    const dummyRefresh = `demo_refresh_token_${Date.now()}`;
    storeTokens(dummyToken, dummyRefresh, true);
    return this.currentUser;
  }

  async getDashboardSummary(): Promise<DashboardSummary> {
    await this.sleep(200, 400);
    this.maybeThrowError();
    this.syncExpiryAlerts();

    const activeBatches = this.batches.filter((b) => b.status === 'ACTIVE');
    const totalActiveQty = activeBatches.reduce((acc, b) => acc + parseFloat(b.quantity), 0);

    const now = new Date();
    const in48h = new Date(now.getTime() + 48 * 3600 * 1000);
    const expiring48h = activeBatches.filter((b) => {
      const exp = new Date(b.expiry_date);
      return exp >= now && exp <= in48h;
    }).length;

    const criticalAlerts = this.alerts.filter(
      (a) => a.severity === 'CRITICAL' && !a.is_acknowledged
    ).length;

    // Calculate 30-day waste and donated value
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 3600 * 1000);
    let wastedVal = 0;
    let donatedVal = 0;

    for (const t of this.transactions) {
      if (new Date(t.created_at) >= thirtyDaysAgo) {
        const batch = this.batches.find((b) => b.id === t.batch);
        const prod = batch ? this.products.find((p) => p.id === batch.product) : null;
        const unitCost = prod?.unit_cost ? parseFloat(prod.unit_cost) : 100;
        const qty = parseFloat(t.quantity);
        if (t.txn_type === 'WASTED' || t.txn_type === 'DISCARDED') {
          wastedVal += qty * unitCost;
        } else if (t.txn_type === 'DONATED') {
          donatedVal += qty * unitCost;
        }
      }
    }

    return {
      total_active_batches: activeBatches.length,
      total_active_quantity: totalActiveQty.toFixed(1),
      batches_expiring_48h: expiring48h,
      critical_alerts_unacknowledged: criticalAlerts,
      wasted_value_30d: wastedVal.toFixed(2),
      donated_value_30d: donatedVal.toFixed(2),
      missing_cost_items: 0,
    };
  }

  async getCategories(): Promise<Category[]> {
    await this.sleep(100, 250);
    return [...this.categories];
  }

  async getStorageLocations(): Promise<StorageLocation[]> {
    await this.sleep(100, 250);
    return [...this.locations];
  }

  async getProducts(search?: string, categoryId?: number): Promise<Product[]> {
    await this.sleep(200, 450);
    this.maybeThrowError();

    let list = [...this.products];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.sku.toLowerCase().includes(q) ||
          p.barcode.includes(q)
      );
    }
    if (categoryId) {
      list = list.filter((p) => p.category === categoryId);
    }
    return list;
  }

  async createProduct(product: Omit<Product, 'id' | 'organization'>): Promise<Product> {
    await this.sleep(250, 400);
    const newProd: Product = {
      ...product,
      id: this.products.length + 1,
      organization: 1,
    };
    this.products.unshift(newProd);
    return newProd;
  }

  async updateProduct(id: number, partial: Partial<Product>): Promise<Product> {
    await this.sleep(200, 350);
    const idx = this.products.findIndex((p) => p.id === id);
    if (idx === -1) throw new Error('Product not found.');
    this.products[idx] = { ...this.products[idx], ...partial };
    return this.products[idx];
  }

  async lookupBarcode(barcode: string): Promise<BarcodeLookupResult> {
    await this.sleep(200, 400);
    const prod = this.products.find((p) => p.barcode === barcode);
    if (prod) {
      const activeBatch = this.batches.find(
        (b) => b.product === prod.id && b.status === 'ACTIVE'
      );
      const cat = this.categories.find((c) => c.id === prod.category);
      return {
        found: true,
        source: 'local',
        product: prod,
        product_name: prod.name,
        category_name: cat?.name,
        current_stock: activeBatch ? parseFloat(activeBatch.quantity) : 0,
        batch_code: activeBatch?.batch_code,
        expiry_date: activeBatch?.expiry_date,
      };
    }

    // Fallback simulation for Open Food Facts
    if (barcode.startsWith('890')) {
      return {
        found: true,
        source: 'openfoodfacts',
        product_name: 'Simulated Open Food Facts Item',
        brand: 'Standard Brands India',
        category_name: 'Dairy',
        categories_text: 'en:dairies, en:milks',
        current_stock: 0,
      };
    }

    return {
      found: false,
      source: 'none',
      detail: `Barcode ${barcode} not found in local catalog or Open Food Facts.`,
    };
  }

  async getBatches(status?: string, productId?: number): Promise<BatchWithProduct[]> {
    await this.sleep(250, 450);
    this.maybeThrowError();

    let list = [...this.batches];
    if (status) {
      list = list.filter((b) => b.status === status);
    }
    if (productId) {
      list = list.filter((b) => b.product === productId);
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    return list.map((b) => {
      const prod = this.products.find((p) => p.id === b.product);
      const loc = this.locations.find((l) => l.id === b.location);
      const cat = prod ? this.categories.find((c) => c.id === prod.category) : null;
      const exp = new Date(b.expiry_date);
      exp.setHours(0, 0, 0, 0);
      const diffDays = Math.ceil((exp.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

      return {
        ...b,
        product_name: prod?.name || `Product #${b.product}`,
        product_sku: prod?.sku || '',
        product_barcode: prod?.barcode || '',
        category_name: cat?.name,
        unit: prod?.unit || 'kg',
        unit_cost: prod?.unit_cost || null,
        location_name: loc?.name,
        days_to_expiry: diffDays,
      };
    });
  }

  async getExpiringBatches(days = 7): Promise<BatchWithProduct[]> {
    await this.sleep(200, 400);
    const all = await this.getBatches('ACTIVE');
    return all
      .filter((b) => b.days_to_expiry >= 0 && b.days_to_expiry <= days)
      .sort((a, b) => a.days_to_expiry - b.days_to_expiry);
  }

  async createBatch(batch: Omit<Batch, 'id' | 'organization' | 'created_at'>): Promise<Batch> {
    await this.sleep(250, 450);
    const newBatch: Batch = {
      ...batch,
      id: this.batches.length + 1,
      organization: 1,
      created_at: new Date().toISOString(),
    };
    this.batches.unshift(newBatch);

    // Append to transactions ledger
    this.transactions.unshift({
      id: this.transactions.length + 1,
      organization: 1,
      batch: newBatch.id,
      txn_type: 'RECEIVED',
      quantity: newBatch.quantity,
      reason: 'Inward Goods Receipt',
      source: 'MANUAL',
      created_by: 1,
      created_at: new Date().toISOString(),
      external_id: `RCV-${Date.now()}`,
    });

    this.syncExpiryAlerts();
    return newBatch;
  }

  async updateBatch(id: number, partial: Partial<Batch>): Promise<Batch> {
    await this.sleep(200, 350);
    const idx = this.batches.findIndex((b) => b.id === id);
    if (idx === -1) throw new Error('Batch not found.');
    this.batches[idx] = { ...this.batches[idx], ...partial };
    return this.batches[idx];
  }

  /**
   * Strict FEFO Stock Deduction
   * Deducts strictly in First-Expired, First-Out order from active non-expired batches.
   */
  async deductStock(req: DeductStockRequest): Promise<DeductStockResponse> {
    await this.sleep(300, 500);

    // Resolve product
    let targetProduct: Product | undefined;
    if (req.product) {
      targetProduct = this.products.find((p) => p.id === req.product);
    } else if (req.barcode) {
      targetProduct = this.products.find((p) => p.barcode === req.barcode);
    } else if (req.sku) {
      targetProduct = this.products.find((p) => p.sku === req.sku);
    }

    if (!targetProduct) {
      throw new Error('Product not found for stock deduction.');
    }

    const requestedQty = parseFloat(String(req.quantity));
    if (isNaN(requestedQty) || requestedQty <= 0) {
      throw new Error('Quantity must be a positive number.');
    }

    // Find active batches for product sorted by expiry_date ASC (FEFO)
    const todayStr = new Date().toISOString().split('T')[0];
    const candidateBatches = this.batches
      .filter(
        (b) =>
          b.product === targetProduct!.id &&
          b.status === 'ACTIVE' &&
          b.expiry_date >= todayStr &&
          parseFloat(b.quantity) > 0
      )
      .sort((a, b) => a.expiry_date.localeCompare(b.expiry_date));

    const totalAvailable = candidateBatches.reduce((acc, b) => acc + parseFloat(b.quantity), 0);
    if (totalAvailable < requestedQty) {
      throw new Error(`Insufficient stock. Requested: ${requestedQty}, Available: ${totalAvailable}`);
    }

    let remainingToDeduct = requestedQty;
    const deductions: Array<{
      batch_id: number;
      batch_code: string;
      deducted_quantity: string;
      remaining_batch_quantity: string;
      status: 'ACTIVE' | 'EXPIRED' | 'DEPLETED' | 'DONATED';
    }> = [];

    for (const b of candidateBatches) {
      if (remainingToDeduct <= 0) break;
      const bQty = parseFloat(b.quantity);
      const deductAmt = Math.min(bQty, remainingToDeduct);
      const newQty = bQty - deductAmt;

      b.quantity = newQty.toFixed(1);
      if (newQty === 0) {
        b.status = 'DEPLETED';
      }

      remainingToDeduct -= deductAmt;

      deductions.push({
        batch_id: b.id,
        batch_code: b.batch_code,
        deducted_quantity: deductAmt.toFixed(1),
        remaining_batch_quantity: b.quantity,
        status: b.status,
      });

      // Append transaction
      this.transactions.unshift({
        id: this.transactions.length + 1,
        organization: 1,
        batch: b.id,
        txn_type: req.txn_type || 'SOLD',
        quantity: deductAmt.toFixed(1),
        reason: req.reason || 'FEFO Stock Deduction',
        source: 'MANUAL',
        created_by: 1,
        created_at: new Date().toISOString(),
        external_id: req.external_id || `DED-${Date.now()}`,
      });
    }

    return {
      message: 'Stock deducted successfully.',
      product_id: targetProduct.id,
      total_deducted: requestedQty.toFixed(1),
      deductions,
      idempotent_replay: false,
    };
  }

  async getTransactions(limit = 50): Promise<StockTransaction[]> {
    await this.sleep(150, 350);
    const list = this.transactions.slice(0, limit);
    return list.map((t) => {
      const b = this.batches.find((b) => b.id === t.batch);
      const p = b ? this.products.find((prod) => prod.id === b.product) : null;
      return {
        ...t,
        batch_code: b?.batch_code,
        product_name: p?.name,
      };
    });
  }

  // --- Alerts ---

  async getAlertRules(): Promise<AlertRule[]> {
    await this.sleep(150, 300);
    return [...this.alertRules];
  }

  private syncExpiryAlerts(): void {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayStr = today.toISOString().split('T')[0];

    // Clean up any alerts for batches that are already expired, not active, or past expiry date
    this.alerts = this.alerts.filter((a) => {
      const b = this.batches.find((batch) => batch.id === a.batch);
      if (!b) return true;
      if (b.status === 'EXPIRED') return false;
      if (b.expiry_date < todayStr) return false;
      return true;
    });

    for (const batch of this.batches) {
      const prod = this.products.find((p) => p.id === batch.product);
      const prodName = prod?.name || `Product #${batch.product}`;

      if (batch.status === 'EXPIRED') {
        // Expired batches should NOT be in the alert section
        this.alerts = this.alerts.filter((a) => a.batch !== batch.id);
        continue;
      }

      const expDate = new Date(batch.expiry_date);
      expDate.setHours(0, 0, 0, 0);
      const daysLeft = Math.ceil((expDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

      if (daysLeft < 0) {
        batch.status = 'EXPIRED';
        // Expired batches should NOT be in the alert section
        this.alerts = this.alerts.filter((a) => a.batch !== batch.id);
        continue;
      }

      if (batch.status !== 'ACTIVE') {
        this.alerts = this.alerts.filter((a) => a.batch !== batch.id);
        continue;
      }

      // Strictly for less than 7 days of expiry (< 7 days)
      if (daysLeft >= 7) {
        const staleIdx = this.alerts.findIndex((a) => a.batch === batch.id && !a.is_acknowledged);
        if (staleIdx !== -1) {
          this.alerts.splice(staleIdx, 1);
        }
        continue;
      }

      // Check category alert rules capped at less than 7 days
      const catRule = this.alertRules.find((r) => r.is_active && r.category === prod?.category);
      const globalRule = this.alertRules.find((r) => r.is_active && !r.category);
      const rule = catRule || globalRule;
      const threshold = rule ? Math.min(rule.days_before_expiry, 6) : 6;

      if (daysLeft <= threshold && daysLeft < 7) {
        let severity: 'CRITICAL' | 'WARNING' | 'INFO' = 'INFO';
        if (daysLeft <= 2) {
          severity = 'CRITICAL';
        } else if (daysLeft <= 4) {
          severity = 'WARNING';
        }

        const msg = `Batch ${batch.batch_code || batch.id} (${prodName}) expires in ${daysLeft} day(s) on ${batch.expiry_date}.`;
        const existing = this.alerts.find((a) => a.batch === batch.id && !a.is_acknowledged);

        if (!existing) {
          this.alerts.unshift({
            id: this.alerts.length > 0 ? Math.max(...this.alerts.map((a) => a.id)) + 1 : 1,
            organization: 1,
            batch: batch.id,
            rule: rule ? rule.id : null,
            severity,
            message: msg,
            is_acknowledged: false,
            created_at: new Date().toISOString(),
          });
        } else {
          const ranks = { INFO: 1, WARNING: 2, CRITICAL: 3 };
          if (ranks[severity] > ranks[existing.severity]) {
            existing.severity = severity;
            existing.message = msg;
          }
        }
      }
    }
  }

  async getAlerts(severity?: string, acknowledged?: boolean): Promise<Alert[]> {
    await this.sleep(200, 400);
    this.syncExpiryAlerts();
    const todayStr = new Date().toISOString().split('T')[0];
    let list = [...this.alerts];
    if (severity) list = list.filter((a) => a.severity === severity);
    if (acknowledged !== undefined) list = list.filter((a) => a.is_acknowledged === acknowledged);

    return list
      .map((a) => {
        const b = this.batches.find((batch) => batch.id === a.batch);
        const p = b ? this.products.find((prod) => prod.id === b.product) : null;
        return {
          ...a,
          batch_code: b?.batch_code,
          batch_status: b?.status,
          product_name: p?.name,
          expiry_date: b?.expiry_date,
        };
      })
      .filter((a) => {
        // The ones which are expired should not be in the alert section
        if (a.batch_status === 'EXPIRED') return false;
        if (a.expiry_date && a.expiry_date < todayStr) return false;
        return true;
      });
  }

  async acknowledgeAlert(id: number): Promise<{ success: boolean }> {
    await this.sleep(150, 300);
    const alert = this.alerts.find((a) => a.id === id);
    if (alert) alert.is_acknowledged = true;
    return { success: true };
  }

  async bulkAcknowledgeAlerts(ids: number[]): Promise<{ success: boolean; count: number }> {
    await this.sleep(200, 350);
    let count = 0;
    this.alerts.forEach((a) => {
      if (ids.includes(a.id) && !a.is_acknowledged) {
        a.is_acknowledged = true;
        count++;
      }
    });
    return { success: true, count };
  }

  // --- CSV Import & POS Keys ---

  async uploadCsvImport(file: File): Promise<ImportJob> {
    await this.sleep(400, 700);
    let rowsOk = 0;
    let rowsFailed = 0;
    const errors: Array<{ row: number; error: string; raw?: unknown }> = [];

    try {
      const text = await file.text();
      const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
      if (lines.length > 1) {
        const headers = lines[0].split(',').map((h) => h.trim().toLowerCase());
        for (let i = 1; i < lines.length; i++) {
          const values = lines[i].split(',').map((v) => v.trim());
          const rowData: Record<string, string> = {};
          headers.forEach((h, idx) => {
            rowData[h] = values[idx] || '';
          });

          const name = rowData['product_name'] || rowData['name'];
          if (!name) {
            rowsFailed++;
            errors.push({ row: i + 1, error: 'Missing product_name' });
            continue;
          }

          let prod = this.products.find(
            (p) =>
              (rowData['sku'] && p.sku === rowData['sku']) ||
              (rowData['barcode'] && p.barcode === rowData['barcode']) ||
              p.name.toLowerCase() === name.toLowerCase()
          );

          if (!prod) {
            const catObj = this.categories.find(
              (c) => c.name.toLowerCase() === (rowData['category'] || '').toLowerCase()
            ) || this.categories[0];
            prod = {
              id: this.products.length + 1,
              organization: 1,
              name,
              sku: rowData['sku'] || `SKU-${Date.now()}-${i}`,
              barcode: rowData['barcode'] || `890${Math.floor(1000000000 + Math.random() * 9000000000)}`,
              category: catObj ? catObj.id : 1,
              category_name: catObj ? catObj.name : 'General',
              unit: rowData['unit'] || 'kg',
              unit_cost: rowData['cost_price'] || rowData['unit_cost'] || '50.00',
              cost_price: rowData['cost_price'] || rowData['unit_cost'] || '50.00',
              selling_price: rowData['selling_price'] || '70.00',
              min_stock_level: 10,
              reorder_level: '10',
              shelf_life_days: 14,
              is_active: true,
            };
            this.products.unshift(prod);
          }

          const qty = parseFloat(rowData['quantity'] || '10') || 10;
          const expDate = rowData['expiry_date'] || new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0];
          const recDate = rowData['received_date'] || rowData['manufacturing_date'] || new Date().toISOString().split('T')[0];
          const batchCode = rowData['batch_code'] || `BTH-CSV-${Date.now().toString().slice(-4)}-${i}`;

          const newBatch: Batch = {
            id: this.batches.length + 1,
            organization: 1,
            product: prod.id,
            location: null,
            batch_code: batchCode,
            quantity: String(qty),
            initial_quantity: qty,
            current_quantity: qty,
            received_date: recDate,
            expiry_date: expDate,
            status: 'ACTIVE',
            created_at: new Date().toISOString(),
          };
          this.batches.unshift(newBatch);
          rowsOk++;
        }
        this.saveCustomData();
      }
    } catch {
      // fallback if file.text() fails
    }

    if (rowsOk === 0 && rowsFailed === 0) {
      rowsOk = 3;
    }

    const totalRows = rowsOk + rowsFailed;
    const isAsyncSimulation = totalRows > 50 || file.name.toLowerCase().includes('large') || file.name.toLowerCase().includes('async');
    const isStuckWorker = file.name.toLowerCase().includes('stuck') || file.name.toLowerCase().includes('down');

    const jobId = this.importJobs.length + 1;
    const nowIso = new Date().toISOString();

    let job: ImportJob;
    if (isStuckWorker) {
      job = {
        id: jobId,
        organization: 1,
        file: file.name,
        status: 'PENDING',
        total_rows: totalRows,
        processed_rows: 0,
        rows_ok: 0,
        rows_failed: 0,
        started_at: null,
        finished_at: null,
        error_report: [],
        worker_may_be_down: true,
        created_at: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
      };
    } else if (isAsyncSimulation) {
      job = {
        id: jobId,
        organization: 1,
        file: file.name,
        status: 'PROCESSING',
        total_rows: totalRows,
        processed_rows: Math.min(10, totalRows),
        rows_ok: Math.min(10, rowsOk),
        rows_failed: 0,
        started_at: nowIso,
        finished_at: null,
        error_report: [],
        created_at: nowIso,
      };

      // Progressively simulate background worker increments
      const targetOk = rowsOk;
      const targetFailed = rowsFailed;
      const targetErrors = errors;
      setTimeout(() => {
        const found = this.importJobs.find((j) => j.id === jobId);
        if (found && found.status === 'PROCESSING') {
          found.processed_rows = Math.floor(totalRows * 0.5);
          found.rows_ok = Math.floor(targetOk * 0.5);
        }
      }, 800);

      setTimeout(() => {
        const found = this.importJobs.find((j) => j.id === jobId);
        if (found && found.status === 'PROCESSING') {
          found.processed_rows = totalRows;
          found.rows_ok = targetOk;
          found.rows_failed = targetFailed;
          found.error_report = targetErrors;
          found.finished_at = new Date().toISOString();
          found.status = targetFailed === 0 ? 'DONE' : targetOk === 0 ? 'FAILED' : 'PARTIAL';
          this.syncExpiryAlerts();
        }
      }, 2000);
    } else {
      job = {
        id: jobId,
        organization: 1,
        file: file.name,
        status: rowsFailed === 0 ? 'DONE' : rowsOk === 0 ? 'FAILED' : 'PARTIAL',
        total_rows: totalRows,
        processed_rows: totalRows,
        rows_ok: rowsOk,
        rows_failed: rowsFailed,
        started_at: nowIso,
        finished_at: nowIso,
        error_report: errors,
        created_at: nowIso,
      };
      this.syncExpiryAlerts();
    }

    this.importJobs.unshift(job);
    return job;
  }

  async getImportJobs(): Promise<ImportJob[]> {
    await this.sleep(100, 200);
    return [...this.importJobs];
  }

  async getImportJob(id: number): Promise<ImportJob> {
    await this.sleep(100, 200);
    const job = this.importJobs.find((j) => j.id === id);
    if (!job) {
      throw new Error(`ImportJob #${id} not found.`);
    }
    return { ...job };
  }

  async getPOSKeys(): Promise<POSApiKey[]> {
    await this.sleep(150, 300);
    return [...this.posKeys];
  }

  async createPOSKey(label: string): Promise<POSApiKey> {
    await this.sleep(250, 450);
    const rawKey = `sps_live_${Math.random().toString(16).substring(2)}${Math.random().toString(16).substring(2)}`;
    const newKey: POSApiKey = {
      id: this.posKeys.length + 1,
      organization: 1,
      label,
      is_active: true,
      raw_key: rawKey,
      key_prefix: `${rawKey.substring(0, 11)}...${rawKey.substring(rawKey.length - 4)}`,
    };
    this.posKeys.unshift(newKey);
    return newKey;
  }

  async rotatePOSKey(id: number): Promise<{ id: number; raw_key: string; key_prefix: string }> {
    await this.sleep(250, 400);
    const key = this.posKeys.find((k) => k.id === id);
    if (!key) throw new Error('API key not found');
    const rawKey = `sps_live_${Math.random().toString(16).substring(2)}${Math.random().toString(16).substring(2)}`;
    const prefix = `${rawKey.substring(0, 11)}...${rawKey.substring(rawKey.length - 4)}`;
    key.raw_key = rawKey;
    key.key_prefix = prefix;
    return { id, raw_key: rawKey, key_prefix: prefix };
  }

  // --- Marketplace & NGO Operations (Active in Demo Mode) ---

  async getListings(filters?: { status?: string; category?: string }): Promise<DonationListing[]> {
    await this.sleep(200, 400);
    let list = [...this.listings];
    if (filters?.status) list = list.filter((l) => l.status === filters.status);
    if (filters?.category) list = list.filter((l) => l.category === filters.category);
    return list;
  }

  async createListing(batchId: number, windowHours: number): Promise<DonationListing> {
    await this.sleep(250, 450);
    const b = this.batches.find((b) => b.id === batchId);
    if (!b) throw new Error('Batch not found.');
    const p = this.products.find((prod) => prod.id === b.product);
    const cat = p ? this.categories.find((c) => c.id === p.category) : null;

    const start = new Date();
    const end = new Date(start.getTime() + windowHours * 3600 * 1000);

    const newListing: DonationListing = {
      id: this.listings.length + 1,
      business_id: 1,
      business_name: 'The Grand Gateway Bengaluru',
      business_rating: 4.9,
      batch_id: b.id,
      product_name: p?.name || 'Surplus Item',
      category: cat?.name || 'Surplus Food',
      quantity: parseFloat(b.quantity),
      unit: p?.unit || 'kg',
      expiry_date: b.expiry_date,
      pickup_window_start: `${String(start.getHours()).padStart(2, '0')}:00`,
      pickup_window_end: `${String(end.getHours()).padStart(2, '0')}:00`,
      status: 'AVAILABLE',
      address: 'Service Gate 3, The Grand Gateway, MG Road, Bengaluru',
      latitude: 12.9754,
      longitude: 77.6190,
      created_at: new Date().toISOString(),
    };

    b.status = 'DONATED';
    this.listings.unshift(newListing);
    return newListing;
  }

  async getClaims(status?: ClaimStatus): Promise<DonationClaim[]> {
    await this.sleep(200, 400);
    let list = [...this.claims];
    if (status) list = list.filter((c) => c.status === status);
    return list;
  }

  async claimListing(listingId: number, pickupEta: string, notes: string): Promise<DonationClaim> {
    await this.sleep(300, 500);
    const listing = this.listings.find((l) => l.id === listingId);
    if (!listing) throw new Error('Listing not found');
    listing.status = 'CLAIMED';

    const newClaim: DonationClaim = {
      id: this.claims.length + 1,
      listing_id: listing.id,
      listing,
      ngo_id: this.currentUser.organization?.id || 1,
      ngo_name: this.currentUser.organization?.name || 'Surplus Relief Foundation',
      status: 'PENDING',
      pickup_eta: pickupEta,
      notes,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    this.claims.unshift(newClaim);
    return newClaim;
  }

  async updateClaimStatus(claimId: number, status: ClaimStatus): Promise<DonationClaim> {
    await this.sleep(200, 400);
    const claim = this.claims.find((c) => c.id === claimId);
    if (!claim) throw new Error('Claim not found');
    claim.status = status;
    claim.updated_at = new Date().toISOString();
    if (claim.listing) {
      if (status === 'PICKED_UP') claim.listing.status = 'PICKED_UP';
      else if (status === 'CANCELLED') claim.listing.status = 'AVAILABLE';
    }
    return claim;
  }

  async rateDonor(claimId: number, rating: number, feedback?: string): Promise<{ success: boolean }> {
    await this.sleep(200, 400);
    const claim = this.claims.find((c) => c.id === claimId);
    if (claim) {
      claim.donor_rating = rating;
      claim.donor_feedback = feedback;
    }
    return { success: true };
  }

  async getDonors(): Promise<DonorPartner[]> {
    await this.sleep(150, 300);
    return [...this.donors];
  }

  async getNGOs(): Promise<NGOPartner[]> {
    await this.sleep(150, 300);
    return [...this.ngos];
  }

  async getImpactMetrics(): Promise<ImpactMetrics> {
    await this.sleep(200, 400);
    const totalDonatedKg = this.transactions
      .filter((t) => t.txn_type === 'DONATED')
      .reduce((acc, t) => acc + parseFloat(t.quantity), 0);

    const kgDiverted = Math.round(totalDonatedKg + 2840);
    const meals = Math.round(kgDiverted / 0.42);
    const co2e = Math.round(kgDiverted * 2.5);

    return {
      kg_diverted: kgDiverted,
      meals_provided: meals,
      co2e_avoided_kg: co2e,
      monthly_trend: [
        { month: 'Jun', kg_diverted: 480, meals: Math.round(480 / 0.42), co2e_kg: Math.round(480 * 2.5) },
        { month: 'Jul', kg_diverted: 620, meals: Math.round(620 / 0.42), co2e_kg: Math.round(620 * 2.5) },
        { month: 'Aug', kg_diverted: 810, meals: Math.round(810 / 0.42), co2e_kg: Math.round(810 * 2.5) },
        { month: 'Sep', kg_diverted: 940, meals: Math.round(940 / 0.42), co2e_kg: Math.round(940 * 2.5) },
        { month: 'Oct', kg_diverted: 1120, meals: Math.round(1120 / 0.42), co2e_kg: Math.round(1120 * 2.5) },
      ],
    };
  }

  async getNotifications(): Promise<NotificationItem[]> {
    await this.sleep(100, 250);
    return [...this.notifications];
  }

  async markNotificationRead(id: string): Promise<void> {
    const notif = this.notifications.find((n) => n.id === id);
    if (notif) notif.is_read = true;
  }

  // --- Ratings (NGO rating business) ---
  async getPendingRatings(): Promise<PendingRating[]> {
    await this.sleep(150, 300);
    const org = this.currentUser?.organization;
    if (!org || org.type !== 'NGO' || !org.is_verified) {
      throw new Error('Only verified NGO users may access pending ratings.');
    }

    const ratedClaimIds = new Set(this.ratings.map((r) => r.claim));

    return this.claims
      .filter((c) => c.status === 'PICKED_UP' && c.ngo_id === org.id && !ratedClaimIds.has(c.id))
      .map((c) => {
        const listing = c.listing || this.listings.find((l) => l.id === c.listing_id);
        const donorId = listing?.business_id || 1;
        const donorName = listing?.business_name || 'Donor Partner';

        const businessRatings = this.ratings.filter(
          (r) => r.business === donorId && !r.is_hidden
        );
        const avg =
          businessRatings.length > 0
            ? Math.round(
                (businessRatings.reduce((sum, r) => sum + r.stars, 0) / businessRatings.length) * 100
              ) / 100
            : null;

        return {
          id: c.id,
          claim_id: c.id,
          donor_id: donorId,
          donor_name: donorName,
          donor_rating_avg: avg,
          donor_rating_count: businessRatings.length,
          item: listing?.product_name || 'Donation Package',
          listing_title: listing?.product_name || 'Donation Package',
          quantity: listing?.quantity ?? '0',
          pickup_date: c.updated_at || c.created_at,
          pickup_eta: c.pickup_eta,
          updated_at: c.updated_at,
        };
      });
  }

  async rateClaim(claimId: number, payload: RatingCreatePayload): Promise<Rating> {
    await this.sleep(200, 400);
    const org = this.currentUser?.organization;
    if (!org || org.type !== 'NGO' || !org.is_verified) {
      throw new Error('Only verified NGO users may rate a donor.');
    }

    const claim = this.claims.find((c) => c.id === claimId);
    if (!claim || claim.ngo_id !== org.id) {
      throw new Error('Not found.');
    }
    if (claim.status !== 'PICKED_UP') {
      throw new Error('You can only rate a claim that has been picked up.');
    }
    if (this.ratings.some((r) => r.claim === claimId)) {
      throw new Error('A rating already exists for this claim.');
    }
    if (!payload.stars || payload.stars < 1 || payload.stars > 5) {
      throw new Error('Stars must be between 1 and 5.');
    }

    const listing = claim.listing || this.listings.find((l) => l.id === claim.listing_id);
    const businessId = listing?.business_id || 1;
    const businessName = listing?.business_name || 'Donor Partner';
    const now = new Date();
    const editDeadline = new Date(now.getTime() + 7 * 86400000).toISOString();

    const newRating: Rating = {
      id: this.ratings.length ? Math.max(...this.ratings.map((r) => r.id)) + 1 : 1,
      claim: claim.id,
      ngo: org.id,
      ngo_name: org.name,
      business: businessId,
      business_name: businessName,
      stars: payload.stars,
      comment: payload.comment || '',
      is_hidden: false,
      is_editable: true,
      edit_deadline: editDeadline,
      created_at: now.toISOString(),
      updated_at: now.toISOString(),
    };

    this.ratings.unshift(newRating);
    claim.donor_rating = payload.stars;
    claim.donor_feedback = payload.comment || '';

    return newRating;
  }

  async updateRating(ratingId: number, payload: RatingUpdatePayload): Promise<Rating> {
    await this.sleep(200, 400);
    const org = this.currentUser?.organization;
    if (!org || org.type !== 'NGO' || !org.is_verified) {
      throw new Error('Only verified NGO users may edit a rating.');
    }

    const rating = this.ratings.find((r) => r.id === ratingId);
    if (!rating || rating.ngo !== org.id) {
      throw new Error('Not found.');
    }

    const now = new Date();
    const deadline = new Date(rating.edit_deadline).getTime();
    if (now.getTime() > deadline || !rating.is_editable) {
      rating.is_editable = false;
      throw new Error('This rating is locked; the 7-day edit window has passed.');
    }

    if (payload.stars !== undefined) {
      if (payload.stars < 1 || payload.stars > 5) {
        throw new Error('Stars must be between 1 and 5.');
      }
      rating.stars = payload.stars;
    }
    if (payload.comment !== undefined) {
      rating.comment = payload.comment;
    }
    rating.updated_at = now.toISOString();

    return { ...rating };
  }

  async getMyRatings(page = 1): Promise<PaginatedResponse<Rating>> {
    await this.sleep(150, 300);
    const org = this.currentUser?.organization;
    if (!org || org.type !== 'NGO' || !org.is_verified) {
      throw new Error('Only verified NGO users may view their ratings.');
    }

    const now = new Date();
    const myRatings = this.ratings
      .filter((r) => r.ngo === org.id && !r.is_hidden)
      .map((r) => ({
        ...r,
        is_editable: new Date(r.edit_deadline).getTime() > now.getTime(),
      }))
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const pageSize = 10;
    const total = myRatings.length;
    const start = (page - 1) * pageSize;
    const paged = myRatings.slice(start, start + pageSize);

    return {
      count: total,
      next: start + pageSize < total ? `?page=${page + 1}` : null,
      previous: page > 1 ? `?page=${page - 1}` : null,
      results: paged,
    };
  }

  async getBusinessRatings(businessId: number): Promise<BusinessRatingSummary> {
    await this.sleep(150, 300);
    const donor = this.donors.find((d) => d.id === businessId);
    const businessName = donor?.name || 'Partner Business';

    const reviews = this.ratings
      .filter((r) => r.business === businessId && !r.is_hidden)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const breakdown: Record<string, number> = { '1': 0, '2': 0, '3': 0, '4': 0, '5': 0 };
    let sum = 0;
    for (const r of reviews) {
      const starKey = String(r.stars);
      if (breakdown[starKey] !== undefined) {
        breakdown[starKey]++;
      }
      sum += r.stars;
    }
    const ratingAvg =
      reviews.length > 0 ? Math.round((sum / reviews.length) * 100) / 100 : null;

    return {
      business_id: businessId,
      business_name: businessName,
      rating_avg: ratingAvg,
      rating_count: reviews.length,
      breakdown,
      recent_reviews: reviews.slice(0, 5),
    };
  }

  // --- Platform Administration Methods (Admin Portal) ---

  async getAdminStats(): Promise<PlatformStats> {
    await this.sleep(150, 300);
    const businesses = this.adminOrganizations.filter((o) => o.org_type === 'BUSINESS').length;
    const ngos = this.adminOrganizations.filter((o) => o.org_type === 'NGO').length;
    const pendingVerifs = this.adminOrganizations.filter(
      (o) => o.org_type === 'NGO' && o.verification_status === 'PENDING'
    ).length;
    const openIssues = this.adminIssues.filter((i) => i.status === 'OPEN').length;

    const visibleRatings = this.adminRatings.filter((r) => !r.is_hidden);
    const avgRating =
      visibleRatings.length > 0
        ? Math.round((visibleRatings.reduce((sum, r) => sum + r.stars, 0) / visibleRatings.length) * 100) / 100
        : null;

    const signupsPerWeek = [
      { week: '2026-08-25', label: 'Aug 25', total: 6, count: 6, signups: 6, businesses: 4, ngos: 2 },
      { week: '2026-09-01', label: 'Sep 01', total: 9, count: 9, signups: 9, businesses: 5, ngos: 4 },
      { week: '2026-09-08', label: 'Sep 08', total: 12, count: 12, signups: 12, businesses: 7, ngos: 5 },
      { week: '2026-09-15', label: 'Sep 15', total: 15, count: 15, signups: 15, businesses: 9, ngos: 6 },
      { week: '2026-09-22', label: 'Sep 22', total: 19, count: 19, signups: 19, businesses: 11, ngos: 8 },
      { week: '2026-09-29', label: 'Sep 29', total: 24, count: 24, signups: 24, businesses: 14, ngos: 10 },
      { week: '2026-10-06', label: 'Oct 06', total: 31, count: 31, signups: 31, businesses: 18, ngos: 13 },
      { week: '2026-10-13', label: 'Oct 13', total: 38, count: 38, signups: 38, businesses: 22, ngos: 16 },
    ];

    const needsApproval = this.adminOrganizations
      .filter((o) => o.org_type === 'NGO' && o.verification_status === 'PENDING')
      .slice(0, 5)
      .map((o) => ({
        id: o.id,
        name: o.name,
        phone: o.phone,
        address: o.address,
        created_at: o.created_at,
      }));

    const recentIssues = this.adminIssues
      .filter((i) => i.status === 'OPEN')
      .slice(0, 5)
      .map((i) => ({
        id: i.id,
        category: i.category,
        priority: i.priority,
        description: i.description,
        reporter_org__name: i.reporter_org_name,
        created_at: i.created_at,
      }));

    return {
      total_businesses: businesses,
      total_ngos: ngos,
      pending_verifications: pendingVerifs,
      pending_ngo_verifications: pendingVerifs,
      open_issues: openIssues,
      total_kg_donated: 3840.5,
      active_listings: 6,
      average_platform_rating: avgRating,
      average_rating: avgRating,
      total_ratings: visibleRatings.length,
      signups_per_week: signupsPerWeek,
      needs_approval_queue: needsApproval,
      open_issues_queue: recentIssues,
    };
  }

  async getAdminOrganizations(params?: {
    org_type?: string;
    is_verified?: boolean | string;
    verification_status?: string;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminOrganization>> {
    await this.sleep(150, 300);
    let list = [...this.adminOrganizations];

    if (params?.org_type) {
      list = list.filter((o) => o.org_type.toLowerCase() === params.org_type?.toLowerCase());
    }
    if (params?.is_verified !== undefined) {
      const boolVal = String(params.is_verified).toLowerCase() === 'true';
      list = list.filter((o) => o.is_verified === boolVal);
    }
    if (params?.verification_status) {
      list = list.filter((o) => o.verification_status.toLowerCase() === params.verification_status?.toLowerCase());
    }
    if (params?.search) {
      const q = params.search.toLowerCase();
      list = list.filter((o) => o.name.toLowerCase().includes(q) || o.address.toLowerCase().includes(q));
    }

    return {
      count: list.length,
      next: null,
      previous: null,
      results: list,
    };
  }

  async getAdminOrganization(id: number): Promise<AdminOrganization> {
    await this.sleep(150, 300);
    const org = this.adminOrganizations.find((o) => o.id === id);
    if (!org) {
      throw new Error(`Organization #${id} not found.`);
    }
    return org;
  }

  async verifyOrganization(id: number, note = ''): Promise<AdminOrganization> {
    await this.sleep(200, 400);
    const org = this.adminOrganizations.find((o) => o.id === id);
    if (!org) throw new Error(`Organization #${id} not found.`);

    org.verification_status = 'VERIFIED';
    org.is_verified = true;
    org.verified_at = new Date().toISOString();
    if (note) org.verification_note = note;

    this.adminAuditLogs.unshift({
      id: Date.now(),
      admin_user: 99,
      admin_username: 'admin_sys',
      admin_email: 'admin@surplussync.com',
      action: 'ORGANIZATION_VERIFY',
      target_type: 'Organization',
      target_id: String(id),
      details: { note },
      created_at: new Date().toISOString(),
    });

    return { ...org };
  }

  async rejectOrganization(id: number, reason: string): Promise<AdminOrganization> {
    await this.sleep(200, 400);
    if (!reason?.trim()) throw new Error('A reason is required to reject an organization.');

    const org = this.adminOrganizations.find((o) => o.id === id);
    if (!org) throw new Error(`Organization #${id} not found.`);

    org.verification_status = 'REJECTED';
    org.is_verified = false;
    org.verification_note = reason;

    this.adminAuditLogs.unshift({
      id: Date.now(),
      admin_user: 99,
      admin_username: 'admin_sys',
      admin_email: 'admin@surplussync.com',
      action: 'ORGANIZATION_REJECT',
      target_type: 'Organization',
      target_id: String(id),
      details: { reason },
      created_at: new Date().toISOString(),
    });

    return { ...org };
  }

  async suspendOrganization(id: number, reason = ''): Promise<AdminOrganization> {
    await this.sleep(200, 400);
    const org = this.adminOrganizations.find((o) => o.id === id);
    if (!org) throw new Error(`Organization #${id} not found.`);

    org.verification_status = 'SUSPENDED';
    org.is_verified = false;
    if (reason) org.verification_note = reason;

    this.adminAuditLogs.unshift({
      id: Date.now(),
      admin_user: 99,
      admin_username: 'admin_sys',
      admin_email: 'admin@surplussync.com',
      action: 'ORGANIZATION_SUSPEND',
      target_type: 'Organization',
      target_id: String(id),
      details: { reason },
      created_at: new Date().toISOString(),
    });

    return { ...org };
  }

  async reinstateOrganization(id: number, reason = ''): Promise<AdminOrganization> {
    await this.sleep(200, 400);
    const org = this.adminOrganizations.find((o) => o.id === id);
    if (!org) throw new Error(`Organization #${id} not found.`);

    org.verification_status = 'VERIFIED';
    org.is_verified = true;
    org.verified_at = new Date().toISOString();
    if (reason) org.verification_note = reason;

    this.adminAuditLogs.unshift({
      id: Date.now(),
      admin_user: 99,
      admin_username: 'admin_sys',
      admin_email: 'admin@surplussync.com',
      action: 'ORGANIZATION_REINSTATE',
      target_type: 'Organization',
      target_id: String(id),
      details: { reason },
      created_at: new Date().toISOString(),
    });

    return { ...org };
  }

  async getAdminIssues(params?: {
    status?: string;
    category?: string;
    priority?: string;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminIssue>> {
    await this.sleep(150, 300);
    let list = [...this.adminIssues];

    if (params?.status) {
      list = list.filter((i) => i.status.toLowerCase() === params.status?.toLowerCase());
    }
    if (params?.category) {
      list = list.filter((i) => i.category.toLowerCase() === params.category?.toLowerCase());
    }
    if (params?.priority) {
      list = list.filter((i) => i.priority.toLowerCase() === params.priority?.toLowerCase());
    }
    if (params?.search) {
      const q = params.search.toLowerCase();
      list = list.filter(
        (i) =>
          i.description.toLowerCase().includes(q) ||
          i.reporter_name.toLowerCase().includes(q) ||
          i.reporter_org_name.toLowerCase().includes(q)
      );
    }

    return {
      count: list.length,
      next: null,
      previous: null,
      results: list,
    };
  }

  async updateAdminIssue(
    id: number,
    patch: Partial<{
      status: IssueStatus;
      priority: IssuePriority;
      admin_notes: string;
      assigned_to: number | null;
    }>
  ): Promise<AdminIssue> {
    await this.sleep(200, 350);
    const issue = this.adminIssues.find((i) => i.id === id);
    if (!issue) throw new Error(`Issue #${id} not found.`);

    Object.assign(issue, patch, { updated_at: new Date().toISOString() });
    if (patch.status === 'RESOLVED' || patch.status === 'DISMISSED') {
      issue.resolved_by = 99;
      issue.resolved_by_name = 'admin_sys';
      issue.resolved_at = new Date().toISOString();
    }

    this.adminAuditLogs.unshift({
      id: Date.now(),
      admin_user: 99,
      admin_username: 'admin_sys',
      admin_email: 'admin@surplussync.com',
      action: 'ISSUE_UPDATE',
      target_type: 'Issue',
      target_id: String(id),
      details: { ...patch },
      created_at: new Date().toISOString(),
    });

    return { ...issue };
  }

  async getAdminRatings(params?: {
    stars?: number;
    business?: number;
    ngo?: number;
    is_hidden?: boolean;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminRating>> {
    await this.sleep(150, 300);
    let list = [...this.adminRatings];

    if (params?.stars) {
      list = list.filter((r) => r.stars === Number(params.stars));
    }
    if (params?.business) {
      list = list.filter((r) => r.business === Number(params.business));
    }
    if (params?.ngo) {
      list = list.filter((r) => r.ngo === Number(params.ngo));
    }
    if (params?.is_hidden !== undefined) {
      list = list.filter((r) => r.is_hidden === Boolean(params.is_hidden));
    }
    if (params?.search) {
      const q = params.search.toLowerCase();
      list = list.filter(
        (r) =>
          r.comment.toLowerCase().includes(q) ||
          r.business_name.toLowerCase().includes(q) ||
          r.ngo_name.toLowerCase().includes(q)
      );
    }

    return {
      count: list.length,
      next: null,
      previous: null,
      results: list,
    };
  }

  async hideRating(id: number, reason: string): Promise<AdminRating> {
    await this.sleep(200, 350);
    if (!reason?.trim()) throw new Error('A reason is required to hide a rating.');

    const rating = this.adminRatings.find((r) => r.id === id);
    if (!rating) throw new Error(`Rating #${id} not found.`);

    rating.is_hidden = true;
    rating.hidden_reason = reason;
    rating.updated_at = new Date().toISOString();

    this.adminAuditLogs.unshift({
      id: Date.now(),
      admin_user: 99,
      admin_username: 'admin_sys',
      admin_email: 'admin@surplussync.com',
      action: 'RATING_HIDE',
      target_type: 'Rating',
      target_id: String(id),
      details: { reason, stars: rating.stars },
      created_at: new Date().toISOString(),
    });

    return { ...rating };
  }

  async unhideRating(id: number, reason: string): Promise<AdminRating> {
    await this.sleep(200, 350);
    if (!reason?.trim()) throw new Error('A reason is required to unhide a rating.');

    const rating = this.adminRatings.find((r) => r.id === id);
    if (!rating) throw new Error(`Rating #${id} not found.`);

    rating.is_hidden = false;
    rating.hidden_reason = reason;
    rating.updated_at = new Date().toISOString();

    this.adminAuditLogs.unshift({
      id: Date.now(),
      admin_user: 99,
      admin_username: 'admin_sys',
      admin_email: 'admin@surplussync.com',
      action: 'RATING_UNHIDE',
      target_type: 'Rating',
      target_id: String(id),
      details: { reason, stars: rating.stars },
      created_at: new Date().toISOString(),
    });

    return { ...rating };
  }

  async getAdminAuditLogs(params?: {
    action?: string;
    target_type?: string;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminAuditLog>> {
    await this.sleep(150, 300);
    let list = [...this.adminAuditLogs];

    if (params?.action) {
      list = list.filter((l) => l.action.toLowerCase() === params.action?.toLowerCase());
    }
    if (params?.target_type) {
      list = list.filter((l) => l.target_type.toLowerCase() === params.target_type?.toLowerCase());
    }
    if (params?.search) {
      const q = params.search.toLowerCase();
      list = list.filter(
        (l) =>
          l.action.toLowerCase().includes(q) ||
          l.admin_username.toLowerCase().includes(q) ||
          l.target_type.toLowerCase().includes(q)
      );
    }

    return {
      count: list.length,
      next: null,
      previous: null,
      results: list,
    };
  }

  async reportIssue(payload: IssueReportPayload): Promise<AdminIssue> {
    await this.sleep(200, 400);
    const newIssue: AdminIssue = {
      id: Date.now(),
      reporter: this.currentUser.id,
      reporter_name: this.currentUser.username,
      reporter_email: this.currentUser.email,
      reporter_org: this.currentUser.organization?.id || 1,
      reporter_org_name: this.currentUser.organization?.name || 'My Organization',
      reporter_org_type: this.currentUser.organization?.type || 'BUSINESS',
      target_org: payload.target_org || null,
      target_org_name: payload.target_org ? `Organization #${payload.target_org}` : null,
      target_org_type: null,
      claim: payload.claim || null,
      claim_title: payload.claim ? `Claim #${payload.claim}` : null,
      category: payload.category,
      description: payload.description,
      status: 'OPEN',
      priority: payload.priority || 'MEDIUM',
      admin_notes: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    this.adminIssues.unshift(newIssue);
    return newIssue;
  }

  async getMyIssues(): Promise<AdminIssue[]> {
    await this.sleep(150, 300);
    const orgId = this.currentUser.organization?.id;
    if (!orgId) return [];
    return this.adminIssues.filter((i) => i.reporter_org === orgId);
  }

  // --- Simulation Engine Accessors (Used in Task 2) ---
  public getInternalState() {
    return {
      products: this.products,
      batches: this.batches,
      transactions: this.transactions,
      listings: this.listings,
      claims: this.claims,
      ratings: this.ratings,
      alerts: this.alerts,
      alertRules: this.alertRules,
      notifications: this.notifications,
      adminOrganizations: this.adminOrganizations,
      adminIssues: this.adminIssues,
      adminRatings: this.adminRatings,
      adminAuditLogs: this.adminAuditLogs,
    };
  }

  public saveCustomData(): void {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem('surplussync_demo_custom_products', JSON.stringify(this.products));
      localStorage.setItem('surplussync_demo_custom_batches', JSON.stringify(this.batches));
    } catch {
      // Ignore quota exceeded
    }
  }

  public loadCustomData(): void {
    if (typeof window === 'undefined') return;
    try {
      const savedProds = localStorage.getItem('surplussync_demo_custom_products');
      if (savedProds) {
        const parsed = JSON.parse(savedProds);
        if (Array.isArray(parsed) && parsed.length > 0) {
          this.products = parsed;
        }
      }
      const savedBatches = localStorage.getItem('surplussync_demo_custom_batches');
      if (savedBatches) {
        const parsed = JSON.parse(savedBatches);
        if (Array.isArray(parsed) && parsed.length > 0) {
          this.batches = parsed;
        }
      }
    } catch {
      // Ignore parse errors
    }
  }

  public clearCustomData(): void {
    if (typeof window === 'undefined') return;
    try {
      localStorage.removeItem('surplussync_demo_custom_products');
      localStorage.removeItem('surplussync_demo_custom_batches');
    } catch {
      // Ignore
    }
  }
}

export const demoSource = new DemoSource();


