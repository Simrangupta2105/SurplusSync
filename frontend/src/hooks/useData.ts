import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dataSource } from '../services';
import type {
  Product,
  Batch,
  DeductStockRequest,
  ClaimStatus,
  RatingCreatePayload,
  RatingUpdatePayload,
  IssueReportPayload,
  IssueStatus,
  IssuePriority,
  ImportJob,
  SurplusListingItem,
  NGORequirementItem,
  PlanPredictionRequest,
} from '../types';


// Query Keys
export const QUERY_KEYS = {
  dashboardSummary: ['dashboard', 'summary'],
  categories: ['categories'],
  locations: ['locations'],
  products: (search?: string, catId?: number) => ['products', { search, catId }],
  batches: (status?: string, prodId?: number) => ['batches', { status, prodId }],
  expiringBatches: (days?: number) => ['batches', 'expiring', days],
  alerts: (severity?: string, ack?: boolean) => ['alerts', { severity, ack }],
  alertRules: ['alertRules'],
  transactions: (limit?: number) => ['transactions', limit],
  importJobs: ['importJobs'],
  posKeys: ['posKeys'],
  listings: (filters?: Record<string, unknown>) => ['listings', filters],
  claims: (status?: ClaimStatus) => ['claims', status],
  donors: ['donors'],
  ngos: ['ngos'],
  impact: ['impact'],
  notifications: ['notifications'],
  me: ['auth', 'me'],
  donationRequests: (filters?: Record<string, unknown>) => ['donationRequests', filters],
  donationRequest: (codeOrId: string | number) => ['donationRequest', codeOrId],
  surplusListings: (filters?: Record<string, unknown>) => ['surplusListings', filters],
  surplusListing: (id: number) => ['surplusListing', id],
  listingMatches: (id: number) => ['listingMatches', id],
  ngoRequirements: (filters?: Record<string, unknown>) => ['ngoRequirements', filters],
  ngoRequirement: (id: number) => ['ngoRequirement', id],
  requirementMatches: (id: number) => ['requirementMatches', id],
  pickupSchedule: (filters?: Record<string, unknown>) => ['pickupSchedule', filters],
  impactAnalytics: (period?: string) => ['impactAnalytics', period],
  marketplaceNotifications: (unreadOnly?: boolean) => ['marketplaceNotifications', unreadOnly],
  publicImpact: ['publicImpact'] as const,
  homePublic: ['home', 'public'] as const,
  homeAuth: ['home', 'auth'] as const,
  predictionsInsights: ['predictions', 'insights'] as const,
};

// --- Read Queries ---

export function useCurrentUser() {
  return useQuery({
    queryKey: QUERY_KEYS.me,
    queryFn: () => dataSource.getMe(),
    staleTime: 1000 * 60 * 5,
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => dataSource.logout(),
    onSuccess: () => {
      queryClient.clear();
    },
  });
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: QUERY_KEYS.dashboardSummary,
    queryFn: () => dataSource.getDashboardSummary(),
  });
}

export function useCategories() {
  return useQuery({
    queryKey: QUERY_KEYS.categories,
    queryFn: () => dataSource.getCategories(),
    staleTime: 1000 * 60 * 10,
  });
}

export function useStorageLocations() {
  return useQuery({
    queryKey: QUERY_KEYS.locations,
    queryFn: () => dataSource.getStorageLocations(),
    staleTime: 1000 * 60 * 10,
  });
}

export function useProducts(search?: string, categoryId?: number) {
  return useQuery({
    queryKey: QUERY_KEYS.products(search, categoryId),
    queryFn: () => dataSource.getProducts(search, categoryId),
  });
}

export function useBatches(status?: string, productId?: number) {
  return useQuery({
    queryKey: QUERY_KEYS.batches(status, productId),
    queryFn: () => dataSource.getBatches(status, productId),
  });
}

export function useExpiringBatches(days = 7) {
  return useQuery({
    queryKey: QUERY_KEYS.expiringBatches(days),
    queryFn: () => dataSource.getExpiringBatches(days),
  });
}

export function useAlerts(severity?: string, acknowledged?: boolean) {
  return useQuery({
    queryKey: QUERY_KEYS.alerts(severity, acknowledged),
    queryFn: () => dataSource.getAlerts(severity, acknowledged),
  });
}

export function useAlertRules() {
  return useQuery({
    queryKey: QUERY_KEYS.alertRules,
    queryFn: () => dataSource.getAlertRules(),
  });
}

export function useTransactions(limit = 50) {
  return useQuery({
    queryKey: QUERY_KEYS.transactions(limit),
    queryFn: () => dataSource.getTransactions(limit),
  });
}

