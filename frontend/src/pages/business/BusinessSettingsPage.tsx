import React, { useState } from 'react';
import {
  Building2,
  Key,
  MapPin,
  Moon,
  Sun,
  Copy,
  Check,
  RefreshCw,
  Plus,
  ShieldAlert,
  Laptop,
  Terminal,
  Database,
  HardDrive,
  RotateCcw,
  CheckCircle2,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { MapView, type MapMarker } from '../../components/ui/MapView';
import { useCurrentUser, usePOSKeys, useCreatePOSKey, useRotatePOSKey } from '../../hooks/useData';
import { setDataSourceMode, defaultMode } from '../../services';
import type { POSKey } from '../../types';

interface BusinessSettingsPageProps {
  onTriggerToast: (msg: string) => void;
  isDark: boolean;
  onToggleTheme: () => void;
  onNavigate?: (path: string) => void;
}

export const BusinessSettingsPage: React.FC<BusinessSettingsPageProps> = ({
  onTriggerToast,
  isDark,
  onToggleTheme,
  onNavigate,
}) => {
  const { data: user } = useCurrentUser();
  const { data: posKeys, isLoading: isKeysLoading } = usePOSKeys();
  const createKeyMutation = useCreatePOSKey();
  const rotateKeyMutation = useRotatePOSKey();

  // Developer tools toggle (persisted to localStorage)
  const [devToolsEnabled, setDevToolsEnabled] = useState<boolean>(() => {
    return typeof window !== 'undefined' && localStorage.getItem('surplussync_dev_tools') === 'true';
  });

  const handleToggleDevTools = () => {
    const next = !devToolsEnabled;
    setDevToolsEnabled(next);
    localStorage.setItem('surplussync_dev_tools', next ? 'true' : 'false');
    window.dispatchEvent(new Event('surplussync_devtools_change'));
    onTriggerToast(
      next
        ? 'Developer tools enabled (POS simulator available in navigation)'
        : 'Developer tools disabled'
    );
  };

  // Data Source Mode state (Live vs Demo)
  const [dataMode, setDataMode] = useState<'live' | 'demo'>(() => {
    const stored = typeof window !== 'undefined' ? localStorage.getItem('surplussync_data_mode') : null;
    if (stored === 'live' || stored === 'demo') return stored;
    return defaultMode;
  });

  const handleToggleMode = (mode: 'live' | 'demo') => {
    setDataMode(mode);
    setDataSourceMode(mode);
    queryClient.clear();
    onTriggerToast(
      mode === 'live'
        ? 'Switched to Live Backend Mode (Django DB on http://127.0.0.1:8000)'
        : 'Switched to Demo Sandbox Mode (LocalStorage Persistent)'
    );
  };

  const handleClearDemoCache = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('surplussync_demo_custom_products');
      localStorage.removeItem('surplussync_demo_custom_batches');
    }
    onTriggerToast('Cleared custom demo data cache. Default sample fixtures will load on refresh.');
  };

  // Created key modal state
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [keyLabel, setKeyLabel] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  // Profile fields state
  const [orgName, setOrgName] = useState(user?.organization?.name || 'The Grand Gateway Bengaluru');
  const [address, setAddress] = useState(user?.organization?.address || '45 MG Road, Ashok Nagar, Bengaluru 560001');
  const [phone, setPhone] = useState(user?.organization?.phone || '+91 80 4123 4567');

  const latitude = user?.organization?.latitude || 12.9716;
  const longitude = user?.organization?.longitude || 77.5946;

  const mapMarkers: MapMarker[] = [
    {
      id: 'org-location',
      latitude,
      longitude,
      title: orgName,
      subtitle: address,
      badge: 'Main Facility Location',
    },
  ];

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    onTriggerToast('Organization profile details updated');
  };

  const handleGeneratePOSKey = () => {
    if (!keyLabel.trim()) {
      onTriggerToast('Please enter a descriptive label for the terminal');
      return;
    }
    setIsGenerating(true);
    createKeyMutation.mutate(keyLabel, {
      onSuccess: (res) => {
        setIsGenerating(false);
        setKeyLabel('');
        setNewlyCreatedKey(res.raw_key || 'pos_live_' + Math.random().toString(36).substring(2, 18));
        onTriggerToast('Generated new POS Integration Key');
      },
      onError: () => {
        setIsGenerating(false);
      },
    });
  };

  const handleCopyKey = () => {
    if (!newlyCreatedKey) return;
    navigator.clipboard.writeText(newlyCreatedKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onTriggerToast('Copied POS Key to clipboard');
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <PageHeader
        title="Organization Settings"
        description="Manage your enterprise facility profile, geographic coordinates for NGO pickups, and automated POS API keys."
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Profile & Geolocation (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Organization Profile */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4">
            <h3 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2 border-b border-[var(--border)] pb-3">
              <Building2 className="w-4 h-4 text-[var(--primary)]" />
              <span>Facility &amp; Business Profile</span>
            </h3>

            <form onSubmit={handleSaveProfile} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">
                  Organization Legal Name
                </label>
                <input
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-[var(--text)] mb-1">
                    Contact Phone
                  </label>
                  <input
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-[var(--text)] mb-1">
                    Operating Type
                  </label>
                  <input
                    type="text"
                    disabled
                    value={user?.organization?.type || 'BUSINESS'}
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)]/50 p-2.5 text-[var(--muted)] cursor-not-allowed font-semibold"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">
                  Facility Address
                </label>
                <textarea
                  rows={2}
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
                />
              </div>

              <div className="flex justify-end">
                <Button variant="primary" size="sm" type="submit">
                  Save Changes
                </Button>
              </div>
            </form>
          </div>

          {/* Facility Location Map */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2">
                <MapPin className="w-4 h-4 text-[var(--primary)]" />
                <span>Pickup Geolocation Coordinates</span>
              </h3>
              <span className="font-mono text-[11px] text-[var(--muted)]">
                {latitude.toFixed(4)}, {longitude.toFixed(4)}
              </span>
            </div>
            <p className="text-xs text-[var(--muted)]">
              This pin defines the navigation waypoint provided to NGO rescue vehicles upon pickup confirmation.
            </p>

            <div className="h-60 w-full rounded-[10px] border border-[var(--border)] overflow-hidden shadow-xs">
              <MapView markers={mapMarkers} center={[latitude, longitude]} zoom={14} />
            </div>
          </div>
        </div>

        {/* Right Column: POS API Keys & Appearance (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* POS API Keys Card */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <h3 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2">
                <Key className="w-4 h-4 text-[var(--primary)]" />
                <span>POS &amp; ERP API Keys</span>
              </h3>
              <StatusBadge status="API v1" variant="info">
                API v1
              </StatusBadge>
            </div>

            <p className="text-xs text-[var(--muted)] leading-relaxed">
              Generate secure authorization bearer tokens to automatically deduct stock batches from your point-of-sale registers.
            </p>

            {/* Generate Key Input */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="e.g. Register 1 - Front Bakery"
                  value={keyLabel}
                  onChange={(e) => setKeyLabel(e.target.value)}
                  className="flex-1 rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2 text-xs text-[var(--text)] outline-none focus:border-[var(--primary)]"
                />
                <Button
                  variant="primary"
                  size="sm"
                  disabled={isGenerating || !keyLabel.trim()}
                  onClick={handleGeneratePOSKey}
                  className="gap-1.5 text-xs shrink-0"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Generate</span>
                </Button>
              </div>
            </div>

            {/* Newly Created Key Modal Banner (Shown Once!) */}
            {newlyCreatedKey && (
              <div className="p-3.5 rounded-[8px] border border-[var(--color-warning-border)] bg-[var(--color-warning-subtle)] space-y-2.5 animate-in fade-in duration-200">
                <div className="flex items-start gap-2 text-xs text-[var(--color-warning)] font-semibold">
                  <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>Copy your POS API key now. It will not be shown again!</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 p-2 rounded-[6px] bg-[var(--surface)] font-mono text-xs text-[var(--text)] truncate border border-[var(--border)]">
                    {newlyCreatedKey}
                  </code>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopyKey}
                    className="h-8 px-2.5 text-xs shrink-0 gap-1"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-[var(--color-success)]" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                  </Button>
                </div>
              </div>
            )}

            {/* Existing Keys List */}
            <div className="space-y-2 pt-2">
              <span className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider">
                Configured Terminals
              </span>
              {isKeysLoading ? (
                <div className="h-14 rounded-[8px] bg-[var(--surface-2)] animate-pulse" />
              ) : (posKeys || []).length === 0 ? (
                <p className="text-xs text-[var(--muted)] py-2">No active POS keys configured.</p>
              ) : (
                <div className="space-y-2">
                  {(posKeys || []).map((k: POSKey) => (
                    <div
                      key={k.id}
                      className="p-3 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-between text-xs"
                    >
                      <div>
                        <p className="font-semibold text-[var(--text)]">{k.label}</p>
                        <p className="font-mono text-[10px] text-[var(--muted)]">
                          {k.key_prefix || 'sk_live_pos'}... • Active Integration Token
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          rotateKeyMutation.mutate(k.id);
                          onTriggerToast(`Rotated key for ${k.label}`);
                        }}
                        className="text-[11px] h-7 px-2 gap-1 text-[var(--muted)] hover:text-[var(--text)]"
                      >
                        <RefreshCw className="w-3 h-3" />
                        <span>Rotate</span>
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Appearance & Theme Settings Card */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4">
            <h3 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2 border-b border-[var(--border)] pb-3">
              <Laptop className="w-4 h-4 text-[var(--primary)]" />
              <span>Theme &amp; Display Appearance</span>
            </h3>

            <p className="text-xs text-[var(--muted)]">
              Choose your interface theme. SurplusSync defaults to Dark mode with high WCAG AA contrast.
            </p>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <button
                type="button"
                onClick={() => !isDark && onToggleTheme()}
                className={`p-3.5 rounded-[10px] border flex flex-col items-center gap-2 transition-all ${
                  isDark
                    ? 'border-[var(--primary)] bg-[var(--surface-2)] text-[var(--text)] shadow-xs ring-1 ring-[var(--primary)]'
                    : 'border-[var(--border)] bg-[var(--surface)] text-[var(--muted)] hover:text-[var(--text)]'
                }`}
              >
                <Moon className="w-5 h-5 text-[var(--primary)]" />
                <span className="font-semibold">Dark Theme</span>
                <span className="text-[10px] opacity-75">Default #0A0E17</span>
              </button>

              <button
                type="button"
                onClick={() => isDark && onToggleTheme()}
                className={`p-3.5 rounded-[10px] border flex flex-col items-center gap-2 transition-all ${
                  !isDark
                    ? 'border-[var(--primary)] bg-[var(--surface-2)] text-[var(--text)] shadow-xs ring-1 ring-[var(--primary)]'
                    : 'border-[var(--border)] bg-[var(--surface)] text-[var(--muted)] hover:text-[var(--text)]'
                }`}
              >
                <Sun className="w-5 h-5 text-[var(--accent)]" />
                <span className="font-semibold">Warm Light</span>
                <span className="text-[10px] opacity-75">Warm Stone #F5F4F1</span>
              </button>
            </div>
          </div>

          {/* Developer Tools & POS Simulator Card */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <h3 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2">
                <Terminal className="w-4 h-4 text-[var(--primary)]" />
                <span>Developer Tools</span>
              </h3>
              <StatusBadge
                variant={devToolsEnabled ? 'success' : 'neutral'}
                size="sm"
              >
                {devToolsEnabled ? 'Enabled' : 'Disabled'}
              </StatusBadge>
            </div>

            <p className="text-xs text-[var(--muted)] leading-relaxed">
              Enable the developer POS Cash Register simulator to test live backend API keys, create receipts, verify FEFO batch deductions, and inspect HTTP payloads.
            </p>

            <div className="flex items-center justify-between p-3 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)]">
              <div>
                <p className="text-xs font-semibold text-[var(--text)]">POS Terminal Simulator</p>
                <p className="text-[11px] text-[var(--muted)]">Adds simulator to navigation menu</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={devToolsEnabled}
                onClick={handleToggleDevTools}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                  devToolsEnabled ? 'bg-[var(--primary)]' : 'bg-[var(--surface)] border border-[var(--border)]'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                    devToolsEnabled ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {devToolsEnabled && (
              <div className="pt-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onNavigate?.('business/pos-simulator')}
                  className="w-full justify-center text-xs gap-1.5"
                >
                  <Terminal className="w-3.5 h-3.5" />
                  <span>Launch POS Simulator</span>
                </Button>
              </div>
            )}
          </div>

          {/* Data Source & Persistence Environment Card */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <h3 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2">
                <Database className="w-4 h-4 text-[var(--primary)]" />
                <span>Data Source &amp; Backend Mode</span>
              </h3>
              <StatusBadge
                variant={dataMode === 'live' ? 'success' : 'info'}
                size="sm"
              >
                {dataMode === 'live' ? 'Live Backend' : 'Demo Sandbox'}
              </StatusBadge>
            </div>

            <p className="text-xs text-[var(--muted)] leading-relaxed">
              Choose whether SurplusSync runs against your live Django database on port 8000 or the in-browser Demo Sandbox. In Demo Sandbox, any imported CSV batches or products are automatically preserved across browser refreshes using localStorage.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <button
                type="button"
                onClick={() => handleToggleMode('live')}
                className={`p-3.5 rounded-[10px] border flex flex-col text-left gap-1.5 transition-all cursor-pointer ${
                  dataMode === 'live'
                    ? 'border-[var(--primary)] bg-[var(--surface-2)] shadow-xs ring-1 ring-[var(--primary)]'
                    : 'border-[var(--border)] bg-[var(--surface)] hover:border-[var(--muted)]'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className="font-semibold text-[var(--text)] flex items-center gap-1.5">
                    <HardDrive className="w-4 h-4 text-[var(--primary)]" />
                    Live Backend
                  </span>
                  {dataMode === 'live' && (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[var(--color-success)]" />
                  )}
                </div>
                <p className="text-[11px] text-[var(--muted)] leading-relaxed">
                  Real SQLite/PostgreSQL database via Django REST API at <code>http://127.0.0.1:8000</code>.
                </p>
              </button>

              <button
                type="button"
                onClick={() => handleToggleMode('demo')}
                className={`p-3.5 rounded-[10px] border flex flex-col text-left gap-1.5 transition-all cursor-pointer ${
                  dataMode === 'demo'
                    ? 'border-[var(--primary)] bg-[var(--surface-2)] shadow-xs ring-1 ring-[var(--primary)]'
                    : 'border-[var(--border)] bg-[var(--surface)] hover:border-[var(--muted)]'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className="font-semibold text-[var(--text)] flex items-center gap-1.5">
                    <Database className="w-4 h-4 text-[var(--primary)]" />
                    Demo Sandbox
                  </span>
                  {dataMode === 'demo' && (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[var(--color-success)]" />
                  )}
                </div>
                <p className="text-[11px] text-[var(--muted)] leading-relaxed">
                  Offline-ready sandbox. Custom CSV imports and edits persist across browser refreshes via localStorage.
                </p>
              </button>
            </div>

            {dataMode === 'demo' && (
              <div className="pt-2 border-t border-[var(--border)] flex items-center justify-between text-xs">
                <span className="text-[11px] text-[var(--muted)]">Need to clear custom imported demo batches?</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearDemoCache}
                  className="text-xs h-7 gap-1"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Reset Demo Cache</span>
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
