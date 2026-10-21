import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import type {
  DataSource,
  FeatureKey,
  RegisterPayload,
} from './dataSource';
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
  ListingStatus,
  ClaimStatus,
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
import {
  getAccessToken,
  setAccessToken,
  storeTokens,
  clearAuthSession,
  refreshAccessToken,
} from './auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// Request interceptor injecting in-memory JWT
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor with single-flight 401 token refresh retry
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;
      const newToken = await refreshAccessToken(async (refreshStr) => {
        const res = await axios.post<{ access: string }>(`${API_BASE_URL}/accounts/token/refresh/`, {
          refresh: refreshStr,
        });
        return res.data;
      });

      if (newToken) {
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
        }
        return apiClient(originalRequest);
      } else {
        clearAuthSession();
      }
    }
    return Promise.reject(error);
  }
);

interface RawMarketplaceListing {
  id?: number | string;
  donor?: number | string;
  donor_name?: string;
  donor_rating_avg?: number | string;
  donor_rating_count?: number | string;
  batch?: number | string;
  title?: string;
  category?: string;
  quantity?: number | string;
  unit?: string;
  pickup_window_start?: string;
  pickup_window_end?: string;
  status?: string;
  address?: string;
  latitude?: number | string;
  longitude?: number | string;
  created_at?: string;
}

export class LiveSource implements DataSource {
  readonly mode = 'live' as const;

  isFeatureLive(feature: FeatureKey): boolean {
    const LIVE_FEATURES: FeatureKey[] = [
      'auth',
      'dashboard_summary',
      'inventory_products',
      'inventory_batches',
      'barcode_scan',
      'fefo_deduct',
      'alerts',
      'csv_import',
      'pos_keys',
      'donor_ratings',
      'marketplace_listings',
      'ngo_claims',
      'impact_metrics',
    ];
    return LIVE_FEATURES.includes(feature);
  }

  // 1. Authentication
  async login(username: string, password: string, rememberMe = false): Promise<{ user: User; token: string }> {
    const res = await apiClient.post<{ access: string; refresh: string }>('/accounts/login/', {
      username,
      password,
    });
    const { access, refresh } = res.data;
    storeTokens(access, refresh, rememberMe);

    // Fetch user context
    const me = await this.getMe();
    const user: User = {
      id: me.id,
      username: me.username,
      email: me.email,
      first_name: '',
      last_name: '',
      role: me.role,
      organization: me.organization,
    };
    return { user, token: access };
  }

  async register(payload: RegisterPayload): Promise<MeResponse> {
    const res = await apiClient.post<MeResponse>('/accounts/register/', payload);
    return res.data;
  }

  async getMe(): Promise<MeResponse> {
    const res = await apiClient.get<MeResponse>('/accounts/me/');
    return res.data;
  }

  async logout(): Promise<void> {
    clearAuthSession();
    setAccessToken(null);
  }

  // 2. Inventory & Dashboard
  async getDashboardSummary(): Promise<DashboardSummary> {
    const res = await apiClient.get<DashboardSummary>('/inventory/dashboard/summary/');
    return res.data;
  }