export function useImportJobs() {
  return useQuery({
    queryKey: QUERY_KEYS.importJobs,
    queryFn: () => dataSource.getImportJobs(),
  });
}

export function useImportJob(
  jobId: number | null,
  options?: {
    refetchInterval?:
      | number
      | false
      | ((query: { state: { data: ImportJob | null | undefined } }) => number | false);
  }
) {
  return useQuery({
    queryKey: ['importJob', jobId],
    queryFn: () => (jobId ? dataSource.getImportJob(jobId) : null),
    enabled: !!jobId,
    refetchInterval: options?.refetchInterval,
  });
}

export function usePOSKeys() {
  return useQuery({
    queryKey: QUERY_KEYS.posKeys,
    queryFn: () => dataSource.getPOSKeys(),
  });
}

export function useDonationListings(filters?: { status?: string; category?: string }) {
  return useQuery({
    queryKey: QUERY_KEYS.listings(filters),
    queryFn: () => dataSource.getListings(filters),
  });
}

export function useDonationClaims(status?: ClaimStatus) {
  return useQuery({
    queryKey: QUERY_KEYS.claims(status),
    queryFn: () => dataSource.getClaims(status),
  });
}

export function useDonors() {
  return useQuery({
    queryKey: QUERY_KEYS.donors,
    queryFn: () => dataSource.getDonors(),
  });
}

export function useNGOs() {
  return useQuery({
    queryKey: QUERY_KEYS.ngos,
    queryFn: () => dataSource.getNGOs(),
  });
}

export function useImpactMetrics() {
  return useQuery({
    queryKey: QUERY_KEYS.impact,
    queryFn: () => dataSource.getImpactMetrics(),
  });
}

export function useNotifications() {
  return useQuery({
    queryKey: QUERY_KEYS.notifications,
    queryFn: () => dataSource.getNotifications(),
  });
}

// --- Mutations ---

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<Product, 'id' | 'organization'>) => dataSource.createProduct(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, partial }: { id: number; partial: Partial<Product> }) =>
      dataSource.updateProduct(id, partial),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
}

export function useCreateBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<Batch, 'id' | 'organization' | 'created_at'>) => dataSource.createBatch(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batches'] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dashboardSummary });
    },
  });
}

export function useDeductStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (req: DeductStockRequest) => dataSource.deductStock(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batches'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dashboardSummary });
    },
  });
}

export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => dataSource.acknowledgeAlert(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dashboardSummary });
    },
  });
}

export function useBulkAcknowledgeAlerts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: number[]) => dataSource.bulkAcknowledgeAlerts(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dashboardSummary });
    },
  });
}

export function useUploadCsv() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => dataSource.uploadCsvImport(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.importJobs });
      queryClient.invalidateQueries({ queryKey: ['batches'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
}

export function useCreatePOSKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (label: string) => dataSource.createPOSKey(label),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.posKeys });
    },
  });
}

export function useRotatePOSKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => dataSource.rotatePOSKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.posKeys });
    },
  });
}

export function useCreateListing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ batchId, windowHours }: { batchId: number; windowHours: number }) =>
      dataSource.createListing(batchId, windowHours),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      queryClient.invalidateQueries({ queryKey: ['batches'] });
    },
  });
}

export function useClaimListing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ listingId, eta, notes }: { listingId: number; eta: string; notes: string }) =>
      dataSource.claimListing(listingId, eta, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      queryClient.invalidateQueries({ queryKey: ['claims'] });
    },
  });
}

export function useUpdateClaimStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ claimId, status }: { claimId: number; status: ClaimStatus }) =>
      dataSource.updateClaimStatus(claimId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['claims'] });
      queryClient.invalidateQueries({ queryKey: ['listings'] });
    },
  });
}

export function useRateDonor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ claimId, rating, feedback }: { claimId: number; rating: number; feedback?: string }) =>
      dataSource.rateDonor(claimId, rating, feedback),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['claims'] });
    },
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => dataSource.markNotificationRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.notifications });
    },
  });
}

// --- Ratings Hooks ---

export function usePendingRatings() {
  return useQuery({
    queryKey: ['ratings', 'pending'],
    queryFn: () => dataSource.getPendingRatings(),
  });
}

export function useMyRatings(page = 1) {
  return useQuery({
    queryKey: ['ratings', 'mine', page],
    queryFn: () => dataSource.getMyRatings(page),
  });
}

