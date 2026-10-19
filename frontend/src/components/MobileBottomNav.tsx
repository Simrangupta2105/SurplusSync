import React, { useState } from 'react';
import {
  LayoutDashboard,
  Package,
  ScanLine,
  BellRing,
  MoreHorizontal,
  UploadCloud,
  HeartHandshake,
  BarChart3,
  Settings,
  LogOut,
  X,
  UtensilsCrossed,
  Star,
  ShieldCheck,
  AlertTriangle,
  Building2,
  ScrollText,
  Terminal,
} from 'lucide-react';
import { cn } from '../lib/utils';
import type { OrganizationType } from '../types';

interface MobileBottomNavProps {
  activePath: string;
  onNavigate: (path: string) => void;
  orgType?: OrganizationType;
  alertCount?: number;
  isPlatformAdmin?: boolean;
  onLogout: () => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ElementType;
  badge?: number;
  subtitle?: string;
}

export const MobileBottomNav: React.FC<MobileBottomNavProps> = ({
  activePath,
  onNavigate,
  orgType = 'BUSINESS',
  alertCount = 0,
  isPlatformAdmin = false,
  onLogout,
}) => {
  const [isMoreOpen, setIsMoreOpen] = useState(false);

  // Listen to developer tools toggle
  const [devToolsEnabled, setDevToolsEnabled] = useState<boolean>(() => {
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

  // Business 4 Primary items + More
  const businessPrimary: NavItem[] = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'inventory', label: 'Inventory', icon: Package },
    { id: 'scan', label: 'Scan', icon: ScanLine },
    { id: 'alerts', label: 'Alerts', icon: BellRing, badge: alertCount },
  ];

  const businessMore: NavItem[] = [
    { id: 'import', label: 'CSV Import', icon: UploadCloud, subtitle: 'Batch file import' },
    { id: 'donations', label: 'Donations', icon: HeartHandshake, subtitle: 'Surplus food listings & claims' },
    { id: 'impact', label: 'Impact', icon: BarChart3, subtitle: 'Diverted kg & meals' },
    ...(devToolsEnabled
      ? [
          {
            id: 'business/pos-simulator',
            label: 'POS Simulator',
            icon: Terminal,
            subtitle: 'Fake cash register & wire tester',
          },
        ]
      : []),
    { id: 'settings', label: 'Settings', icon: Settings, subtitle: 'Account & POS keys' },
  ];

  // NGO 4 Primary items + More
  const ngoPrimary: NavItem[] = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'feed', label: 'Food Feed', icon: UtensilsCrossed },
    { id: 'claims', label: 'My Claims', icon: HeartHandshake },
    { id: 'impact', label: 'Impact', icon: BarChart3 },
  ];

  const ngoMore: NavItem[] = [
    { id: 'profile', label: 'Profile & Ratings', icon: Star, subtitle: 'Rate donors & view reviews' },
    { id: 'settings', label: 'Settings', icon: Settings, subtitle: 'Hub & preferences' },
  ];

  // Admin 4 Primary items + More
  const adminPrimary: NavItem[] = [
    { id: 'admin/overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'admin/verifications', label: 'Verify', icon: ShieldCheck },
    { id: 'admin/organizations', label: 'Orgs', icon: Building2 },
    { id: 'admin/issues', label: 'Issues', icon: AlertTriangle },
  ];

  const adminMore: NavItem[] = [
    { id: 'admin/ratings', label: 'Ratings Moderation', icon: Star, subtitle: 'Review & moderate ratings' },
    { id: 'admin/audit-logs', label: 'Platform Audit Log', icon: ScrollText, subtitle: 'Security audit trail' },
    { id: 'admin/settings', label: 'Admin Settings', icon: Settings, subtitle: 'System diagnostics' },
  ];

  const primaryItems = isPlatformAdmin ? adminPrimary : orgType === 'NGO' ? ngoPrimary : businessPrimary;
  const moreItems = isPlatformAdmin ? adminMore : orgType === 'NGO' ? ngoMore : businessMore;


  return (
    <>
      {/* Mobile Bottom Navigation Bar (< 1024px) */}
      <nav
        aria-label="Mobile Bottom Navigation"
        className="lg:hidden fixed bottom-0 left-0 right-0 h-16 bg-[var(--surface)]/95 backdrop-blur-md z-30 flex items-center justify-around px-2 border-t border-[var(--border)] transition-colors duration-150"
      >
        {primaryItems.map((item) => {
          const isActive = activePath === item.id;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={cn(
                'flex flex-col items-center justify-center gap-1 text-center relative py-1 px-3 rounded-[8px] transition-colors cursor-pointer select-none min-w-[56px]',
                isActive
                  ? 'text-[var(--primary)] font-semibold'
                  : 'text-[var(--muted)] hover:text-[var(--text)]'
              )}
            >
              <div className="relative">
                <Icon className={cn('w-5 h-5', isActive && 'text-[var(--primary)]')} />
                {item.badge && item.badge > 0 && (
                  <span className="absolute -top-1 -right-1 w-2 h-2 bg-[var(--color-danger)] rounded-full animate-pulse" />
                )}
              </div>
              <span className="text-[10px] leading-tight">{item.label}</span>
            </button>
          );
        })}

        {/* 5th Item: More Drawer Trigger */}
        <button
          onClick={() => setIsMoreOpen(true)}
          className={cn(
            'flex flex-col items-center justify-center gap-1 text-center relative py-1 px-3 rounded-[8px] transition-colors cursor-pointer select-none min-w-[56px]',
            isMoreOpen ||
              moreItems.some(
                (m) =>
                  m.id === activePath ||
                  (m.id === 'business/pos-simulator' && (activePath === 'pos-simulator' || activePath === 'business/pos-simulator'))
              )
              ? 'text-[var(--primary)] font-semibold'
              : 'text-[var(--muted)] hover:text-[var(--text)]'
          )}
        >
          <MoreHorizontal className="w-5 h-5" />
          <span className="text-[10px] leading-tight">More</span>
        </button>
      </nav>

      {/* "More" Bottom Sheet Modal */}
      {isMoreOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="lg:hidden fixed inset-0 z-50 flex flex-col justify-end"
        >
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
            onClick={() => setIsMoreOpen(false)}
          />

          {/* Drawer Sheet */}
          <div className="relative z-10 w-full rounded-t-[16px] border-t border-[var(--border)] bg-[var(--surface)] text-[var(--text)] p-4 shadow-2xl space-y-3 animate-in slide-in-from-bottom duration-200">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <span className="text-sm font-semibold text-[var(--text)]">More Options</span>
              <button
                onClick={() => setIsMoreOpen(false)}
                className="p-1 rounded-[8px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1">
              {moreItems.map((item) => {
                const Icon = item.icon;
                const isActive =
                  activePath === item.id ||
                  (item.id === 'business/pos-simulator' &&
                    (activePath === 'pos-simulator' || activePath === 'business/pos-simulator'));
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      onNavigate(item.id);
                      setIsMoreOpen(false);
                    }}
                    className={cn(
                      'w-full flex items-center gap-3 px-3 py-2.5 rounded-[8px] text-left transition-colors cursor-pointer',
                      isActive
                        ? 'bg-[var(--primary)] text-white'
                        : 'text-[var(--text)] hover:bg-[var(--surface-2)]'
                    )}
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-semibold">{item.label}</p>
                      <p className={cn('text-[10px]', isActive ? 'text-white/80' : 'text-[var(--muted)]')}>
                        {item.subtitle}
                      </p>
                    </div>
                  </button>
                );
              })}

              {/* Sign Out */}
              <div className="pt-2 border-t border-[var(--border)]">
                <button
                  onClick={() => {
                    setIsMoreOpen(false);
                    onLogout();
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-[8px] text-xs font-semibold text-[var(--color-danger)] hover:bg-[var(--color-danger-subtle)] transition-colors cursor-pointer"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