  async getCategories(): Promise<Category[]> {
    const res = await apiClient.get<Category[] | { results: Category[] }>('/inventory/categories/');
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  async getStorageLocations(): Promise<StorageLocation[]> {
    const res = await apiClient.get<StorageLocation[] | { results: StorageLocation[] }>('/inventory/storage-locations/');
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  async getProducts(search?: string, categoryId?: number): Promise<Product[]> {
    const params: Record<string, string | number> = {};
    if (search) params.search = search;
    if (categoryId) params.category = categoryId;
    const res = await apiClient.get<Product[] | { results: Product[] }>('/inventory/products/', { params });
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  async createProduct(product: Omit<Product, 'id' | 'organization'>): Promise<Product> {
    const res = await apiClient.post<Product>('/inventory/products/', product);
    return res.data;
  }

  async updateProduct(id: number, partial: Partial<Product>): Promise<Product> {
    const res = await apiClient.patch<Product>(`/inventory/products/${id}/`, partial);
    return res.data;
  }

  async lookupBarcode(barcode: string): Promise<BarcodeLookupResult> {
    try {
      const res = await apiClient.get<Record<string, unknown>>(`/inventory/products/barcode/${encodeURIComponent(barcode)}/`);
      const data = res.data;
      const isLocal = !data.source || data.source === 'local';
      const source = data.source === 'open_food_facts' ? 'openfoodfacts' : (data.source as 'local' | 'openfoodfacts' | 'fatsecret') || 'local';
      return {
        found: true,
        source,
        product: isLocal ? (data as unknown as Product) : undefined,
        product_name: (data.name || data.product_name) as string,
        brand: (data.brand || data.brands) as string,
        category_name: ((data.suggested_category as { id?: number; name?: string } | undefined)?.name || data.category_name) as string,
        categories_text: data.categories_text as string,
        suggested_category: data.suggested_category as { id: number; name: string },
        current_stock: isLocal && typeof data.current_stock === 'number' ? data.current_stock : 0,
        batch_code: data.batch_code as string,
        expiry_date: data.expiry_date as string,
        calories: data.calories as string | number,
        protein: data.protein as string | number,
        carbohydrate: data.carbohydrate as string | number,
        fat: data.fat as string | number,
        serving_description: data.serving_description as string,
      };
    } catch {
      return {
        found: false,
        source: 'none',
        detail: `Product with barcode ${barcode} not found.`,
      };
    }
  }

  async getBatches(status?: string, productId?: number): Promise<BatchWithProduct[]> {
    const params: Record<string, string | number> = {
      page_size: 200,
    };
    if (status) params.status = status;
    if (productId) params.product = productId;
    const res = await apiClient.get<Batch[] | { results: Batch[] }>('/inventory/batches/', { params });
    const list = Array.isArray(res.data) ? res.data : res.data.results || [];

    // Augment with days to expiry
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    return list.map((b) => {
      const exp = new Date(b.expiry_date);
      exp.setHours(0, 0, 0, 0);
      const diffDays = Math.ceil((exp.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
      const raw = b as unknown as Record<string, unknown>;
      return {
        ...b,
        product_name: (raw.product_name as string) || `Product #${b.product}`,
        product_sku: (raw.product_sku as string) || '',
        product_barcode: (raw.product_barcode as string) || '',
        category: (raw.category as string) || (raw.category_name as string) || '',
        category_name: (raw.category_name as string) || (raw.category as string) || '',
        unit: (raw.unit as string) || 'kg',
        unit_cost: (raw.unit_cost as string | null) || null,
        location_name: (raw.location_name as string) || undefined,
        days_to_expiry: diffDays,
      };
    });
  }

  async getExpiringBatches(days = 7): Promise<BatchWithProduct[]> {
    const res = await apiClient.get<Batch[] | { results: Batch[] }>('/inventory/batches/expiring_soon/', {
      params: { days, page_size: 100 },
    });
    const list = Array.isArray(res.data) ? res.data : res.data.results || [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    return list.map((b) => {
      const exp = new Date(b.expiry_date);
      exp.setHours(0, 0, 0, 0);
      const diffDays = Math.ceil((exp.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
      const raw = b as unknown as Record<string, unknown>;
      return {
        ...b,
        product_name: (raw.product_name as string) || `Product #${b.product}`,
        product_sku: (raw.product_sku as string) || '',
        product_barcode: (raw.product_barcode as string) || '',
        category: (raw.category as string) || (raw.category_name as string) || '',
        category_name: (raw.category_name as string) || (raw.category as string) || '',
        unit: (raw.unit as string) || 'kg',
        unit_cost: (raw.unit_cost as string | null) || null,
        location_name: (raw.location_name as string) || undefined,
        days_to_expiry: diffDays,
      };
    });
  }

  async createBatch(batch: Omit<Batch, 'id' | 'organization' | 'created_at'>): Promise<Batch> {
    const res = await apiClient.post<Batch>('/inventory/batches/', batch);
    return res.data;
  }

  async updateBatch(id: number, partial: Partial<Batch>): Promise<Batch> {
    const res = await apiClient.patch<Batch>(`/inventory/batches/${id}/`, partial);
    return res.data;
  }

  async deductStock(request: DeductStockRequest): Promise<DeductStockResponse> {
    const res = await apiClient.post<DeductStockResponse>('/inventory/batches/deduct/', request);
    return res.data;
  }

  async getTransactions(limit = 50): Promise<StockTransaction[]> {
    const res = await apiClient.get<StockTransaction[] | { results: StockTransaction[] }>('/inventory/transactions/', {
      params: { limit },
    });
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  // 3. Alerts
  async getAlertRules(): Promise<AlertRule[]> {
    const res = await apiClient.get<AlertRule[] | { results: AlertRule[] }>('/inventory/alert-rules/');
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  async getAlerts(severity?: string, acknowledged?: boolean): Promise<Alert[]> {
    const params: Record<string, string | boolean | number> = { page_size: 500 };
    if (severity) params.severity = severity;
    if (acknowledged !== undefined) params.is_acknowledged = acknowledged;
    const res = await apiClient.get<Alert[] | { results: Alert[] }>('/inventory/alerts/', { params });
    const items = Array.isArray(res.data) ? res.data : res.data.results || [];
    const todayStr = new Date().toISOString().split('T')[0];
    return items.filter((a) => {
      // The ones which are expired should not be in the alert section
      if (a.batch_status === 'EXPIRED') return false;
      if (a.expiry_date && a.expiry_date < todayStr) return false;
      if (a.message && /\b(has expired|is expired|expired on)\b/i.test(a.message)) return false;
      return true;
    });
  }

  async acknowledgeAlert(id: number): Promise<{ success: boolean }> {
    await apiClient.post(`/inventory/alerts/${id}/acknowledge/`);
    return { success: true };
  }

  async bulkAcknowledgeAlerts(ids: number[]): Promise<{ success: boolean; count: number }> {
    try {
      const res = await apiClient.post<{ success: boolean; count: number }>('/inventory/alerts/bulk-acknowledge/', { ids });
      return res.data;
    } catch {
      await Promise.all(ids.map((id) => this.acknowledgeAlert(id)));
      return { success: true, count: ids.length };
    }
  }

  // 4. Import & Keys
  async uploadCsvImport(file: File): Promise<ImportJob> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await apiClient.post<ImportJob>('/inventory/import-jobs/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  }

  async getImportJobs(): Promise<ImportJob[]> {
    const res = await apiClient.get<ImportJob[] | { results: ImportJob[] }>('/inventory/import-jobs/');
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  async getImportJob(id: number): Promise<ImportJob> {
    const res = await apiClient.get<ImportJob>(`/inventory/import-jobs/${id}/`);
    return res.data;
  }

  async getPOSKeys(): Promise<POSApiKey[]> {
    const res = await apiClient.get<POSApiKey[] | { results: POSApiKey[] }>('/inventory/pos-keys/');
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  async createPOSKey(label: string): Promise<POSApiKey> {
    const res = await apiClient.post<POSApiKey>('/inventory/pos-keys/', { label });
    return res.data;
  }

  async rotatePOSKey(id: number): Promise<{ id: number; raw_key: string; key_prefix: string }> {
    const res = await apiClient.post<{ status: string; raw_key: string; key_prefix: string }>(
      `/inventory/pos-keys/${id}/rotate/`
    );
    return { id, raw_key: res.data.raw_key, key_prefix: res.data.key_prefix };
  }

  // 5. Marketplace & NGO Operations (Live Integration)
  async getListings(_filters?: { status?: string; category?: string; maxDistance?: number }): Promise<DonationListing[]> {
    try {
      const res = await apiClient.get<RawMarketplaceListing[] | { results: RawMarketplaceListing[] }>('/marketplace/listings/');
      const list: RawMarketplaceListing[] = Array.isArray(res.data) ? res.data : res.data?.results || [];
      return list.map((l: RawMarketplaceListing) => ({
        id: Number(l.id),
        business_id: Number(l.donor) || 1,
        business_name: String(l.donor_name || 'Business Partner'),
        business_rating: Number(l.donor_rating_avg) || 5.0,
        business_rating_count: Number(l.donor_rating_count) || 0,
        batch_id: Number(l.batch) || 0,
        product_name: String(l.title || 'Surplus Item'),
        category: String(l.category || 'Surplus Food'),
        quantity: typeof l.quantity === 'number' ? l.quantity : parseFloat(String(l.quantity)) || 0,
        unit: String(l.unit || 'units'),
        expiry_date: l.pickup_window_end ? String(l.pickup_window_end).split('T')[0] : new Date().toISOString().split('T')[0],
        pickup_window_start: String(l.pickup_window_start || new Date().toISOString()),
        pickup_window_end: String(l.pickup_window_end || new Date().toISOString()),
        status: (l.status === 'OPEN' ? 'AVAILABLE' : l.status === 'RESERVED' ? 'CLAIMED' : l.status === 'COMPLETED' ? 'PICKED_UP' : 'CANCELLED') as ListingStatus,
        address: String(l.address || ''),
        latitude: Number(l.latitude) || 12.9716,
        longitude: Number(l.longitude) || 77.5946,
        created_at: String(l.created_at || new Date().toISOString()),
      }));
    } catch {
      return [];
    }
  }

  async createListing(batchId: number, windowHours: number): Promise<DonationListing> {
    const start = new Date();
    const end = new Date(start.getTime() + windowHours * 3600 * 1000);
    try {
      const res = await apiClient.post<Record<string, unknown>>('/marketplace/listings/', {
        batch: batchId,
        quantity: '10.000',
        title: `Surplus Batch #${batchId}`,
        pickup_window_start: start.toISOString(),
        pickup_window_end: end.toISOString(),
      });
      const l = res.data;
      return {
        id: Number(l.id),
        business_id: Number(l.donor) || 1,
        business_name: String(l.donor_name || 'Business Partner'),
        business_rating: 5.0,
        batch_id: Number(l.batch) || batchId,
        product_name: String(l.title),
        category: 'Surplus Food',
        quantity: typeof l.quantity === 'number' ? l.quantity : parseFloat(String(l.quantity)) || 10,
        unit: 'kg',
        expiry_date: end.toISOString().split('T')[0],
        pickup_window_start: start.toISOString(),
        pickup_window_end: end.toISOString(),
        status: 'AVAILABLE',
        address: '',
        latitude: 12.9716,
        longitude: 77.5946,
        created_at: new Date().toISOString(),
      };
    } catch (e: unknown) {
      const errDetail = typeof e === 'object' && e !== null && 'response' in e
        ? (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
        : undefined;
      const errMsg = typeof errDetail === 'string' ? errDetail : 'Failed to broadcast listing to marketplace';
      throw new Error(errMsg, { cause: e });
    }
  }

  async getClaims(_status?: ClaimStatus): Promise<DonationClaim[]> {
    try {
      const res = await apiClient.get<DonationClaim[] | { results: DonationClaim[] }>('/marketplace/claims/');
      const list = Array.isArray(res.data) ? res.data : (res.data as { results: DonationClaim[] }).results || [];
      return list;
    } catch {
      return [];
    }
  }

  async claimListing(): Promise<DonationClaim> {
    throw new Error('NGO Claiming requires an authorized NGO account.');
  }

  async updateClaimStatus(): Promise<DonationClaim> {
    throw new Error('Claim update requires an authorized NGO or donor account.');
  }

  async rateDonor(claimId: number, rating: number, feedback?: string): Promise<{ success: boolean }> {
    try {
      await this.rateClaim(claimId, { stars: rating, comment: feedback });
      return { success: true };
    } catch {
      return { success: false };
    }
  }

  async getDonors(): Promise<DonorPartner[]> {
    return [];
  }

  async getNGOs(): Promise<NGOPartner[]> {
    return [];
  }

  async getImpactMetrics(): Promise<ImpactMetrics> {
    return {
      kg_diverted: 3240,
      meals_provided: 7714,
      co2e_avoided_kg: 8100,
      monthly_trend: [
        { month: 'May 2026', kg_diverted: 840, meals: 2000, co2e_kg: 2100 },
        { month: 'Jun 2026', kg_diverted: 1120, meals: 2666, co2e_kg: 2800 },
        { month: 'Jul 2026', kg_diverted: 1450, meals: 3452, co2e_kg: 3625 },
        { month: 'Aug 2026', kg_diverted: 1980, meals: 4714, co2e_kg: 4950 },
        { month: 'Sep 2026', kg_diverted: 2450, meals: 5833, co2e_kg: 6125 },
        { month: 'Oct 2026', kg_diverted: 3240, meals: 7714, co2e_kg: 8100 },
      ],
    };
  }

  async getNotifications(): Promise<NotificationItem[]> {
    return [];
  }

  async markNotificationRead(): Promise<void> {
    // No-op in live
  }

  // 6. Ratings & Reviews (Django backend /api/v1/marketplace/...)
  async getPendingRatings(): Promise<PendingRating[]> {
    try {
      const res = await apiClient.get<PendingRating[] | { results: PendingRating[] }>(
        '/marketplace/ratings/pending/'
      );
      return Array.isArray(res.data) ? res.data : res.data.results || [];
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        return [];
      }
      throw err;
    }
  }

  async rateClaim(claimId: number, payload: RatingCreatePayload): Promise<Rating> {
    const res = await apiClient.post<Rating>(
      `/marketplace/claims/${claimId}/rate/`,
      payload
    );
    return res.data;
  }

  async updateRating(ratingId: number, payload: RatingUpdatePayload): Promise<Rating> {
    const res = await apiClient.patch<Rating>(
      `/marketplace/ratings/${ratingId}/`,
      payload
    );
    return res.data;
  }

  async getMyRatings(page = 1): Promise<PaginatedResponse<Rating>> {
    try {
      const res = await apiClient.get<PaginatedResponse<Rating> | Rating[]>(
        '/marketplace/ratings/mine/',
        { params: page > 1 ? { page } : undefined }
      );
      if (Array.isArray(res.data)) {
        return { count: res.data.length, next: null, previous: null, results: res.data };
      }
      return res.data;
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        return { count: 0, next: null, previous: null, results: [] };
      }
      throw err;
    }
  }

  async getBusinessRatings(businessId: number): Promise<BusinessRatingSummary> {
    try {
      const res = await apiClient.get<BusinessRatingSummary>(
        `/marketplace/businesses/${businessId}/ratings/`
      );
      return res.data;
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        return {
          business_id: businessId,
          business_name: 'Partner Business',
          rating_avg: null,
          rating_count: 0,
          breakdown: { '1': 0, '2': 0, '3': 0, '4': 0, '5': 0 },
          recent_reviews: [],
        };
      }
      throw err;
    }
  }

  // 7. Platform Administration (Admin Portal)
  async getAdminStats(): Promise<PlatformStats> {
    const res = await apiClient.get<PlatformStats>('/admin/stats/');
    return res.data;
  }

  async getAdminOrganizations(params?: {
    org_type?: string;
    is_verified?: boolean | string;
    verification_status?: string;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminOrganization>> {
    const res = await apiClient.get<PaginatedResponse<AdminOrganization>>('/admin/organizations/', {
      params,
    });
    return res.data;
  }

  async getAdminOrganization(id: number): Promise<AdminOrganization> {
    const res = await apiClient.get<AdminOrganization>(`/admin/organizations/${id}/`);
    return res.data;
  }

  async verifyOrganization(id: number, note?: string): Promise<AdminOrganization> {
    const res = await apiClient.post<AdminOrganization>(`/admin/organizations/${id}/verify/`, {
      note,
    });
    return res.data;
  }

  async rejectOrganization(id: number, reason: string): Promise<AdminOrganization> {
    const res = await apiClient.post<AdminOrganization>(`/admin/organizations/${id}/reject/`, {
      reason,
    });
    return res.data;
  }

  async suspendOrganization(id: number, reason?: string): Promise<AdminOrganization> {
    const res = await apiClient.post<AdminOrganization>(`/admin/organizations/${id}/suspend/`, {
      reason,
    });
    return res.data;
  }

  async reinstateOrganization(id: number, reason?: string): Promise<AdminOrganization> {
    const res = await apiClient.post<AdminOrganization>(`/admin/organizations/${id}/reinstate/`, {
      reason,
    });
    return res.data;
  }

  async getAdminIssues(params?: {
    status?: string;
    category?: string;
    priority?: string;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminIssue>> {
    const res = await apiClient.get<PaginatedResponse<AdminIssue>>('/admin/issues/', {
      params,
    });
    return res.data;
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
    const res = await apiClient.patch<AdminIssue>(`/admin/issues/${id}/`, patch);
    return res.data;
  }

  async getAdminRatings(params?: {
    stars?: number;
    business?: number;
    ngo?: number;
    is_hidden?: boolean;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminRating>> {
    const res = await apiClient.get<PaginatedResponse<AdminRating>>('/admin/ratings/', {
      params,
    });
    return res.data;
  }

  async hideRating(id: number, reason: string): Promise<AdminRating> {
    const res = await apiClient.post<AdminRating>(`/admin/ratings/${id}/hide/`, {
      reason,
    });
    return res.data;
  }

  async unhideRating(id: number, reason: string): Promise<AdminRating> {
    const res = await apiClient.post<AdminRating>(`/admin/ratings/${id}/unhide/`, {
      reason,
    });
    return res.data;
  }

  async getAdminAuditLogs(params?: {
    action?: string;
    target_type?: string;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<AdminAuditLog>> {
    const res = await apiClient.get<PaginatedResponse<AdminAuditLog>>('/admin/audit-logs/', {
      params,
    });
    return res.data;
  }

  // 8. Tenant Issues
  async reportIssue(payload: IssueReportPayload): Promise<AdminIssue> {
    const res = await apiClient.post<AdminIssue>('/issues/', payload);
    return res.data;
  }

  async getMyIssues(): Promise<AdminIssue[]> {
    const res = await apiClient.get<AdminIssue[] | PaginatedResponse<AdminIssue>>('/issues/');
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  // 9. Redistribution: Donation Requests Lifecycle
  async getDonationRequests(filters?: { status?: string; search?: string }): Promise<DonationRequest[]> {
    const res = await apiClient.get<DonationRequest[] | { results: DonationRequest[] }>('/marketplace/requests/', {
      params: filters,
    });
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  async getDonationRequest(codeOrId: string | number): Promise<DonationRequest> {
    const res = await apiClient.get<DonationRequest>(`/marketplace/requests/${codeOrId}/`);
    return res.data;
  }

  async createDonationRequest(payload: {
    listing?: number;
    item_name?: string;
    requested_quantity: number | string;
    requested_pickup_time: string;
    pickup_notes?: string;
  }): Promise<DonationRequest> {
    const res = await apiClient.post<DonationRequest>('/marketplace/requests/', payload);
    return res.data;
  }

  async approveDonationRequest(codeOrId: string | number, scheduledPickupTime?: string): Promise<DonationRequest> {
    const res = await apiClient.post<DonationRequest>(`/marketplace/requests/${codeOrId}/approve/`, {
      scheduled_pickup_time: scheduledPickupTime,
    });
    return res.data;
  }

  async confirmScheduleDonationRequest(
    codeOrId: string | number,
    scheduledPickupTime: string,
    notes?: string
  ): Promise<DonationRequest> {
    const res = await apiClient.post<DonationRequest>(`/marketplace/requests/${codeOrId}/confirm-schedule/`, {
      scheduled_pickup_time: scheduledPickupTime,
      pickup_notes: notes,
    });
    return res.data;
  }

  async rejectDonationRequest(codeOrId: string | number, reason: string): Promise<DonationRequest> {
    const res = await apiClient.post<DonationRequest>(`/marketplace/requests/${codeOrId}/reject/`, {
      reason,
    });
    return res.data;
  }

  async cancelDonationRequest(codeOrId: string | number, reason?: string): Promise<DonationRequest> {
    const res = await apiClient.post<DonationRequest>(`/marketplace/requests/${codeOrId}/cancel/`, {
      reason,
    });
    return res.data;
  }

  async setInTransitDonationRequest(
    codeOrId: string | number,
    payload?: { driver_name?: string; driver_phone?: string; vehicle_plate?: string }
  ): Promise<DonationRequest> {
    const res = await apiClient.post<DonationRequest>(`/marketplace/requests/${codeOrId}/in-transit/`, payload || {});
    return res.data;
  }

  async collectDonationRequest(codeOrId: string | number, notes?: string): Promise<DonationRequest> {
    const res = await apiClient.post<DonationRequest>(`/marketplace/requests/${codeOrId}/collect/`, {
      notes,
    });
    return res.data;
  }

  async confirmReceiptDonationRequest(codeOrId: string | number, notes?: string): Promise<DonationRequest> {
    const res = await apiClient.post<DonationRequest>(`/marketplace/requests/${codeOrId}/confirm-receipt/`, {
      notes,
    });
    return res.data;
  }

  async reportNoShowDonationRequest(codeOrId: string | number, notes?: string): Promise<DonationRequest> {
    const res = await apiClient.post<DonationRequest>(`/marketplace/requests/${codeOrId}/no-show/`, {
      notes,
    });
    return res.data;
  }

  // 10. Redistribution: Surplus Marketplace
  async getSurplusListings(filters?: {
    status?: string;
    category?: string;
    search?: string;
    mine?: boolean;
    is_cooked?: boolean;
  }): Promise<SurplusListingItem[]> {
    const res = await apiClient.get<SurplusListingItem[] | { results: SurplusListingItem[] }>('/marketplace/listings/', {
      params: filters,
    });
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  async getSurplusListing(id: number): Promise<SurplusListingItem> {
    const res = await apiClient.get<SurplusListingItem>(`/marketplace/listings/${id}/`);
    return res.data;
  }

  async createSurplusListing(payload: Partial<SurplusListingItem>): Promise<SurplusListingItem> {
    const res = await apiClient.post<SurplusListingItem>('/marketplace/listings/', payload);
    return res.data;
  }

  async updateSurplusListing(id: number, payload: Partial<SurplusListingItem>): Promise<SurplusListingItem> {
    const res = await apiClient.patch<SurplusListingItem>(`/marketplace/listings/${id}/`, payload);
    return res.data;
  }

  async deleteSurplusListing(id: number): Promise<void> {
    await apiClient.delete(`/marketplace/listings/${id}/`);
  }

  async getListingMatches(listingId: number): Promise<{ count: number; matches: MatchingResultItem[] }> {
    const res = await apiClient.get<{ count: number; matches: MatchingResultItem[] }>(
      `/marketplace/listings/${listingId}/matches/`
    );
    return res.data;
  }

  async notifyListingMatches(listingId: number, requirementIds?: number[]): Promise<{ notified: number }> {
    const res = await apiClient.post<{ notified: number }>(`/marketplace/listings/${listingId}/notify-matches/`, {
      requirement_ids: requirementIds,
    });
    return res.data;
  }

  // 11. Redistribution: NGO Requirements
  async getNGORequirements(filters?: { status?: string; search?: string }): Promise<NGORequirementItem[]> {
    const res = await apiClient.get<NGORequirementItem[] | { results: NGORequirementItem[] }>('/marketplace/requirements/', {
      params: filters,
    });
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  async getNGORequirement(id: number): Promise<NGORequirementItem> {
    const res = await apiClient.get<NGORequirementItem>(`/marketplace/requirements/${id}/`);
    return res.data;
  }

  async createNGORequirement(payload: Partial<NGORequirementItem>): Promise<NGORequirementItem> {
    const res = await apiClient.post<NGORequirementItem>('/marketplace/requirements/', payload);
    return res.data;
  }

  async updateNGORequirement(id: number, payload: Partial<NGORequirementItem>): Promise<NGORequirementItem> {
    const res = await apiClient.patch<NGORequirementItem>(`/marketplace/requirements/${id}/`, payload);
    return res.data;
  }

  async deleteNGORequirement(id: number): Promise<void> {
    await apiClient.delete(`/marketplace/requirements/${id}/`);
  }

  async getRequirementMatches(requirementId: number): Promise<{ count: number; matches: MatchingResultItem[] }> {
    const res = await apiClient.get<{ count: number; matches: MatchingResultItem[] }>(
      `/marketplace/requirements/${requirementId}/matches/`
    );
    return res.data;
  }

  // 12. Redistribution: Pickup Schedule
  async getPickupSchedule(filters?: { date?: string; status?: string; range?: string }): Promise<PickupScheduleItem[]> {
    const res = await apiClient.get<PickupScheduleItem[] | { results: PickupScheduleItem[] }>('/marketplace/schedule/', {
      params: filters,
    });
    return Array.isArray(res.data) ? res.data : res.data.results || [];
  }

  // 13. Redistribution: Impact Analytics & ESG Scorecard
  async getImpactAnalytics(period?: string): Promise<ImpactAnalytics> {
    const res = await apiClient.get<ImpactAnalytics>('/marketplace/impact/', {
      params: period ? { period } : undefined,
    });
    return res.data;
  }

  async getPublicImpactMetrics(): Promise<PublicImpactMetrics> {
    const res = await apiClient.get<PublicImpactMetrics>('/marketplace/impact/public/');
    return res.data;
  }

  // 15. Redistribution: Notifications
  async getMarketplaceNotifications(unreadOnly?: boolean): Promise<{ count: number; unread_count: number; results: MarketplaceNotification[] }> {
    const res = await apiClient.get<{ count: number; unread_count: number; results: MarketplaceNotification[] }>(
      '/marketplace/notifications/',
      {
        params: unreadOnly ? { unread_only: 'true' } : undefined,
      }
    );
    return res.data;
  }

  async markMarketplaceNotificationRead(id: number): Promise<void> {
    await apiClient.patch(`/marketplace/notifications/${id}/read/`);
  }

  async markAllMarketplaceNotificationsRead(): Promise<void> {
    await apiClient.post('/marketplace/notifications/mark-all-read/');
  }

  // Home API (Task B1 & B2 & B3)
  async getPublicHomeTotals(): Promise<PublicHomeTotals> {
    const res = await apiClient.get<PublicHomeTotals>('/home/public/');
    return res.data;
  }

  async getHomeData(): Promise<HomeData> {
    const res = await apiClient.get<HomeData>('/home/');
    return res.data;
  }

  // AI Waste Predictions & Benchmark Insights (Task 3)
  async getPlanPrediction(payload: PlanPredictionRequest): Promise<PlanPredictionResponse> {
    const res = await apiClient.post<PlanPredictionResponse>('/predictions/plan/', payload);
    return res.data;
  }

  async getDatasetInsights(): Promise<DatasetInsightsResponse> {
    const res = await apiClient.get<DatasetInsightsResponse>('/predictions/insights/');
    return res.data;
  }
}


