/**
 * SurplusSync Domain Types
 * Strictly mirrors the Django REST Framework models and serializers:
 * - accounts (User, Organization)
 * - inventory (Category, StorageLocation, Product, Batch, StockTransaction, AlertRule, Alert, ImportJob, POSApiKey)
 * - demo extensions (Marketplace, Claims, Ratings, Impact)
 */

export type OrganizationType = 'BUSINESS' | 'NGO';
export type UserRole = 'OWNER' | 'STAFF';

export interface Organization {
  id: number;
  name: string;
  org_type: OrganizationType;
  address: string;
  latitude: number | null;
  longitude: number | null;
  phone: string;
  is_verified: boolean;
  created_at: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  is_platform_admin?: boolean;
  organization: {
    id: number;
    name: string;
    type: OrganizationType;
    is_verified: boolean;
  } | null;
}

export interface MeResponse {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  is_platform_admin?: boolean;
  organization: {
    id: number;
    name: string;
    type: OrganizationType;
    is_verified: boolean;
    address?: string;
    phone?: string;
    latitude?: number;
    longitude?: number;
  } | null;
}

export type PerishabilityRisk = 1 | 2 | 3 | 4;
export type StorageType = 'AMBIENT' | 'CHILLED' | 'FROZEN';

export interface Category {
  id: number;
  name: string;
  parent: number | null;
  perishability_risk: PerishabilityRisk;
  storage_type: StorageType;
  default_shelf_life_days: number | null;
}

export interface StorageLocation {
  id: number;
  organization: number;
  name: string;
  storage_type: StorageType;
  capacity: string | null;
}

export interface Product {
  id: number;
  organization: number;
  name: string;
  sku: string;
  barcode: string;
  category: number;
  unit: string;
  unit_cost: string | null;
  reorder_level: string;
  is_active: boolean;
  category_name?: string;
  shelf_life_days?: number;
  selling_price?: string;
  cost_price?: string;
  min_stock_level?: number;
}

export type BatchStatus = 'ACTIVE' | 'EXPIRED' | 'DEPLETED' | 'DONATED';

export interface Batch {
  id: number;
  organization: number;
  product: number;
  location: number | null;
  batch_code: string;
  quantity: string;
  initial_quantity?: string | number;
  current_quantity?: string | number;
  received_date: string;
  expiry_date: string;
  manufacturing_date?: string;
  unit?: string;
  status: BatchStatus;
  created_at: string;
}

export interface BatchWithProduct extends Batch {
  product_name: string;
  product_sku: string;
  product_barcode: string;
  category?: string;
  category_name?: string;
  unit: string;
  unit_cost: string | null;
  location_name?: string;
  days_to_expiry: number;
}

export type TransactionType = 'RECEIVED' | 'SOLD' | 'WASTED' | 'DISCARDED' | 'DONATED' | 'ADJUSTMENT';

export interface StockTransaction {
  id: number;
  organization: number;
  batch: number;
  txn_type: TransactionType;
  quantity: string;
  reason: string;
  source: string;
  created_by: number | null;
  created_at: string;
  external_id: string;
  batch_code?: string;
  product_name?: string;
}

export interface AlertRule {
  id: number;
  organization: number;
  category: number | null;
  days_before_expiry: number;
  is_active: boolean;
}

export type AlertSeverity = 'INFO' | 'WARNING' | 'CRITICAL';

export interface Alert {
  id: number;
  organization: number;
  batch: number;
  rule: number | null;
  severity: AlertSeverity;
  message: string;
  is_acknowledged: boolean;
  created_at: string;
  batch_code?: string;
  batch_status?: BatchStatus;
  product_name?: string;
  expiry_date?: string;
}

export interface ImportJob {
  id: number;
  organization: number;
  file: string;
  status: 'PENDING' | 'PROCESSING' | 'DONE' | 'FAILED' | 'CANCELLED' | 'PARTIAL';
  total_rows?: number;
  processed_rows?: number;
  rows_ok: number;
  rows_failed: number;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string;
  error_report: Array<{ row?: number; error?: string; raw?: unknown; data?: Record<string, string> }>;
  worker_may_be_down?: boolean;
  created_at: string;
}

export interface POSApiKey {
  id: number;
  organization: number;
  label: string;
  is_active: boolean;
  raw_key?: string;
  key_prefix?: string;
}