export function useBusinessRatings(businessId: number) {
  return useQuery({
    queryKey: ['ratings', 'business', businessId],
    queryFn: () => dataSource.getBusinessRatings(businessId),
    enabled: !!businessId,
  });
}

export function useRateClaim() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ claimId, payload }: { claimId: number; payload: RatingCreatePayload }) =>
      dataSource.rateClaim(claimId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ratings'] });
      queryClient.invalidateQueries({ queryKey: ['claims'] });
    },
  });
}

export function useUpdateRating() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ratingId, payload }: { ratingId: number; payload: RatingUpdatePayload }) =>
      dataSource.updateRating(ratingId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ratings'] });
    },
  });
}

// --- Platform Admin Hooks ---

export function useAdminStats(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: () => dataSource.getAdminStats(),
    enabled: options?.enabled ?? true,
    refetchInterval: 1000 * 30, // refresh stats every 30s
  });
}


export function useAdminOrganizations(params?: {
  org_type?: string;
  is_verified?: boolean | string;
  verification_status?: string;
  search?: string;
  page?: number;
}) {
  return useQuery({
    queryKey: ['admin', 'organizations', params],
    queryFn: () => dataSource.getAdminOrganizations(params),
  });
}

export function useAdminOrganization(id: number) {
  return useQuery({
    queryKey: ['admin', 'organization', id],
    queryFn: () => dataSource.getAdminOrganization(id),
    enabled: !!id,
  });
}

export function useVerifyOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) =>
      dataSource.verifyOrganization(id, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'organizations'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'organization'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'auditLogs'] });
      queryClient.invalidateQueries({ queryKey: ['ngos'] });
      queryClient.invalidateQueries({ queryKey: ['donors'] });
    },
  });
}

export function useRejectOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      dataSource.rejectOrganization(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'organizations'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'organization'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'auditLogs'] });
    },
  });
}

export function useSuspendOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      dataSource.suspendOrganization(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'organizations'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'organization'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'auditLogs'] });
      queryClient.invalidateQueries({ queryKey: ['ngos'] });
      queryClient.invalidateQueries({ queryKey: ['donors'] });
    },
  });
}

export function useReinstateOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      dataSource.reinstateOrganization(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'organizations'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'organization'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'auditLogs'] });
      queryClient.invalidateQueries({ queryKey: ['ngos'] });
      queryClient.invalidateQueries({ queryKey: ['donors'] });
    },
  });
}

export function useAdminIssues(params?: {
  status?: string;
  category?: string;
  priority?: string;
  search?: string;
  page?: number;
}) {
  return useQuery({
    queryKey: ['admin', 'issues', params],
    queryFn: () => dataSource.getAdminIssues(params),
  });
}

export function useUpdateAdminIssue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<{
        status: IssueStatus;
        priority: IssuePriority;
        admin_notes: string;
        assigned_to: number | null;
      }>;
    }) => dataSource.updateAdminIssue(id, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'issues'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'auditLogs'] });
      queryClient.invalidateQueries({ queryKey: ['issues'] });
    },
  });
}

export function useAdminRatings(params?: {
  stars?: number;
  business?: number;
  ngo?: number;
  is_hidden?: boolean;
  search?: string;
  page?: number;
}) {
  return useQuery({
    queryKey: ['admin', 'ratings', params],
    queryFn: () => dataSource.getAdminRatings(params),
  });
}

export function useHideRating() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      dataSource.hideRating(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'ratings'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'auditLogs'] });
      queryClient.invalidateQueries({ queryKey: ['ratings'] });
    },
  });
}

export function useUnhideRating() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      dataSource.unhideRating(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'ratings'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'auditLogs'] });
      queryClient.invalidateQueries({ queryKey: ['ratings'] });
    },
  });
}

export function useAdminAuditLogs(params?: {
  action?: string;
  target_type?: string;
  search?: string;
  page?: number;
}) {
  return useQuery({
    queryKey: ['admin', 'auditLogs', params],
    queryFn: () => dataSource.getAdminAuditLogs(params),
  });
}

// --- Tenant Issue Reporting Hooks ---

export function useReportIssue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: IssueReportPayload) => dataSource.reportIssue(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['issues'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'issues'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
    },
  });
}

export function useMyIssues() {
  return useQuery({
    queryKey: ['issues', 'mine'],
    queryFn: () => dataSource.getMyIssues(),
  });
}

// --- Redistribution Hooks (Donation Requests, Surplus Marketplace, Requirements, Schedule, ESG) ---

export function useDonationRequests(filters?: { status?: string; search?: string }) {
  return useQuery({
    queryKey: QUERY_KEYS.donationRequests(filters),
    queryFn: () => dataSource.getDonationRequests(filters),
  });
}

