import React, { useState, useEffect, useCallback } from 'react';
import {
  Sparkles,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { MobileBottomNav } from './components/MobileBottomNav';
import { CommandPaletteModal } from './components/CommandPaletteModal';
import { OfflineBanner } from './components/OfflineBanner';
import { SessionExpiredDialog } from './components/SessionExpiredDialog';
import { DeviceSimulatorFrame, type DeviceMode } from './components/DeviceSimulatorFrame';
import { Sheet } from './components/ui/Sheet';
import { ConfirmDialog } from './components/ui/ConfirmDialog';
import { Button } from './components/ui/Button';
import { Skeleton } from './components/ui/Skeleton';

// Code-split / Lazy-loaded routes for optimal bundle performance
const PublicHomePage = React.lazy(() => import('./pages/PublicHomePage').then(m => ({ default: m.PublicHomePage })));
const AuthenticatedHomePage = React.lazy(() => import('./pages/AuthenticatedHomePage').then(m => ({ default: m.AuthenticatedHomePage })));
const LoginPage = React.lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })));
const RegisterPage = React.lazy(() => import('./pages/RegisterPage').then(m => ({ default: m.RegisterPage })));
const ForbiddenPage = React.lazy(() => import('./pages/ForbiddenPage').then(m => ({ default: m.ForbiddenPage })));
const NotFoundPage = React.lazy(() => import('./pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })));
const PendingVerificationPage = React.lazy(() => import('./pages/PendingVerificationPage').then(m => ({ default: m.PendingVerificationPage })));
const BusinessDashboardPage = React.lazy(() => import('./pages/business/BusinessDashboardPage').then(m => ({ default: m.BusinessDashboardPage })));
const BusinessInventoryPage = React.lazy(() => import('./pages/business/BusinessInventoryPage').then(m => ({ default: m.BusinessInventoryPage })));
const BusinessScanPage = React.lazy(() => import('./pages/business/BusinessScanPage').then(m => ({ default: m.BusinessScanPage })));
const BusinessAlertsPage = React.lazy(() => import('./pages/business/BusinessAlertsPage').then(m => ({ default: m.BusinessAlertsPage })));
const BusinessImportPage = React.lazy(() => import('./pages/business/BusinessImportPage').then(m => ({ default: m.BusinessImportPage })));
const BusinessSettingsPage = React.lazy(() => import('./pages/business/BusinessSettingsPage').then(m => ({ default: m.BusinessSettingsPage })));
const BusinessPOSSimulatorPage = React.lazy(() => import('./pages/business/BusinessPOSSimulatorPage').then(m => ({ default: m.BusinessPOSSimulatorPage })));
const BusinessPurchasePlannerPage = React.lazy(() => import('./pages/business/BusinessPurchasePlannerPage').then(m => ({ default: m.BusinessPurchasePlannerPage })));
const BusinessForecastPage = React.lazy(() => import('./pages/business/BusinessForecastPage').then(m => ({ default: m.BusinessForecastPage })));
const BusinessAiInsightsPage = React.lazy(() => import('./pages/business/BusinessAiInsightsPage').then(m => ({ default: m.BusinessAiInsightsPage })));
const DonationRequestsPage = React.lazy(() => import('./pages/DonationRequestsPage').then(m => ({ default: m.DonationRequestsPage })));
const SurplusMarketplacePage = React.lazy(() => import('./pages/SurplusMarketplacePage').then(m => ({ default: m.SurplusMarketplacePage })));
const NgoRequirementsPage = React.lazy(() => import('./pages/NgoRequirementsPage').then(m => ({ default: m.NgoRequirementsPage })));
const PickupSchedulePage = React.lazy(() => import('./pages/PickupSchedulePage').then(m => ({ default: m.PickupSchedulePage })));
const ImpactAnalyticsPage = React.lazy(() => import('./pages/ImpactAnalyticsPage').then(m => ({ default: m.ImpactAnalyticsPage })));
const NotificationsPage = React.lazy(() => import('./pages/NotificationsPage').then(m => ({ default: m.NotificationsPage })));
const NgoDashboardPage = React.lazy(() => import('./pages/ngo/NgoDashboardPage').then(m => ({ default: m.NgoDashboardPage })));
const NgoFoodFeedPage = React.lazy(() => import('./pages/ngo/NgoFoodFeedPage').then(m => ({ default: m.NgoFoodFeedPage })));
const NgoClaimsPage = React.lazy(() => import('./pages/ngo/NgoClaimsPage').then(m => ({ default: m.NgoClaimsPage })));
const NgoSettingsPage = React.lazy(() => import('./pages/ngo/NgoSettingsPage').then(m => ({ default: m.NgoSettingsPage })));
const NgoProfilePage = React.lazy(() => import('./pages/ngo/NgoProfilePage').then(m => ({ default: m.NgoProfilePage })));
const AdminOverviewPage = React.lazy(() => import('./pages/admin/AdminOverviewPage').then(m => ({ default: m.AdminOverviewPage })));
const AdminVerificationsPage = React.lazy(() => import('./pages/admin/AdminVerificationsPage').then(m => ({ default: m.AdminVerificationsPage })));
const AdminOrganizationsPage = React.lazy(() => import('./pages/admin/AdminOrganizationsPage').then(m => ({ default: m.AdminOrganizationsPage })));
const AdminIssuesPage = React.lazy(() => import('./pages/admin/AdminIssuesPage').then(m => ({ default: m.AdminIssuesPage })));
const AdminRatingsPage = React.lazy(() => import('./pages/admin/AdminRatingsPage').then(m => ({ default: m.AdminRatingsPage })));
const AdminAuditLogPage = React.lazy(() => import('./pages/admin/AdminAuditLogPage').then(m => ({ default: m.AdminAuditLogPage })));
const AdminSettingsPage = React.lazy(() => import('./pages/admin/AdminSettingsPage').then(m => ({ default: m.AdminSettingsPage })));

const PageLoadingFallback: React.FC = () => (
  <div className="w-full space-y-4 py-8 animate-in fade-in duration-200">
    <div className="h-8 w-48 rounded-[8px] bg-[var(--surface-2)] animate-pulse" />
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <Skeleton variant="statCard" />
      <Skeleton variant="statCard" />
      <Skeleton variant="statCard" />
      <Skeleton variant="statCard" />
    </div>
    <div className="h-64 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 animate-pulse" />
  </div>
);
import { demoSource } from './services/demoSource';
import { defaultMode, setDataSourceMode } from './services';
import { isAuthenticated, subscribeAuth } from './services/auth';
import {
  useCurrentUser,
  useAlerts,
  useNotifications,
  useMarkNotificationRead,
  useLogout,
  useAdminStats,
  QUERY_KEYS,
} from './hooks/useData';

import {
  simulationEngine,
  type SimulationEvent,
} from './simulation/simulationEngine';

export const App: React.FC = () => {
  const queryClient = useQueryClient();

  // Re-render when auth session changes (login / logout)
  const [, setAuthTick] = useState<number>(0);
  useEffect(() => {
    return subscribeAuth(() => {
      setAuthTick((t) => t + 1);
    });
  }, []);

  // Navigation & Shell State: Direct URL open without hash defaults to landing page for logged-out visitors
  const [rawPath, setRawPath] = useState<string>(() => {
    const hash = window.location.hash.replace('#', '').trim();
    if (hash) {
      if (hash === 'ngo/profile' || hash === '/ngo/profile') return 'profile';
      if (hash === '/' || hash === '') return '';
      return hash;
    }
    const pathname = window.location.pathname.replace(/^\//, '').trim();
    if (pathname === 'ngo/profile' || pathname === 'profile') return 'profile';
    if (pathname === '/' || pathname === '') return '';
    const params = new URLSearchParams(window.location.search);
    const page = params.get('page');
    if (page) {
      if (page === 'ngo/profile' || page === '/ngo/profile') return 'profile';
      return page;
    }
    return '';
  });

  const setActivePath = useCallback((path: string) => {
    const target = path === 'ngo/profile' || path === '/ngo/profile' ? 'profile' : path;
    setRawPath(target);
    window.location.hash = path;
  }, []);

  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace('#', '').trim();
      if (hash === 'ngo/profile' || hash === '/ngo/profile') {
        setRawPath('profile');
      } else {
        setRawPath(hash || '');
      }
    };
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isSessionExpiredOpen, setIsSessionExpiredOpen] = useState(false);
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);

  // App Appearance & Mode State
  const [dataMode, setDataMode] = useState<'live' | 'demo'>(() => {
    const stored = typeof window !== 'undefined' ? localStorage.getItem('surplussync_data_mode') : null;
    if (stored === 'live' || stored === 'demo') return stored;
    return defaultMode;
  });
  const isDemo = dataMode === 'demo';

  useEffect(() => {
    const handleModeChange = () => {
      const stored = localStorage.getItem('surplussync_data_mode');
      if (stored === 'live' || stored === 'demo') {
        setDataMode(stored);
      }
    };
    window.addEventListener('surplussync_mode_change', handleModeChange);
    window.addEventListener('storage', handleModeChange);
    return () => {
      window.removeEventListener('surplussync_mode_change', handleModeChange);
      window.removeEventListener('storage', handleModeChange);
    };
  }, []);

  // Simulation engine lifecycle: stopped by default, manual actions on demand
  useEffect(() => {
    simulationEngine.stop();
    return () => {
      simulationEngine.stop();
    };
  }, [isDemo]);

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [deviceMode, setDeviceMode] = useState<DeviceMode>('fluid');
  const [, setReconcile] = useState(() => simulationEngine.reconcileStock());
  const [, setVirtualTimeStr] = useState<string>('');

  const [isDark, setIsDark] = useState<boolean>(() => {
    const saved = localStorage.getItem('surplussync_theme');
    return saved ? saved === 'dark' : true;
  });

  // Queries: In live mode, user profile and role come strictly from GET /accounts/me/
  const { data: currentUser, refetch: refetchUser, isLoading: isUserLoading, isError: isUserError } = useCurrentUser();
  const { data: alerts } = useAlerts();
  const { data: notifications } = useNotifications();
  const markNotifReadMutation = useMarkNotificationRead();
  const logoutMutation = useLogout();

  // Sync demo persona from URL query param or route
  useEffect(() => {
    if (!isDemo) return;
    const params = new URLSearchParams(window.location.search);
    const personaParam = params.get('persona')?.toUpperCase();
    if (
      personaParam === 'NGO' ||
      personaParam === 'NGO_UNVERIFIED' ||
      personaParam === 'BUSINESS' ||
      personaParam === 'ADMIN'
    ) {
      const user = demoSource.setDemoUser(
        personaParam as 'BUSINESS' | 'NGO' | 'NGO_UNVERIFIED' | 'ADMIN'
      );
      queryClient.setQueryData(QUERY_KEYS.me, { ...user });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.me });
      refetchUser();
    } else if (rawPath.startsWith('admin')) {
      const savedPersona = localStorage.getItem('surplussync_demo_persona');
      if (savedPersona !== 'ADMIN') {
        const user = demoSource.setDemoUser('ADMIN');
        queryClient.setQueryData(QUERY_KEYS.me, { ...user });
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.me });
        refetchUser();
      }
    } else if (rawPath === 'feed' || rawPath === 'claims') {
      const savedPersona = localStorage.getItem('surplussync_demo_persona');
      if (!savedPersona || savedPersona === 'BUSINESS') {
        const user = demoSource.setDemoUser('NGO');
        queryClient.setQueryData(QUERY_KEYS.me, { ...user });
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.me });
        refetchUser();
      }
    }
  }, [isDemo, rawPath, queryClient, refetchUser]);

  // Route Authentication Derivation:
  // - Default root route '' or '/' or 'public' or 'landing' or 'public-home' -> 'public-home' (shows starting overview page)
  // - In live mode, unauthenticated access to other paths -> 'login' (or 'register')
  // - 'home' -> AuthenticatedHomePage cockpit
  // - all other paths -> rawPath
  const isLiveUnauthenticated = !isDemo && (!isAuthenticated() || isUserError);
  let activePath: string;
  if (
    rawPath === '' ||
    rawPath === '/' ||
    rawPath === 'public' ||
    rawPath === 'landing' ||
    rawPath === 'public-home'
  ) {
    activePath = 'public-home';
  } else if (rawPath === 'register') {
    activePath = 'register';
  } else if (rawPath === 'login') {
    activePath = isLiveUnauthenticated ? 'login' : 'home';
  } else if (isLiveUnauthenticated) {
    activePath = 'login';
  } else {
    activePath = rawPath;
  }

  const isPlatformAdmin = Boolean(currentUser?.is_platform_admin);
  const { data: adminStats } = useAdminStats({ enabled: isPlatformAdmin });

  const orgType = currentUser?.organization?.type || (isDemo ? 'BUSINESS' : 'BUSINESS');
  const orgName = currentUser?.organization?.name || (isDemo ? (isPlatformAdmin ? 'Platform Administration' : 'SurplusSync Partner Kitchen') : '');
  const isVerified = currentUser?.organization?.is_verified ?? (isDemo ? true : false);
  const userName = currentUser?.username || (isDemo ? (isPlatformAdmin ? 'Platform Admin' : 'Demo Admin') : '');


  const triggerToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((current) => (current === msg ? null : current));
    }, 4000);
  }, []);

  const refreshQueries = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.homeAuth });
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dashboardSummary });
    queryClient.invalidateQueries({ queryKey: ['batches'] });
    queryClient.invalidateQueries({ queryKey: ['products'] });
    queryClient.invalidateQueries({ queryKey: ['transactions'] });
    queryClient.invalidateQueries({ queryKey: ['listings'] });
    queryClient.invalidateQueries({ queryKey: ['alerts'] });
    queryClient.invalidateQueries({ queryKey: ['impact'] });
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.notifications });
    setReconcile(simulationEngine.reconcileStock());
  }, [queryClient]);

  const handleToggleDataMode = useCallback(() => {
    const nextMode = isDemo ? 'live' : 'demo';
    setDataSourceMode(nextMode);
    setDataMode(nextMode);
    queryClient.clear();
    triggerToast(
      nextMode === 'live'
        ? 'Switched to Live Backend Mode (Django DB on http://127.0.0.1:8000)'
        : 'Switched to Demo Sandbox Mode'
    );
    refreshQueries();
  }, [isDemo, triggerToast, refreshQueries, queryClient]);

  // Global Ctrl+K / Cmd+K Command Palette Listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Sync theme changes
  useEffect(() => {
    const handleStorage = () => {
      const saved = localStorage.getItem('surplussync_theme');
      setIsDark(saved === 'dark');
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  // Listen to simulation engine ticks and events (Demo mode only)
  useEffect(() => {
    if (!isDemo) return;

    const unsubscribe = simulationEngine.subscribe((event: SimulationEvent) => {
      setVirtualTimeStr(simulationEngine.getVirtualTime().toLocaleTimeString());

      if (
        event.type === 'POS_SALE' ||
        event.type === 'NEW_LISTING' ||
        event.type === 'CLOCK_FAST_FORWARD' ||
        event.type === 'BATCH_ADDED'
      ) {
        refreshQueries();
        triggerToast(event.message);
      }
    });

    return () => {
      unsubscribe();
    };
  }, [isDemo, refreshQueries, triggerToast]);

  const toggleDarkMode = () => {
    const next = !isDark;
    setIsDark(next);
    if (next) {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
      localStorage.setItem('surplussync_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
      localStorage.setItem('surplussync_theme', 'light');
    }
  };

  const handleSwitchPersona = (persona: 'BUSINESS' | 'NGO' | 'NGO_UNVERIFIED' | 'ADMIN') => {
    const user = demoSource.setDemoUser(persona);
    queryClient.setQueryData(QUERY_KEYS.me, { ...user });
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.me });
    refetchUser();
    if (persona === 'NGO') {
      setActivePath('dashboard');
      triggerToast('Switched to NGO Partner Persona (Relief Foundation)');
    } else if (persona === 'NGO_UNVERIFIED') {
      setActivePath('dashboard');
      triggerToast('Switched to Unverified NGO Persona (Robin Hood Army Mysore)');
    } else if (persona === 'ADMIN') {
      setActivePath('admin/overview');
      triggerToast('Switched to Platform Administrator Persona (Full Superuser Access)');
    } else {
      setActivePath('dashboard');
      triggerToast('Switched to Business Persona (Partner Kitchen)');
    }
  };


  const handleLogout = () => {
    logoutMutation.mutate(undefined, {
      onSuccess: () => {
        triggerToast('Signed out of session');
        setActivePath('');
      },
      onError: () => {
        setActivePath('');
      },
    });
  };

  // Standalone Public Home Landing Page
  if (activePath === 'public-home') {
    return (
      <React.Suspense fallback={<PageLoadingFallback />}>
        <PublicHomePage
          onNavigateToLogin={() => setActivePath('login')}
          onNavigateToRegister={(role) => setActivePath(role ? `register?role=${role}` : 'register')}
          isDark={isDark}
          onToggleDark={toggleDarkMode}
          isDemo={isDemo}
        />
      </React.Suspense>
    );
  }

  // Auth Standalone Pages
  if (activePath === 'login') {
    return (
      <React.Suspense fallback={<PageLoadingFallback />}>
        <LoginPage
          onLoginSuccess={(loggedInUser) => {
            refetchUser();
            const userObj = loggedInUser as { is_platform_admin?: boolean } | undefined;
            if (userObj?.is_platform_admin) {
              setActivePath('admin/overview');
            } else {
              setActivePath('home');
            }
          }}
          onNavigateToRegister={() => setActivePath('register')}
          onBackToPlatform={() => setActivePath(isLiveUnauthenticated ? '' : 'home')}
          onNavigate={(path) => {
            if (path === 'register') setActivePath('register');
            else setActivePath(isLiveUnauthenticated ? '' : 'home');
          }}
          isDark={isDark}
          onToggleDark={toggleDarkMode}
        />
      </React.Suspense>
    );
  }

  if (activePath === 'register') {
    return (
      <React.Suspense fallback={<PageLoadingFallback />}>
        <RegisterPage
          onRegisterSuccess={() => {
            refetchUser();
            setActivePath('home');
          }}
          onNavigateToLogin={() => setActivePath('login')}
          onBackToPlatform={() => setActivePath(isLiveUnauthenticated ? '' : 'home')}
          onNavigate={(path) => {
            if (path === 'login') setActivePath('login');
            else setActivePath(isLiveUnauthenticated ? '' : 'home');
          }}
          isDark={isDark}
          onToggleDark={toggleDarkMode}
        />
      </React.Suspense>
    );
  }

  // Route Titles



  // Route Titles
  const pageTitles: Record<string, string> = {
    home: 'Home',
    dashboard: 'Dashboard',
    marketplace: 'Surplus Food Marketplace',
    'surplus-marketplace': 'Surplus Food Marketplace',
    requirements: 'NGO Food Requirements',
    'ngo/requirements': 'NGO Food Requirements',
    'ngo-requirements': 'NGO Food Requirements',
    donations: 'Donation Requests & Rescues',
    'donation-requests': 'Donation Requests & Rescues',
    schedule: 'Pickup & Logistics Schedule',
    'pickup-schedule': 'Pickup & Logistics Schedule',
    impact: 'Environmental & Social Impact (ESG)',
    notifications: 'Notifications & Alerts Center',
    inventory: 'Inventory & Batches',
    scan: 'Barcode Scanner',
    alerts: 'Stock & Spoilage Alerts',
    import: 'CSV Import Manifest',
    feed: 'Live Surplus Food Feed',
    claims: 'My Food Rescue Claims',
    settings: 'Organization Settings',
    profile: 'NGO Profile & Donor Ratings',
    'ngo/profile': 'NGO Profile & Donor Ratings',
    'admin/overview': 'Platform Overview',
    'admin/verifications': 'NGO Verification Queue',
    'admin/organizations': 'Organizations Directory',
    'admin/issues': 'Incident & Dispute Management',
    'admin/ratings': 'Ratings & Reviews Moderation',
    'admin/audit-logs': 'Administrative Audit Log',
    'admin/settings': 'Platform Settings',
    'business/pos-simulator': 'POS Cash Register Simulator',
    'pos-simulator': 'POS Cash Register Simulator',
    'business/ai/planner': 'Purchase Planner (AI)',
    'ai/planner': 'Purchase Planner (AI)',
    planner: 'Purchase Planner (AI)',
    'business/ai/forecast': 'Sales & Demand Forecast (AI)',
    'ai/forecast': 'Sales & Demand Forecast (AI)',
    forecast: 'Sales & Demand Forecast (AI)',
    'business/ai/insights': 'Benchmark Waste Insights',
    'ai/insights': 'Benchmark Waste Insights',
    insights: 'Benchmark Waste Insights',
  };

  // Business Only Routes Guard
  const isBusinessOnlyRoute = [
    'inventory',
    'scan',
    'import',
    'business/pos-simulator',
    'pos-simulator',
    'business/ai/planner',
    'ai/planner',
    'planner',
    'business/ai/forecast',
    'ai/forecast',
    'forecast',
    'business/ai/insights',
    'ai/insights',
    'insights',
  ].includes(activePath);

  // Render Shell Content with Route Guards
  const renderContent = () => {
    // In live mode, display loading skeleton while fetching initial user role from GET /accounts/me/
    if (!isDemo && isUserLoading && !currentUser) {
      return <PageLoadingFallback />;
    }

    const isAdminRoute = activePath.startsWith('admin');

    // Platform Admin Route Guard: Non-admin users visiting /admin/* get 403 ForbiddenPage
    if (isAdminRoute && !isPlatformAdmin) {
      return (
        <ForbiddenPage
          onGoHome={() => setActivePath('dashboard')}
          requiredRole="Platform Administrators"
        />
      );
    }

    // Platform Admin Routes
    if (isPlatformAdmin) {
      if (
        activePath === 'dashboard' ||
        activePath === 'overview' ||
        activePath === 'admin/overview' ||
        activePath === 'admin'
      ) {
        return <AdminOverviewPage onNavigate={setActivePath} onTriggerToast={triggerToast} />;
      }
      if (activePath === 'admin/verifications') {
        return <AdminVerificationsPage onTriggerToast={triggerToast} />;
      }
      if (activePath === 'admin/organizations') {
        return <AdminOrganizationsPage onTriggerToast={triggerToast} />;
      }
      if (activePath === 'admin/issues') {
        return <AdminIssuesPage onTriggerToast={triggerToast} />;
      }
      if (activePath === 'admin/ratings') {
        return <AdminRatingsPage onTriggerToast={triggerToast} />;
      }
      if (activePath === 'admin/audit-logs' || activePath === 'admin/audit') {
        return <AdminAuditLogPage />;
      }
      if (activePath === 'admin/settings' || activePath === 'settings') {
        return <AdminSettingsPage onTriggerToast={triggerToast} />;
      }
    }


    // 1. Pending Verification Screen for Unverified NGOs (Home, Profile, Settings are accessible)
    if (
      orgType === 'NGO' &&
      !isVerified &&
      activePath !== 'home' &&
      activePath !== 'profile' &&
      activePath !== 'ngo/profile' &&
      activePath !== 'settings'
    ) {
      return (
        <PendingVerificationPage
          organizationName={orgName}
          onLogout={handleLogout}
          onSwitchToBusinessDemo={isDemo ? () => handleSwitchPersona('BUSINESS') : undefined}
        />
      );
    }

    // 2. Role Guard: 403 Forbidden Page
    if (orgType === 'NGO' && isBusinessOnlyRoute) {
      return (
        <ForbiddenPage
          onGoHome={() => setActivePath('dashboard')}
          requiredRole="Business Organizations"
        />
      );
    }

    // 3. Route: Home
    if (activePath === 'home') {
      return (
        <AuthenticatedHomePage
          onNavigate={(path: string) => setActivePath(path)}
          onOpenAddBatch={() => setIsSheetOpen(true)}
          onTriggerToast={triggerToast}
        />
      );
    }

    // 4. Route: Dashboard
    if (activePath === 'dashboard') {
      if (orgType === 'NGO') {
        return (
          <NgoDashboardPage
            onTriggerToast={triggerToast}
            onNavigate={(path: string) => setActivePath(path)}
          />
        );
      }
      return (
        <BusinessDashboardPage
          onNavigate={(path: string) => setActivePath(path)}
          onOpenAddBatch={() => setIsSheetOpen(true)}
          onOpenCreateListing={() => setActivePath('donations')}
          onTriggerToast={triggerToast}
        />
      );
    }

    // 4. Route: Inventory
    if (activePath === 'inventory') {
      return (
        <BusinessInventoryPage
          onTriggerToast={triggerToast}
          onOpenCreateListing={() => setActivePath('donations')}
        />
      );
    }

    // 5. Route: Barcode Scan
    if (activePath === 'scan') {
      return (
        <BusinessScanPage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 6. Route: Stock & Spoilage Alerts
    if (activePath === 'alerts') {
      return (
        <BusinessAlertsPage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 7. Route: CSV Manifest Ingestion
    if (activePath === 'import') {
      return (
        <BusinessImportPage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 8. Route: Surplus Marketplace
    if (activePath === 'marketplace' || activePath === 'surplus-marketplace') {
      return (
        <SurplusMarketplacePage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 9. Route: Donation Requests & Lifecycle Management
    if (activePath === 'donations' || activePath === 'donation-requests') {
      return (
        <DonationRequestsPage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 10. Route: NGO Food Requirements
    if (
      activePath === 'requirements' ||
      activePath === 'ngo/requirements' ||
      activePath === 'ngo-requirements'
    ) {
      return (
        <NgoRequirementsPage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 11. Route: Pickup & Logistics Schedule
    if (activePath === 'schedule' || activePath === 'pickup-schedule') {
      return (
        <PickupSchedulePage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 12. Route: Environmental & Social Impact (ESG)
    if (activePath === 'impact') {
      return (
        <ImpactAnalyticsPage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 14. Route: Notifications Center
    if (activePath === 'notifications') {
      return (
        <NotificationsPage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 10. Route: Settings
    if (activePath === 'settings') {
      if (orgType === 'NGO') {
        return (
          <NgoSettingsPage
            onTriggerToast={triggerToast}
            isDark={isDark}
            onToggleTheme={toggleDarkMode}
          />
        );
      }
      return (
        <BusinessSettingsPage
          onTriggerToast={triggerToast}
          isDark={isDark}
          onToggleTheme={toggleDarkMode}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // Route: POS Cash Register Simulator (Developer Tools)
    if (activePath === 'business/pos-simulator' || activePath === 'pos-simulator') {
      return (
        <BusinessPOSSimulatorPage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // Route: AI Purchase Planner (Business)
    if (activePath === 'business/ai/planner' || activePath === 'ai/planner' || activePath === 'planner') {
      return (
        <BusinessPurchasePlannerPage
          onNavigate={(path: string) => setActivePath(path)}
          onTriggerToast={triggerToast}
        />
      );
    }

    // Route: AI Sales & Demand Forecast (Business)
    if (activePath === 'business/ai/forecast' || activePath === 'ai/forecast' || activePath === 'forecast') {
      return (
        <BusinessForecastPage
          onNavigate={(path: string) => setActivePath(path)}
          onTriggerToast={triggerToast}
        />
      );
    }

    // Route: AI Benchmark Waste Insights (Business)
    if (activePath === 'business/ai/insights' || activePath === 'ai/insights' || activePath === 'insights') {
      return <BusinessAiInsightsPage />;
    }

    // 11. Route: Food Feed (NGO)
    if (activePath === 'feed') {
      return (
        <NgoFoodFeedPage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 12. Route: My Claims (NGO)
    if (activePath === 'claims') {
      return (
        <NgoClaimsPage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 13. Route: Profile & Ratings (NGO)
    if (activePath === 'profile' || activePath === 'ngo/profile') {
      if (orgType !== 'NGO') {
        return (
          <div
            id="ngo-profile-forbidden"
            className="rounded-[12px] border border-[var(--color-danger-border)] bg-[var(--color-danger-subtle)] p-8 text-center space-y-4 max-w-lg mx-auto my-12"
          >
            <div className="space-y-1.5">
              <h2 className="text-lg font-bold text-[var(--text)]">Access Restricted</h2>
              <p className="text-xs text-[var(--muted)]">
                The NGO profile and rating management console is exclusively accessible to registered NGO relief partners.
              </p>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setActivePath('dashboard')}
              className="text-xs"
            >
              Return to Dashboard
            </Button>
          </div>
        );
      }
      return (
        <NgoProfilePage
          onTriggerToast={triggerToast}
          onNavigate={(path: string) => setActivePath(path)}
        />
      );
    }

    // 8. 404 Not Found Page Fallback
    return <NotFoundPage onGoHome={() => setActivePath('dashboard')} />;
  };

  return (
    <DeviceSimulatorFrame mode={deviceMode} onModeChange={setDeviceMode}>
      <div className="min-h-screen bg-[var(--bg)] text-[var(--text)] selection:bg-[var(--primary)] selection:text-[var(--primary-foreground)] transition-colors duration-200">
        {/* Offline Status Banner */}
        <OfflineBanner />

        {/* Floating Toast Notification */}
        {toastMessage && (
          <div
            role="status"
            aria-live="polite"
            className="fixed top-20 right-4 sm:right-8 z-50 flex items-center gap-2.5 rounded-[8px] border border-[var(--primary)]/30 bg-[var(--surface)] px-4 py-3 text-xs font-semibold text-[var(--text)] shadow-2xl animate-in fade-in slide-in-from-top-3 max-w-md"
          >
            <Sparkles className="h-4 w-4 text-[var(--primary)] shrink-0 animate-spin" />
            <span className="truncate">{toastMessage}</span>
          </div>
        )}

        {/* Top Header Bar */}
        <Header
          onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
          pageTitle={pageTitles[activePath] || 'Overview'}
          onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
          isSidebarCollapsed={isSidebarCollapsed}
          orgType={orgType}
          orgName={orgName}
          userName={userName}
          isVerified={isVerified}
          isDemoMode={isDemo}
          isPlatformAdmin={isPlatformAdmin}
          notifications={notifications || []}
          onMarkNotificationRead={(id) => markNotifReadMutation.mutate(id)}
          onLogout={handleLogout}
          onSwitchPersona={isDemo ? handleSwitchPersona : undefined}
          onNavigate={setActivePath}
          onToggleDataMode={handleToggleDataMode}
        />

        {/* Collapsible Sidebar */}
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          activePath={activePath}
          onNavigate={(path) => setActivePath(path)}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
          orgType={orgType}
          orgName={orgName}
          alertCount={
            alerts
              ? alerts.filter((a) => {
                  if (a.is_acknowledged) return false;
                  if (a.batch_status === 'EXPIRED') return false;
                  const todayStr = new Date().toISOString().split('T')[0];
                  if (a.expiry_date && a.expiry_date < todayStr) return false;
                  if (a.message && /\b(has expired|is expired|expired on)\b/i.test(a.message)) return false;
                  return true;
                }).length
              : 0
          }
          isPlatformAdmin={isPlatformAdmin}
          pendingVerificationCount={adminStats?.pending_verifications ?? adminStats?.pending_ngo_verifications ?? 0}
          openIssuesCount={adminStats?.open_issues ?? 0}
        />

        {/* Main Content Area */}
        <main
          className={`transition-all duration-200 pt-20 pb-24 lg:pb-8 px-4 sm:px-6 lg:px-8 max-w-[1280px] mx-auto ${isSidebarCollapsed ? 'lg:pl-[96px]' : 'lg:pl-[264px]'
            }`}
        >
          <React.Suspense fallback={<PageLoadingFallback />}>
            {renderContent()}
          </React.Suspense>
        </main>

        {/* Mobile Bottom Navigation (< 1024px) */}
        <MobileBottomNav
          activePath={activePath}
          onNavigate={(path) => setActivePath(path)}
          orgType={orgType}
          alertCount={
            alerts
              ? alerts.filter((a) => {
                  if (a.is_acknowledged) return false;
                  if (a.batch_status === 'EXPIRED') return false;
                  const todayStr = new Date().toISOString().split('T')[0];
                  if (a.expiry_date && a.expiry_date < todayStr) return false;
                  if (a.message && /\b(has expired|is expired|expired on)\b/i.test(a.message)) return false;
                  return true;
                }).length
              : 0
          }
          isPlatformAdmin={isPlatformAdmin}
          onLogout={handleLogout}
        />

        {/* Command Palette Search Dialog (Ctrl+K) */}
        <CommandPaletteModal
          isOpen={isCommandPaletteOpen}
          onClose={() => setIsCommandPaletteOpen(false)}
          onNavigate={(path) => setActivePath(path)}
          orgType={orgType}
          isPlatformAdmin={isPlatformAdmin}
          isDark={isDark}
          onToggleTheme={toggleDarkMode}
          onLogout={handleLogout}
          onSimulatePOS={

            isDemo
              ? () => {
                  const res = simulationEngine.executeRandomPOSSale();
                  triggerToast(res.message);
                  refreshQueries();
                }
              : undefined
          }
        />

        {/* Session Expired Dialog */}
        <SessionExpiredDialog
          isOpen={isSessionExpiredOpen}
          onLogin={() => {
            setIsSessionExpiredOpen(false);
            setActivePath('login');
          }}
        />

        {/* Sheet-based Form Drawer (Example: Add Batch Form) */}
        <Sheet
          isOpen={isSheetOpen}
          onClose={() => setIsSheetOpen(false)}
          title="Add Inward Batch"
          description="Register a newly received stock batch into FEFO rotation"
          footer={
            <>
              <Button variant="outline" size="sm" onClick={() => setIsSheetOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  simulationEngine.addExpiringBatch(48, 25);
                  setIsSheetOpen(false);
                  triggerToast('Added 25 units of inward batch to FEFO rotation');
                  refreshQueries();
                }}
              >
                Save Batch
              </Button>
            </>
          }
        >
          <div className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold text-[var(--text)] mb-1">Product</label>
              <select className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2 text-[var(--text)]">
                <option>Nandini Toned Fresh Milk 500ml</option>
                <option>Amul Taaza Homogenised Toned Milk 1L</option>
                <option>Milky Mist Paneer Fresh 200g</option>
                <option>Fresh Robusta Bananas Bunch</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">Batch Number</label>
                <input
                  type="text"
                  defaultValue="BTH-202610-482"
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2 font-mono text-[var(--text)]"
                />
              </div>
              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">Initial Quantity</label>
                <input
                  type="number"
                  defaultValue="25"
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2 text-[var(--text)]"
                />
              </div>
            </div>
            <div>
              <label className="block font-semibold text-[var(--text)] mb-1">Expiry Date</label>
              <input
                type="date"
                defaultValue="2026-10-18"
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2 text-[var(--text)]"
              />
            </div>
          </div>
        </Sheet>

        {/* Accessible ConfirmDialog (e.g. Acknowledge Alert or Sign Out) */}
        <ConfirmDialog
          isOpen={isConfirmOpen}
          title="Acknowledge All Warnings"
          description="Are you sure you want to acknowledge all active spoilage horizon warnings? This confirms your staff has reviewed the critical batches."
          confirmLabel="Acknowledge All"
          variant="warning"
          onConfirm={() => {
            setIsConfirmOpen(false);
            triggerToast('Acknowledged all active warnings');
          }}
          onCancel={() => setIsConfirmOpen(false)}
        />
      </div>
    </DeviceSimulatorFrame>
  );
};

export default App;