export interface DashboardSummary {
  total_active_batches: number;
  total_active_quantity: string;
  batches_expiring_48h: number;
  critical_alerts_unacknowledged: number;
  wasted_value_30d: string;
  donated_value_30d: string;
  missing_cost_items: number;
}

export interface DeductStockRequest {
  product?: number;
  barcode?: string;
  sku?: string;
  quantity: number | string;
  reason?: string;
  txn_type?: 'SOLD' | 'DISCARDED';
  external_id?: string;
}

export interface DeductStockResponse {
  message: string;
  product_id: number;
  total_deducted: string;
  deductions: Array<{
    batch_id: number;
    batch_code: string;
    deducted_quantity: string;
    remaining_batch_quantity: string;
    status: BatchStatus;
  }>;
  idempotent_replay: boolean;
}

export interface BarcodeLookupResult {
  found: boolean;
  source: 'local' | 'openfoodfacts' | 'fatsecret' | 'none';
  product?: Product;
  product_name?: string;
  brand?: string;
  category_name?: string;
  current_stock?: number;
  batch_code?: string;
  expiry_date?: string;
  detail?: string;
  calories?: string | number;
  protein?: string | number;
  carbohydrate?: string | number;
  fat?: string | number;
  categories_text?: string;
  suggested_category?: { id: number; name: string; default_shelf_life_days?: number };
  serving_description?: string;
}

/* =========================================================================
   RATINGS & MARKETPLACE TYPES (Mirroring Django backend serializers)
   ========================================================================= */

export interface PendingRating {
  id: number;
  claim_id?: number;
  donor_id: number;
  donor_name: string;
  donor_rating_avg?: number | null;
  donor_rating_count?: number;
  item: string;
  listing_title: string;
  quantity: string | number;
  pickup_date?: string | null;
  pickup_eta?: string | null;
  updated_at?: string;
}

export interface Rating {
  id: number;
  claim: number;
  ngo: number;
  ngo_name?: string;
  business: number;
  business_name?: string;
  stars: number;
  comment?: string;
  is_hidden?: boolean;
  is_editable: boolean;
  edit_deadline: string;
  created_at: string;
  updated_at: string;
}

export interface RatingCreatePayload {
  stars: number;
  comment?: string;
}

export interface RatingUpdatePayload {
  stars?: number;
  comment?: string;
}

