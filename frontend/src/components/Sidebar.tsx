import React from 'react';
import {
  Home,
  LayoutDashboard,
  Package,
  ScanLine,
  BellRing,
  UploadCloud,
  HeartHandshake,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  Repeat,
  X,
  Building2,
  Users,
  Star,
  ShieldCheck,
  AlertTriangle,
  ScrollText,
  Shield,
  Terminal,
  Store,
  Truck,
  ClipboardList,
  Bell,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { cn } from '../lib/utils';
import type { OrganizationType } from '../types';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  activePath: string;
  onNavigate: (path: string) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  orgType?: OrganizationType;
  orgName?: string;
  alertCount?: number;
  isPlatformAdmin?: boolean;
  pendingVerificationCount?: number;
  openIssuesCount?: number;
  aiPredictionAvailable?: boolean;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ElementType;
  badge?: number;
  section?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  activePath,
  onNavigate,
  isCollapsed = false,
  onToggleCollapse,
  orgType = 'BUSINESS',
  orgName = 'The Grand Gateway Bengaluru',
  alertCount = 0,
  isPlatformAdmin = false,
  pendingVerificationCount = 0,
  openIssuesCount = 0,
  aiPredictionAvailable = true,
}) => {
  // Listen to developer tools toggle
  const [devToolsEnabled, setDevToolsEnabled] = React.useState<boolean>(() => {
    return typeof window !== 'undefined' && localStorage.getItem('surplussync_dev_tools') === 'true';
  });

  React.useEffect(() => {
    const handleDevToolsChange = () => {
      setDevToolsEnabled(localStorage.getItem('surplussync_dev_tools') === 'true');
    };
    window.addEventListener('surplussync_devtools_change', handleDevToolsChange);
    window.addEventListener('storage', handleDevToolsChange);
    return () => {
      window.removeEventListener('surplussync_devtools_change', handleDevToolsChange);
      window.removeEventListener('storage', handleDevToolsChange);
    };
  }, []);

  // Navigation defined strictly by role (Task B4)
  const businessNav: NavItem[] = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'inventory', label: 'Inventory', icon: Package },
    { id: 'alerts', label: 'Expiry Alerts', icon: BellRing, badge: alertCount },
    { id: 'scan', label: 'Scan', icon: ScanLine },
    { id: 'import', label: 'CSV Import', icon: UploadCloud },
    { id: 'marketplace', label: 'Surplus Marketplace', icon: Store },
    { id: 'donations', label: 'Donation Requests', icon: HeartHandshake },
    { id: 'schedule', label: 'Pickup Schedule', icon: Truck },
    { id: 'impact', label: 'Impact Analytics', icon: BarChart3 },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    ...(aiPredictionAvailable !== false
      ? [
          {
            id: 'business/ai/forecast',
            label: 'Sales & Forecast',
            icon: TrendingUp,
            section: 'AI Waste Prediction',
          },
          {
            id: 'business/ai/planner',
            label: 'Purchase Planner',
            icon: Sparkles,
          },
          {
            id: 'business/ai/insights',
            label: 'Waste Insights',
            icon: BarChart3,
          },
        ]
      : []),
    ...(devToolsEnabled ? [{ id: 'business/pos-simulator', label: 'POS Simulator', icon: Terminal }] : []),
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  const ngoNav: NavItem[] = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'feed', label: 'Food Feed', icon: Store },
    { id: 'requirements', label: 'Our Requirements', icon: ClipboardList },
    { id: 'donations', label: 'My Requests', icon: HeartHandshake },
    { id: 'schedule', label: 'Pickup Schedule', icon: Truck },
    { id: 'impact', label: 'Impact Analytics', icon: BarChart3 },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'profile', label: 'Profile & Ratings', icon: Star },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  const adminNav: NavItem[] = [
    { id: 'admin/overview', label: 'Overview', icon: LayoutDashboard },
    {
      id: 'admin/verifications',
      label: 'Verifications',
      icon: ShieldCheck,
      badge: pendingVerificationCount > 0 ? pendingVerificationCount : undefined,
    },
    { id: 'admin/organizations', label: 'Organizations', icon: Building2 },
    {
      id: 'admin/issues',
      label: 'Issues',
      icon: AlertTriangle,
      badge: openIssuesCount > 0 ? openIssuesCount : undefined,
    },
    { id: 'admin/ratings', label: 'Ratings', icon: Star },
    { id: 'admin/audit-logs', label: 'Audit Log', icon: ScrollText },
    { id: 'admin/settings', label: 'Settings', icon: Settings },
  ];

  const navItems = isPlatformAdmin ? adminNav : orgType === 'NGO' ? ngoNav : businessNav;


  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs lg:hidden transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Sidebar Container */}
      <aside
        id="app-sidebar"
        className={cn(
          'fixed left-0 top-0 h-full z-40 flex flex-col justify-between bg-[var(--surface)] text-[var(--text)] border-r border-[var(--border)] transition-all duration-200 ease-in-out',
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
          isCollapsed ? 'w-[72px]' : 'w-[240px]'
        )}
      >
        {/* Top: Logo & Brand */}
        <div className="flex flex-col">
          <div className="h-16 flex items-center justify-between px-4 border-b border-[var(--border)]">
            <div
              className={cn(
                'flex items-center gap-2.5 overflow-hidden transition-all',
                isCollapsed && 'justify-center w-full'
              )}
            >
              <div className="w-8 h-8 rounded-[8px] bg-[var(--primary)] text-white flex items-center justify-center shrink-0 shadow-sm">
                <Repeat className="w-4 h-4 stroke-[2.4]" />
              </div>
              {!isCollapsed && (
                <div className="flex flex-col min-w-0">
                  <span className="font-bold text-sm tracking-tight text-[var(--text)] select-none">
                    Surplus<span className="text-[var(--primary)]">Sync</span>
                  </span>
                  <span className="text-[10px] text-[var(--muted)] font-medium -mt-0.5">
                    {orgType === 'NGO' ? 'NGO Rescue Portal' : 'Business Inventory'}
                  </span>
                </div>
              )}
            </div>

            {/* Mobile close button */}
            <button
              onClick={onClose}
              className="lg:hidden p-1.5 rounded-[8px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] cursor-pointer"
              aria-label="Close menu"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Navigation Links */}
          <nav aria-label="Sidebar navigation" className="p-3 space-y-1 overflow-y-auto">
            {navItems.map((item) => {
              const isActive =
                activePath === item.id ||
                (item.id === 'business/pos-simulator' &&
                  (activePath === 'pos-simulator' || activePath === 'business/pos-simulator')) ||
                (item.id === 'business/ai/planner' &&
                  (activePath === 'business/ai/planner' || activePath === 'ai/planner' || activePath === 'planner')) ||
                (item.id === 'business/ai/forecast' &&
                  (activePath === 'business/ai/forecast' || activePath === 'ai/forecast' || activePath === 'forecast')) ||
                (item.id === 'business/ai/insights' &&
                  (activePath === 'business/ai/insights' || activePath === 'ai/insights' || activePath === 'insights'));
              const Icon = item.icon;
              return (
                <React.Fragment key={item.id}>
                  {item.section && !isCollapsed && (
                    <div className="pt-2.5 pb-1 px-3 text-[10px] font-bold text-[var(--muted)] uppercase tracking-wider">
                      {item.section}
                    </div>
                  )}
                  <button
                    onClick={() => {
                      onNavigate(item.id);
                      onClose();
                    }}
                  title={isCollapsed ? item.label : undefined}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-[8px] text-xs font-medium transition-all duration-150 cursor-pointer select-none',
                    isCollapsed ? 'justify-center' : 'justify-start',
                    isActive
                      ? 'bg-[var(--primary)] text-[var(--primary-foreground)] font-semibold shadow-xs'
                      : 'text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]'
                  )}
                >
                  <Icon
                    className={cn(
                      'w-4 h-4 shrink-0 transition-transform',
                      isActive ? 'text-[var(--primary-foreground)]' : 'text-[var(--muted)]'
                    )}
                  />
                  {!isCollapsed && <span className="truncate flex-1 text-left">{item.label}</span>}
                  {!isCollapsed && item.badge && item.badge > 0 && (
                    <span
                      className={cn(
                        'text-[10px] px-1.5 py-0.2 rounded-full font-bold tabular-nums',
                        isActive
                          ? 'bg-white/20 text-white'
                          : 'bg-[var(--color-danger-subtle)] text-[var(--color-danger)]'
                      )}
                    >
                      {item.badge}
                    </span>
                  )}
                  {isCollapsed && item.badge && item.badge > 0 && (
                    <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-[var(--color-danger)]" />
                  )}
                </button>
              </React.Fragment>
            );
          })}
        </nav>
        </div>

        {/* Bottom Section: Organization & Collapse Toggle */}
        <div className="border-t border-[var(--border)] p-3 space-y-2">
          {/* Organization Pill */}
          {!isCollapsed ? (
            <div className="rounded-[8px] bg-[var(--surface-2)] p-2.5 flex items-center gap-2.5 border border-[var(--border)] min-w-0">
              <div className="w-7 h-7 rounded-[6px] bg-[var(--primary)]/15 text-[var(--primary)] flex items-center justify-center shrink-0">
                {isPlatformAdmin ? (
                  <Shield className="w-3.5 h-3.5" />
                ) : orgType === 'NGO' ? (
                  <Users className="w-3.5 h-3.5" />
                ) : (
                  <Building2 className="w-3.5 h-3.5" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-semibold text-[var(--text)] truncate">
                  {isPlatformAdmin ? 'Platform Admin' : orgName}
                </p>
                <p className="text-[10px] text-[var(--muted)] truncate capitalize">
                  {isPlatformAdmin ? 'System Staff' : orgType.toLowerCase()}
                </p>
              </div>
            </div>
          ) : (
            <div
              className="flex justify-center"
              title={isPlatformAdmin ? 'Platform Administrator' : `${orgName} (${orgType})`}
            >
              <div className="w-8 h-8 rounded-[8px] bg-[var(--surface-2)] text-[var(--primary)] flex items-center justify-center border border-[var(--border)]">
                {isPlatformAdmin ? (
                  <Shield className="w-4 h-4" />
                ) : orgType === 'NGO' ? (
                  <Users className="w-4 h-4" />
                ) : (
                  <Building2 className="w-4 h-4" />
                )}
              </div>
            </div>
          )}


          {/* Desktop Collapse Toggle */}
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="hidden lg:flex w-full items-center justify-center gap-2 py-1.5 rounded-[8px] text-xs text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer"
              title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
              aria-label={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
            >
              {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
              {!isCollapsed && <span className="text-[11px]">Collapse sidebar</span>}
            </button>
          )}
        </div>
      </aside>
    </>
  );
};
