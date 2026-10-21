import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Home,
  Search,
  LayoutDashboard,
  Package,
  ScanLine,
  BellRing,
  UploadCloud,
  HeartHandshake,
  BarChart3,
  Settings,
  Sun,
  Moon,
  LogOut,
  Zap,
  ArrowRight,
  UtensilsCrossed,
  Star,
  ShieldCheck,
  AlertTriangle,
  Building2,
  ScrollText,
  Terminal,
  Store,
  Truck,
  ClipboardList,
  Bell,
  Sparkles,
} from 'lucide-react';

import { cn } from '../lib/utils';
import type { OrganizationType } from '../types';

export interface CommandItem {
  id: string;
  title: string;
  subtitle?: string;
  category: 'Navigation' | 'Actions' | 'Theme';
  icon: React.ElementType;
  onSelect: () => void;
  keywords?: string[];
  role?: OrganizationType;
}

interface CommandPaletteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (path: string) => void;
  orgType?: OrganizationType;
  isPlatformAdmin?: boolean;
  isDark: boolean;
  onToggleTheme: () => void;
  onLogout: () => void;
  onSimulatePOS?: () => void;
}

export const CommandPaletteModal: React.FC<CommandPaletteModalProps> = ({
  isOpen,
  onClose,
  onNavigate,
  orgType = 'BUSINESS',
  isPlatformAdmin = false,
  isDark,

  onToggleTheme,
  onLogout,
  onSimulatePOS,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Define commands based on role
  const commands: CommandItem[] = useMemo(() => {
    const list: CommandItem[] = [];

    if (isPlatformAdmin) {
      // Platform Admin Navigation
      list.push(
        {
          id: 'nav-admin-overview',
          title: 'Platform Overview',
          subtitle: 'Real-time metrics, platform charts & quick queues',
          category: 'Navigation',
          icon: LayoutDashboard,
          onSelect: () => onNavigate('admin/overview'),
          keywords: ['admin', 'overview', 'stats', 'growth', 'kpi'],
        },
        {
          id: 'nav-admin-verifications',
          title: 'NGO Verifications Queue',
          subtitle: 'Inspect & verify pending NGO applications',
          category: 'Navigation',
          icon: ShieldCheck,
          onSelect: () => onNavigate('admin/verifications'),
          keywords: ['verify', 'ngo', 'approvals', 'compliance'],
        },
        {
          id: 'nav-admin-organizations',
          title: 'All Organizations',
          subtitle: 'Manage businesses, NGOs, and tenant users',
          category: 'Navigation',
          icon: Building2,
          onSelect: () => onNavigate('admin/organizations'),
          keywords: ['tenants', 'businesses', 'ngos', 'suspend', 'reinstate'],
        },
        {
          id: 'nav-admin-issues',
          title: 'Dispute & Issue Tickets',
          subtitle: 'Review food quality complaints and logistics disputes',
          category: 'Navigation',
          icon: AlertTriangle,
          onSelect: () => onNavigate('admin/issues'),
          keywords: ['issues', 'tickets', 'disputes', 'resolve'],
        },
        {
          id: 'nav-admin-ratings',
          title: 'Ratings & Reviews Moderation',
          subtitle: 'Moderate public donor ratings and comments',
          category: 'Navigation',
          icon: Star,
          onSelect: () => onNavigate('admin/ratings'),
          keywords: ['moderate', 'ratings', 'reviews', 'hide', 'unhide'],
        },
        {
          id: 'nav-admin-audit-logs',
          title: 'Platform Audit Log',
          subtitle: 'Append-only administrative event records',
          category: 'Navigation',
          icon: ScrollText,
          onSelect: () => onNavigate('admin/audit-logs'),
          keywords: ['audit', 'logs', 'security', 'trail'],
        },
        {
          id: 'nav-admin-settings',
          title: 'Admin Settings',
          subtitle: 'Platform diagnostics & administrative configuration',
          category: 'Navigation',
          icon: Settings,
          onSelect: () => onNavigate('admin/settings'),
          keywords: ['settings', 'health', 'diagnostics'],
        }
      );
    } else if (orgType === 'BUSINESS') {
      list.push(
        {
          id: 'nav-home',
          title: 'Home',
          subtitle: 'Welcome overview, operational cockpit & quick actions',
          category: 'Navigation',
          icon: Home,
          onSelect: () => onNavigate('home'),
          keywords: ['home', 'start', 'overview', 'welcome', 'cockpit'],
        },
        {
          id: 'nav-dashboard',
          title: 'Dashboard',
          subtitle: 'Real-time stock metrics & waste analytics',
          category: 'Navigation',
          icon: LayoutDashboard,
          onSelect: () => onNavigate('dashboard'),
          keywords: ['metrics', 'stats', 'waste'],
        },
        {
          id: 'nav-inventory',
          title: 'Inventory',
          subtitle: 'Active batches, products & FEFO tracking',
          category: 'Navigation',
          icon: Package,
          onSelect: () => onNavigate('inventory'),
          keywords: ['batches', 'stock', 'products', 'sku'],
        },
        {
          id: 'nav-alerts',
          title: 'Expiry Alerts',
          subtitle: 'Expiry horizons & threshold notices',
          category: 'Navigation',
          icon: BellRing,
          onSelect: () => onNavigate('alerts'),
          keywords: ['spoilage', 'urgent', 'notifications', 'alerts'],
        },
        {
          id: 'nav-scan',
          title: 'Scan Barcode',
          subtitle: 'Camera barcode scanner & deduction',
          category: 'Navigation',
          icon: ScanLine,
          onSelect: () => onNavigate('scan'),
          keywords: ['camera', 'qr', 'barcode', 'deduct'],
        },
        {
          id: 'nav-import',
          title: 'CSV Import',
          subtitle: 'Batch catalog & manifest upload',
          category: 'Navigation',
          icon: UploadCloud,
          onSelect: () => onNavigate('import'),
          keywords: ['excel', 'csv', 'upload', 'bulk'],
        },
        {
          id: 'nav-marketplace',
          title: 'Surplus Marketplace',
          subtitle: 'Create surplus listings & manage offers',
          category: 'Navigation',
          icon: Store,
          onSelect: () => onNavigate('marketplace'),
          keywords: ['marketplace', 'surplus', 'food', 'listings'],
        },
        {
          id: 'nav-donations',
          title: 'Donation Requests',
          subtitle: 'Review and approve NGO rescue requests',
          category: 'Navigation',
          icon: HeartHandshake,
          onSelect: () => onNavigate('donations'),
          keywords: ['rescue', 'ngo', 'charity', 'requests', 'approve'],
        },
        {
          id: 'nav-schedule',
          title: 'Pickup Schedule',
          subtitle: 'Pickup logistics calendar and agenda',
          category: 'Navigation',
          icon: Truck,
          onSelect: () => onNavigate('schedule'),
          keywords: ['schedule', 'pickups', 'logistics', 'calendar'],
        },
        {
          id: 'nav-notifications',
          title: 'Notifications',
          subtitle: 'System alerts, matching listings & requests',
          category: 'Navigation',
          icon: Bell,
          onSelect: () => onNavigate('notifications'),
          keywords: ['notifications', 'alerts', 'messages', 'bell'],
        },
        {
          id: 'nav-planner',
          title: 'Purchase Planner (AI)',
          subtitle: 'Evaluate purchase plans to prevent over-order waste',
          category: 'Navigation',
          icon: Sparkles,
          onSelect: () => onNavigate('business/ai/planner'),
          keywords: ['planner', 'ai', 'demand', 'forecast', 'purchase', 'waste'],
        },
        {
          id: 'nav-insights',
          title: 'Benchmark Waste Insights',
          subtitle: 'Empirical cross-sectional waste patterns & multipliers',
          category: 'Navigation',
          icon: BarChart3,
          onSelect: () => onNavigate('business/ai/insights'),
          keywords: ['insights', 'benchmark', 'dataset', 'waste', 'weather', 'promotion'],
        }
      );

      if (typeof window !== 'undefined' && localStorage.getItem('surplussync_dev_tools') === 'true') {
        list.push({
          id: 'nav-pos-simulator',
          title: 'POS Terminal Simulator',
          subtitle: 'Fake cash register & API key wire tester',
          category: 'Navigation',
          icon: Terminal,
          onSelect: () => onNavigate('business/pos-simulator'),
          keywords: ['pos', 'terminal', 'register', 'simulator', 'wire', 'idempotency'],
        });
      }
    } else {
      // NGO Navigation
      list.push(
        {
          id: 'nav-home',
          title: 'Home',
          subtitle: 'Welcome overview, operational cockpit & quick actions',
          category: 'Navigation',
          icon: Home,
          onSelect: () => onNavigate('home'),
          keywords: ['home', 'start', 'overview', 'welcome', 'cockpit'],
        },
        {
          id: 'nav-dashboard',
          title: 'Dashboard',
          subtitle: 'Active rescues & impact overview',
          category: 'Navigation',
          icon: LayoutDashboard,
          onSelect: () => onNavigate('dashboard'),
          keywords: ['metrics', 'overview'],
        },
        {
          id: 'nav-feed',
          title: 'Food Feed',
          subtitle: 'Live surplus food listings nearby',
          category: 'Navigation',
          icon: UtensilsCrossed,
          onSelect: () => onNavigate('feed'),
          keywords: ['marketplace', 'donations', 'nearby', 'meals', 'feed'],
        },
        {
          id: 'nav-requirements',
          title: 'Our Requirements',
          subtitle: 'Manage organizational food demand and intake',
          category: 'Navigation',
          icon: ClipboardList,
          onSelect: () => onNavigate('requirements'),
          keywords: ['requirements', 'demand', 'needs', 'food'],
        },
        {
          id: 'nav-donations',
          title: 'My Requests',
          subtitle: 'Track active pickups & completed distributions',
          category: 'Navigation',
          icon: HeartHandshake,
          onSelect: () => onNavigate('donations'),
          keywords: ['requests', 'claims', 'pickups', 'logistics', 'status'],
        },
        {
          id: 'nav-schedule',
          title: 'Pickup Schedule',
          subtitle: 'Pickup logistics calendar and agenda',
          category: 'Navigation',
          icon: Truck,
          onSelect: () => onNavigate('schedule'),
          keywords: ['schedule', 'pickups', 'logistics', 'calendar'],
        },
        {
          id: 'nav-notifications',
          title: 'Notifications',
          subtitle: 'System alerts, matching listings & requests',
          category: 'Navigation',
          icon: Bell,
          onSelect: () => onNavigate('notifications'),
          keywords: ['notifications', 'alerts', 'messages', 'bell'],
        },
        {
          id: 'nav-profile',
          title: 'NGO Profile & Ratings',
          subtitle: 'Rate donors, review completed claims & manage hub profile',
          category: 'Navigation',
          icon: Star,
          onSelect: () => onNavigate('profile'),
          keywords: ['rate', 'ratings', 'reviews', 'donor', 'stars', 'profile'],
        }
      );
    }


    // Shared navigation
    list.push(
      {
        id: 'nav-impact',
        title: 'Impact & Environmental Analytics',
        subtitle: 'Kg diverted, meals provided & CO2e avoided',
        category: 'Navigation',
        icon: BarChart3,
        onSelect: () => onNavigate('impact'),
        keywords: ['carbon', 'sustainability', 'meals'],
      },
      {
        id: 'nav-settings',
        title: 'Settings',
        subtitle: 'Profile, location & API keys',
        category: 'Navigation',
        icon: Settings,
        onSelect: () => onNavigate('settings'),
        keywords: ['account', 'keys', 'appearance'],
      }
    );

    // Actions
    if (onSimulatePOS) {
      list.push({
        id: 'act-pos-sale',
        title: 'Simulate POS Sale',
        subtitle: 'Deduct stock with strict FEFO ordering',
        category: 'Actions',
        icon: Zap,
        onSelect: onSimulatePOS,
        keywords: ['deduct', 'register', 'checkout', 'sale'],
      });
    }

    list.push(
      {
        id: 'act-theme',
        title: isDark ? 'Switch to Warm Light Theme' : 'Switch to Dark Theme',
        subtitle: 'Toggle application color appearance',
        category: 'Theme',
        icon: isDark ? Sun : Moon,
        onSelect: onToggleTheme,
        keywords: ['dark', 'light', 'appearance', 'mode'],
      },
      {
        id: 'act-logout',
        title: 'Sign Out',
        subtitle: 'End your current session',
        category: 'Actions',
        icon: LogOut,
        onSelect: onLogout,
        keywords: ['exit', 'leave'],
      }
    );

    return list;
  }, [orgType, isPlatformAdmin, isDark, onNavigate, onToggleTheme, onLogout, onSimulatePOS]);


  // Filter commands by query
  const filteredCommands = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter((cmd) => {
      const matchTitle = cmd.title.toLowerCase().includes(q);
      const matchSub = cmd.subtitle?.toLowerCase().includes(q);
      const matchKey = cmd.keywords?.some((k) => k.toLowerCase().includes(q));
      return matchTitle || matchSub || matchKey;
    });
  }, [commands, query]);

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % (filteredCommands.length || 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % (filteredCommands.length || 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredCommands[selectedIndex]) {
        filteredCommands[selectedIndex].onSelect();
        onClose();
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command Search Palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-150"
        onClick={onClose}
      />

      {/* Palette Container */}
      <div
        className="relative z-10 w-full max-w-xl rounded-[12px] border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150"
      >
        {/* Input Bar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3 bg-[var(--surface)]">
          <Search className="w-4 h-4 text-[var(--muted)] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Search pages, features, or quick actions... (↑↓ to select, Enter to run)"
            className="w-full bg-transparent text-sm text-[var(--text)] placeholder:text-[var(--muted)] focus:outline-none"
          />
          <kbd className="hidden sm:inline-block rounded-[6px] border border-[var(--border)] bg-[var(--surface-2)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--muted)]">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-[360px] overflow-y-auto p-2">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-xs text-[var(--muted)]">
              No matching commands or pages found.
            </div>
          ) : (
            <div className="space-y-1">
              {filteredCommands.map((cmd, idx) => {
                const Icon = cmd.icon;
                const isSelected = idx === selectedIndex;
                return (
                  <button
                    key={cmd.id}
                    type="button"
                    onClick={() => {
                      cmd.onSelect();
                      onClose();
                    }}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={cn(
                      'w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-[8px] text-left transition-colors cursor-pointer',
                      isSelected
                        ? 'bg-[var(--primary)] text-[var(--primary-foreground)]'
                        : 'text-[var(--text)] hover:bg-[var(--surface-2)]'
                    )}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className={cn(
                          'p-1.5 rounded-[6px]',
                          isSelected
                            ? 'bg-white/20 text-white'
                            : 'bg-[var(--surface-2)] text-[var(--primary)]'
                        )}
                      >
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold truncate">{cmd.title}</p>
                        {cmd.subtitle && (
                          <p
                            className={cn(
                              'text-[11px] truncate',
                              isSelected ? 'text-white/80' : 'text-[var(--muted)]'
                            )}
                          >
                            {cmd.subtitle}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className={cn(
                          'text-[10px] px-1.5 py-0.5 rounded-[4px] border font-medium',
                          isSelected
                            ? 'border-white/30 bg-white/10 text-white'
                            : 'border-[var(--border)] bg-[var(--surface-2)] text-[var(--muted)]'
                        )}
                      >
                        {cmd.category}
                      </span>
                      <ArrowRight className="w-3.5 h-3.5 opacity-60" />
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="border-t border-[var(--border)] bg-[var(--surface-2)] px-4 py-2 text-[11px] text-[var(--muted)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>Navigation:</span>
            <kbd className="rounded border border-[var(--border)] bg-[var(--surface)] px-1 text-[10px]">↑</kbd>
            <kbd className="rounded border border-[var(--border)] bg-[var(--surface)] px-1 text-[10px]">↓</kbd>
            <kbd className="rounded border border-[var(--border)] bg-[var(--surface)] px-1 text-[10px]">↵</kbd>
          </div>
          <span>Active Role: <strong className="text-[var(--text)] font-semibold">{orgType}</strong></span>
        </div>
      </div>
    </div>
  );
};