export function useDonationRequest(codeOrId: string | number) {
  return useQuery({
    queryKey: QUERY_KEYS.donationRequest(codeOrId),
    queryFn: () => dataSource.getDonationRequest(codeOrId),
    enabled: Boolean(codeOrId),
  });
}

export function useCreateDonationRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      listing?: number;
      item_name?: string;
      requested_quantity: number | string;
      requested_pickup_time: string;
      pickup_notes?: string;
    }) => dataSource.createDonationRequest(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donationRequests'] });
      queryClient.invalidateQueries({ queryKey: ['surplusListings'] });
      queryClient.invalidateQueries({ queryKey: ['pickupSchedule'] });
      queryClient.invalidateQueries({ queryKey: ['marketplaceNotifications'] });
    },
  });
}

export function useApproveDonationRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ codeOrId, scheduledPickupTime }: { codeOrId: string | number; scheduledPickupTime?: string }) =>
      dataSource.approveDonationRequest(codeOrId, scheduledPickupTime),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donationRequests'] });
      queryClient.invalidateQueries({ queryKey: ['pickupSchedule'] });
      queryClient.invalidateQueries({ queryKey: ['surplusListings'] });
    },
  });
}

export function useConfirmScheduleDonationRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      codeOrId,
      scheduledPickupTime,
      notes,
    }: {
      codeOrId: string | number;
      scheduledPickupTime: string;
      notes?: string;
    }) => dataSource.confirmScheduleDonationRequest(codeOrId, scheduledPickupTime, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donationRequests'] });
      queryClient.invalidateQueries({ queryKey: ['pickupSchedule'] });
    },
  });
}

export function useRejectDonationRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ codeOrId, reason }: { codeOrId: string | number; reason: string }) =>
      dataSource.rejectDonationRequest(codeOrId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donationRequests'] });
      queryClient.invalidateQueries({ queryKey: ['surplusListings'] });
      queryClient.invalidateQueries({ queryKey: ['pickupSchedule'] });
    },
  });
}

export function useCancelDonationRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ codeOrId, reason }: { codeOrId: string | number; reason?: string }) =>
      dataSource.cancelDonationRequest(codeOrId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donationRequests'] });
      queryClient.invalidateQueries({ queryKey: ['surplusListings'] });
      queryClient.invalidateQueries({ queryKey: ['pickupSchedule'] });
    },
  });
}

export function useSetInTransitDonationRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      codeOrId,
      driver_name,
      driver_phone,
      vehicle_plate,
    }: {
      codeOrId: string | number;
      driver_name?: string;
      driver_phone?: string;
      vehicle_plate?: string;
    }) => dataSource.setInTransitDonationRequest(codeOrId, { driver_name, driver_phone, vehicle_plate }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donationRequests'] });
      queryClient.invalidateQueries({ queryKey: ['pickupSchedule'] });
    },
  });
}

export function useCollectDonationRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ codeOrId, notes }: { codeOrId: string | number; notes?: string }) =>
      dataSource.collectDonationRequest(codeOrId, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donationRequests'] });
      queryClient.invalidateQueries({ queryKey: ['pickupSchedule'] });
      queryClient.invalidateQueries({ queryKey: ['impactAnalytics'] });
    },
  });
}

export function useConfirmReceiptDonationRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ codeOrId, notes }: { codeOrId: string | number; notes?: string }) =>
      dataSource.confirmReceiptDonationRequest(codeOrId, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donationRequests'] });
      queryClient.invalidateQueries({ queryKey: ['pickupSchedule'] });
      queryClient.invalidateQueries({ queryKey: ['impactAnalytics'] });
    },
  });
}

export function useReportNoShowDonationRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ codeOrId, notes }: { codeOrId: string | number; notes?: string }) =>
      dataSource.reportNoShowDonationRequest(codeOrId, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donationRequests'] });
      queryClient.invalidateQueries({ queryKey: ['pickupSchedule'] });
    },
  });
}

// Surplus Listings Hooks
export function useSurplusListings(filters?: {
  status?: string;
  category?: string;
  search?: string;
  mine?: boolean;
  is_cooked?: boolean;
}) {
  return useQuery({
    queryKey: QUERY_KEYS.surplusListings(filters),
    queryFn: () => dataSource.getSurplusListings(filters),
  });
}

export function useSurplusListing(id: number) {
  return useQuery({
    queryKey: QUERY_KEYS.surplusListing(id),
    queryFn: () => dataSource.getSurplusListing(id),
    enabled: Boolean(id),
  });
}

