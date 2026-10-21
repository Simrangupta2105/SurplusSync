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
  DonationRequest,
  SurplusListingItem,
  NGORequirementItem,
  PickupScheduleItem,
  ImpactAnalytics,
  PublicImpactMetrics,
  MarketplaceNotification,
  MatchingResultItem,
  PublicHomeTotals,
  HomeData,
  PlanPredictionRequest,
  PlanPredictionResponse,
  DatasetInsightsResponse,
} from '../types';

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  org_name: string;
  org_type: 'BUSINESS' | 'NGO';
  address?: string;
  phone?: string;
}

export type FeatureKey =
  | 'auth'
  | 'dashboard_summary'
  | 'inventory_products'
  | 'inventory_batches'
  | 'barcode_scan'
  | 'fefo_deduct'
  | 'alerts'
  | 'csv_import'
  | 'pos_keys'
  | 'marketplace_listings'
  | 'ngo_claims'
  | 'donor_ratings'
  | 'notifications'
  | 'impact_metrics';

export interface DataSource {
  readonly mode: 'live' | 'demo';
  isFeatureLive(feature: FeatureKey): boolean;

  // Authentication
  login(username: string, password: string, rememberMe?: boolean): Promise<{ user: User; token: string }>;
  register(payload: RegisterPayload): Promise<MeResponse>;
  getMe(): Promise<MeResponse>;
  logout(): Promise<void>;

  // Inventory & Dashboard
  getDashboardSummary(): Promise<DashboardSummary>;
  getCategories(): Promise<Category[]>;
  getStorageLocations(): Promise<StorageLocation[]>;
  getProducts(search?: string, categoryId?: number): Promise<Product[]>;
  createProduct(product: Omit<Product, 'id' | 'organization'>): Promise<Product>;
  updateProduct(id: number, partial: Partial<Product>): Promise<Product>;
  lookupBarcode(barcode: string): Promise<BarcodeLookupResult>;
  getBatches(status?: string, productId?: number): Promise<BatchWithProduct[]>;
  getExpiringBatches(days?: number): Promise<BatchWithProduct[]>;
  createBatch(batch: Omit<Batch, 'id' | 'organization' | 'created_at'>): Promise<Batch>;
  updateBatch(id: number, partial: Partial<Batch>): Promise<Batch>;
  deductStock(request: DeductStockRequest): Promise<DeductStockResponse>;
  getTransactions(limit?: number): Promise<StockTransaction[]>;

  // Alerts
  getAlertRules(): Promise<AlertRule[]>;
  getAlerts(severity?: string, acknowledged?: boolean): Promise<Alert[]>;
  acknowledgeAlert(id: number): Promise<{ success: boolean }>;
  bulkAcknowledgeAlerts(ids: number[]): Promise<{ success: boolean; count: number }>;

  // Import Jobs & POS API Keys
  uploadCsvImport(file: File): Promise<ImportJob>;
  getImportJobs(): Promise<ImportJob[]>;
  getImportJob(id: number): Promise<ImportJob>;
  getPOSKeys(): Promise<POSApiKey[]>;
  createPOSKey(label: string): Promise<POSApiKey>;
  rotatePOSKey(id: number): Promise<{ id: number; raw_key: string; key_prefix: string }>;

  // Marketplace & NGO Operations (LIVE = Coming Soon, DEMO = Active)
  getListings(filters?: { status?: string; category?: string; maxDistance?: number }): Promise<DonationListing[]>;
  createListing(batchId: number, windowHours: number): Promise<DonationListing>;
  getClaims(status?: ClaimStatus): Promise<DonationClaim[]>;
  claimListing(listingId: number, pickupEta: string, notes: string): Promise<DonationClaim>;
  updateClaimStatus(claimId: number, status: ClaimStatus): Promise<DonationClaim>;
  rateDonor(claimId: number, rating: number, feedback?: string): Promise<{ success: boolean }>;
  getDonors(): Promise<DonorPartner[]>;
  getNGOs(): Promise<NGOPartner[]>;
  getImpactMetrics(): Promise<ImpactMetrics>;
  getNotifications(): Promise<NotificationItem[]>;
  markNotificationRead(id: string): Promise<void>;

  // Ratings (NGO rating business)
  getPendingRatings(): Promise<PendingRating[]>;
  rateClaim(claimId: number, payload: RatingCreatePayload): Promise<Rating>;
  updateRating(ratingId: number, payload: RatingUpdatePayload): Promise<Rating>;
  getMyRatings(page?: number): Promise<PaginatedResponse<Rating>>;
  getBusinessRatings(businessId: number): Promise<BusinessRatingSummary>;