export interface BusinessRatingSummary {
  business_id: number;
  business_name: string;
  rating_avg: number | null;
  rating_count: number;
  breakdown: Record<string, number>;
  recent_reviews: Rating[];
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type ListingStatus = 'AVAILABLE' | 'CLAIMED' | 'PICKED_UP' | 'CANCELLED';

export interface DonationListing {
  id: number;
  business_id: number;
  business_name: string;
  business_rating: number;
  business_rating_count?: number;
  batch_id: number;
  product_name: string;
  category: string;
  quantity: number;
  unit: string;
  expiry_date: string;
  pickup_window_start: string;
  pickup_window_end: string;
  status: ListingStatus;
  address: string;
  latitude: number;
  longitude: number;
  distance_km?: number;
  created_at: string;
}

export type ClaimStatus = 'PENDING' | 'CONFIRMED' | 'PICKED_UP' | 'CANCELLED';

export interface DonationClaim {
  id: number;
  listing_id: number;
  listing?: DonationListing;
  ngo_id: number;
  ngo_name: string;
  status: ClaimStatus;
  pickup_eta: string;
  notes: string;
  donor_rating?: number;
  donor_feedback?: string;
  created_at: string;
  updated_at: string;
}

export interface DonorPartner {
  id: number;
  name: string;
  rating: number;
  rating_count: number;
  verified: boolean;
  address: string;
  phone: string;
  latitude: number;
  longitude: number;
}

export interface NGOPartner {
  id: number;
  name: string;
  verified: boolean;
  address: string;
  phone: string;
  latitude: number;
  longitude: number;
  total_rescued_kg: number;
}

export interface NotificationItem {
  id: string;
  type: 'ALERT' | 'CLAIM' | 'LISTING' | 'SYSTEM';
  title: string;
  message: string;
  timestamp: string;
  is_read: boolean;
  action_url?: string;
}

export interface ImpactMetrics {
  kg_diverted: number;
  meals_provided: number;
  co2e_avoided_kg: number;
  monthly_trend: Array<{
    month: string;
    kg_diverted: number;
    meals: number;
    co2e_kg: number;
  }>;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface AuthSession {
  user: User;
  tokens: AuthTokens;
}

// Convenient type aliases
export type POSKey = POSApiKey;
export type ScanResult = BarcodeLookupResult;
export type CSVImportResult = ImportJob;

/* =========================================================================
   PLATFORM ADMINISTRATION TYPES (Admin Portal)
   ========================================================================= */

export type VerificationStatus = 'PENDING' | 'VERIFIED' | 'REJECTED' | 'SUSPENDED';

export interface AdminOrgUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  is_active: boolean;
  date_joined: string;
  last_login: string | null;
}

export interface AdminOrgActivity {
  listings: Array<{
    id: number;
    title: string;
    quantity: string | number;
    status: string;
    created_at: string;
  }>;
  batches: Array<{
    id: number;
    product__name: string;
    quantity: string | number;
    status: string;
    expiry_date: string;
    created_at: string;
  }>;
  claims: Array<{
    id: number;
    listing_id: number;
    listing__title: string;
    listing__donor__name: string;
    status: string;
    pickup_eta: string | null;
    created_at: string;
  }>;
  ratings: Array<{
    id: number;
    stars: number;
    comment: string;
    ngo__name?: string;
    business__name?: string;
    created_at: string;
  }>;
  audit_logs: Array<{
    id: number;
    action: string;
    admin_user__username: string;
    details: Record<string, unknown>;

    created_at: string;
  }>;
}

export interface AdminOrganization {
  id: number;
  name: string;
  org_type: OrganizationType;
  address: string;
  latitude: number | null;
  longitude: number | null;
  phone: string;
  is_verified: boolean;
  verification_status: VerificationStatus;
  verification_note: string;
  verified_at: string | null;
  created_at: string;
  users_count?: number;
  batches_count?: number;
  claims_count?: number;
  listings_count?: number;
  users?: AdminOrgUser[];
  recent_activity?: AdminOrgActivity;
}

export type IssueCategory =
  | 'FOOD_QUALITY'
  | 'NO_SHOW'
  | 'WRONG_QUANTITY'
  | 'ABUSE'
  | 'TECHNICAL'
  | 'OTHER';

export type IssueStatus = 'OPEN' | 'IN_REVIEW' | 'RESOLVED' | 'DISMISSED';

export type IssuePriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface AdminIssue {
  id: number;
  reporter: number;
  reporter_name: string;
  reporter_email?: string;
  reporter_org: number;
  reporter_org_name: string;
  reporter_org_type: OrganizationType;
  target_org: number | null;
  target_org_name: string | null;
  target_org_type: OrganizationType | null;
  claim: number | null;
  claim_title: string | null;
  claim_status?: string | null;
  category: IssueCategory;
  description: string;
  status: IssueStatus;
  priority: IssuePriority;
  admin_notes: string;
  assigned_to?: number | null;
  assigned_to_name?: string | null;
  assigned_to_email?: string | null;
  resolved_by?: number | null;
  resolved_by_name?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IssueReportPayload {
  category: IssueCategory;
  description: string;
  target_org?: number;
  claim?: number;
  priority?: IssuePriority;
}

export interface AdminRating {
  id: number;
  stars: number;
  comment: string;
  is_hidden: boolean;
  hidden_reason: string;
  business: number;
  business_name: string;
  ngo: number;
  ngo_name: string;
  claim: number;
  claim_title: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminAuditLog {
  id: number;
  admin_user: number;
  admin_username: string;
  admin_email: string;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;

  created_at: string;
}

export interface SignupWeekBucket {
  week: string;
  label: string;
  total: number;
  count: number;
  signups: number;
  businesses: number;
  ngos: number;
}

export interface PlatformStats {
  total_businesses: number;
  total_ngos: number;
  pending_verifications: number;
  pending_ngo_verifications: number;
  open_issues: number;
  total_kg_donated: number;
  active_listings: number;
  average_platform_rating: number | null;
  average_rating: number | null;
  total_ratings?: number;
  signups_per_week: SignupWeekBucket[];
  needs_approval_queue?: Array<{
    id: number;
    name: string;
    phone: string;
    address: string;
    created_at: string;
  }>;
  open_issues_queue?: Array<{
    id: number;
    category: string;
    priority: string;
    description: string;
    reporter_org__name: string;
    created_at: string;
  }>;
}