export function useCreateSurplusListing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<SurplusListingItem>) => dataSource.createSurplusListing(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['surplusListings'] });
    },
  });
}

export function useUpdateSurplusListing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<SurplusListingItem> }) =>
      dataSource.updateSurplusListing(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['surplusListings'] });
    },
  });
}

export function useDeleteSurplusListing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => dataSource.deleteSurplusListing(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['surplusListings'] });
    },
  });
}

export function useListingMatches(listingId: number) {
  return useQuery({
    queryKey: QUERY_KEYS.listingMatches(listingId),
    queryFn: () => dataSource.getListingMatches(listingId),
    enabled: Boolean(listingId),
  });
}

export function useNotifyListingMatches() {
  return useMutation({
    mutationFn: ({ listingId, requirementIds }: { listingId: number; requirementIds?: number[] }) =>
      dataSource.notifyListingMatches(listingId, requirementIds),
  });
}

// NGO Requirements Hooks
export function useNGORequirements(filters?: { status?: string; search?: string }) {
  return useQuery({
    queryKey: QUERY_KEYS.ngoRequirements(filters),
    queryFn: () => dataSource.getNGORequirements(filters),
  });
}

export function useNGORequirement(id: number) {
  return useQuery({
    queryKey: QUERY_KEYS.ngoRequirement(id),
    queryFn: () => dataSource.getNGORequirement(id),
    enabled: Boolean(id),
  });
}

export function useCreateNGORequirement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<NGORequirementItem>) => dataSource.createNGORequirement(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ngoRequirements'] });
    },
  });
}

export function useUpdateNGORequirement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<NGORequirementItem> }) =>
      dataSource.updateNGORequirement(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ngoRequirements'] });
    },
  });
}

export function useDeleteNGORequirement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => dataSource.deleteNGORequirement(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ngoRequirements'] });
    },
  });
}

export function useRequirementMatches(requirementId: number) {
  return useQuery({
    queryKey: QUERY_KEYS.requirementMatches(requirementId),
    queryFn: () => dataSource.getRequirementMatches(requirementId),
    enabled: Boolean(requirementId),
  });
}

// Pickup Schedule Hook
export function usePickupSchedule(filters?: { date?: string; status?: string; range?: string }) {
  return useQuery({
    queryKey: QUERY_KEYS.pickupSchedule(filters),
    queryFn: () => dataSource.getPickupSchedule(filters),
  });
}

// Impact Analytics Hook
export function useImpactAnalytics(period?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.impactAnalytics(period),
    queryFn: () => dataSource.getImpactAnalytics(period),
  });
}

// Public Impact Hook (Cached 10 minutes, unauthenticated home/landing ticker)
export function usePublicImpact() {
  return useQuery({
    queryKey: QUERY_KEYS.publicImpact,
    queryFn: () => dataSource.getPublicImpactMetrics(),
    staleTime: 1000 * 60 * 10,
  });
}

// Marketplace Notifications Hooks
export function useMarketplaceNotifications(unreadOnly = false) {
  return useQuery({
    queryKey: QUERY_KEYS.marketplaceNotifications(unreadOnly),
    queryFn: () => dataSource.getMarketplaceNotifications(unreadOnly),
  });
}

export function useMarkMarketplaceNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => dataSource.markMarketplaceNotificationRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplaceNotifications'] });
    },
  });
}

export function useMarkAllMarketplaceNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => dataSource.markAllMarketplaceNotificationsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplaceNotifications'] });
    },
  });
}

// Home API Hooks (Task B1 & B2 & B3)
export function usePublicHomeTotals() {
  return useQuery({
    queryKey: QUERY_KEYS.homePublic,
    queryFn: () => dataSource.getPublicHomeTotals(),
    staleTime: 1000 * 60 * 10, // 10 minutes cache as per API
  });
}

export function useHomeData(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: QUERY_KEYS.homeAuth,
    queryFn: () => dataSource.getHomeData(),
    staleTime: 1000 * 60 * 1, // 1 minute
    enabled: options?.enabled,
  });
}

// AI Waste Prediction & Insights (Task 3)
export function usePlanPrediction() {
  return useMutation({
    mutationFn: (payload: PlanPredictionRequest) => dataSource.getPlanPrediction(payload),
  });
}

export function useDatasetInsights() {
  return useQuery({
    queryKey: QUERY_KEYS.predictionsInsights,
    queryFn: () => dataSource.getDatasetInsights(),
    staleTime: 1000 * 60 * 30, // 30 minutes cache
  });
}