  // Platform Administration
  getAdminStats(): Promise<PlatformStats>;
  getAdminOrganizations(params?: {
    org_type?: string;
    is_verified?: boolean | string;
    verification_status?: string;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminOrganization>>;
  getAdminOrganization(id: number): Promise<AdminOrganization>;
  verifyOrganization(id: number, note?: string): Promise<AdminOrganization>;
  rejectOrganization(id: number, reason: string): Promise<AdminOrganization>;
  suspendOrganization(id: number, reason?: string): Promise<AdminOrganization>;
  reinstateOrganization(id: number, reason?: string): Promise<AdminOrganization>;

  getAdminIssues(params?: {
    status?: string;
    category?: string;
    priority?: string;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminIssue>>;
  updateAdminIssue(
    id: number,
    patch: Partial<{
      status: IssueStatus;
      priority: IssuePriority;
      admin_notes: string;
      assigned_to: number | null;
    }>
  ): Promise<AdminIssue>;

  getAdminRatings(params?: {
    stars?: number;
    business?: number;
    ngo?: number;
    is_hidden?: boolean;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminRating>>;
  hideRating(id: number, reason: string): Promise<AdminRating>;
  unhideRating(id: number, reason: string): Promise<AdminRating>;

  getAdminAuditLogs(params?: {
    action?: string;
    target_type?: string;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminAuditLog>>;

  // Issues (Tenant reporting)
  reportIssue(payload: IssueReportPayload): Promise<AdminIssue>;
  getMyIssues(): Promise<AdminIssue[]>;

  // Redistribution: Donation Requests Lifecycle (Task 2 & 4)
  getDonationRequests(filters?: { status?: string; search?: string }): Promise<DonationRequest[]>;
  getDonationRequest(codeOrId: string | number): Promise<DonationRequest>;
  createDonationRequest(payload: {
    listing?: number;
    item_name?: string;
    requested_quantity: number | string;
    requested_pickup_time: string;
    pickup_notes?: string;
  }): Promise<DonationRequest>;
  approveDonationRequest(codeOrId: string | number, scheduledPickupTime?: string): Promise<DonationRequest>;
  confirmScheduleDonationRequest(codeOrId: string | number, scheduledPickupTime: string, notes?: string): Promise<DonationRequest>;
  rejectDonationRequest(codeOrId: string | number, reason: string): Promise<DonationRequest>;
  cancelDonationRequest(codeOrId: string | number, reason?: string): Promise<DonationRequest>;
  setInTransitDonationRequest(
    codeOrId: string | number,
    payload?: { driver_name?: string; driver_phone?: string; vehicle_plate?: string }
  ): Promise<DonationRequest>;
  collectDonationRequest(codeOrId: string | number, notes?: string): Promise<DonationRequest>;
  confirmReceiptDonationRequest(codeOrId: string | number, notes?: string): Promise<DonationRequest>;
  reportNoShowDonationRequest(codeOrId: string | number, notes?: string): Promise<DonationRequest>;

  // Redistribution: Surplus Marketplace
  getSurplusListings(filters?: {
    status?: string;
    category?: string;
    search?: string;
    mine?: boolean;
    is_cooked?: boolean;
  }): Promise<SurplusListingItem[]>;
  getSurplusListing(id: number): Promise<SurplusListingItem>;
  createSurplusListing(payload: Partial<SurplusListingItem>): Promise<SurplusListingItem>;
  updateSurplusListing(id: number, payload: Partial<SurplusListingItem>): Promise<SurplusListingItem>;
  deleteSurplusListing(id: number): Promise<void>;
  getListingMatches(listingId: number): Promise<{ count: number; matches: MatchingResultItem[] }>;
  notifyListingMatches(listingId: number, requirementIds?: number[]): Promise<{ notified: number }>;

  // Redistribution: NGO Requirements & Matching (Task 3 & 4)
  getNGORequirements(filters?: { status?: string; search?: string }): Promise<NGORequirementItem[]>;
  getNGORequirement(id: number): Promise<NGORequirementItem>;
  createNGORequirement(payload: Partial<NGORequirementItem>): Promise<NGORequirementItem>;
  updateNGORequirement(id: number, payload: Partial<NGORequirementItem>): Promise<NGORequirementItem>;
  deleteNGORequirement(id: number): Promise<void>;
  getRequirementMatches(requirementId: number): Promise<{ count: number; matches: MatchingResultItem[] }>;

  // Redistribution: Pickup Schedule
  getPickupSchedule(filters?: { date?: string; status?: string; range?: string }): Promise<PickupScheduleItem[]>;

  // Redistribution: Impact Analytics & ESG Scorecard
  getImpactAnalytics(period?: string): Promise<ImpactAnalytics>;
  getPublicImpactMetrics(): Promise<PublicImpactMetrics>;

  // Redistribution: Notifications Center
  getMarketplaceNotifications(unreadOnly?: boolean): Promise<{ count: number; unread_count: number; results: MarketplaceNotification[] }>;
  markMarketplaceNotificationRead(id: number): Promise<void>;
  markAllMarketplaceNotificationsRead(): Promise<void>;

  // Home API (Task B1 & B2 & B3)
  getPublicHomeTotals(): Promise<PublicHomeTotals>;
  getHomeData(): Promise<HomeData>;

  // AI Waste Predictions & Benchmark Insights (Task 3)
  getPlanPrediction(payload: PlanPredictionRequest): Promise<PlanPredictionResponse>;
  getDatasetInsights(): Promise<DatasetInsightsResponse>;
}


