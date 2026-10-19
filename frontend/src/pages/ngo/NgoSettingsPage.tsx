import React, { useState } from 'react';
import {
  ShieldCheck,
  Sun,
  Moon,
  Truck,
  CheckCircle2,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { MapView } from '../../components/ui/MapView';
import { useCurrentUser } from '../../hooks/useData';

interface NgoSettingsPageProps {
  onTriggerToast: (msg: string) => void;
  isDark: boolean;
  onToggleTheme: () => void;
}

export const NgoSettingsPage: React.FC<NgoSettingsPageProps> = ({
  onTriggerToast,
  isDark,
  onToggleTheme,
}) => {
  const { data: user } = useCurrentUser();

  const [orgName, setOrgName] = useState(user?.organization?.name || 'Aahar Food Rescue Alliance');
  const [phone, setPhone] = useState('+91 98450 12345');
  const [address, setAddress] = useState('42 Indira Nagar, 100ft Road, Bengaluru, Karnataka 560038');
  const [dispatchRadius, setDispatchRadius] = useState<number>(15);
  const vehicleTypes = [
    'Refrigerated Transit Van (1.5 Ton)',
    'Three-Wheeler Electric Cargo',
  ];

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    onTriggerToast('Saved NGO dispatch hub and vehicle fleet profile');
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <PageHeader
        title="NGO Organization Settings"
        description="Manage your relief operations hub, dispatch coordinates, volunteer fleet capacities, and interface appearance."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Profile & Dispatch Hub (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Organization Information Card */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-[var(--text)]">
                  Relief Organization Profile
                </h3>
                <p className="text-xs text-[var(--muted)]">
                  Verified hunger relief non-profit credentials and contact details.
                </p>
              </div>
              <StatusBadge variant="success" size="sm" dot>
                Verified NGO
              </StatusBadge>
            </div>

            <form onSubmit={handleSaveProfile} className="space-y-4 pt-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-[var(--text)]">
                    NGO Registered Entity Name
                  </label>
                  <input
                    type="text"
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-xs text-[var(--text)] outline-none focus:ring-1 focus:ring-[var(--primary)]"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-[var(--text)]">
                    Operations Hotline Phone
                  </label>
                  <input
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-xs text-[var(--text)] outline-none focus:ring-1 focus:ring-[var(--primary)]"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-[var(--text)]">
                  Central Distribution Hub Address
                </label>
                <input
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-xs text-[var(--text)] outline-none focus:ring-1 focus:ring-[var(--primary)]"
                />
              </div>

              {/* Dispatch Radius Slider */}
              <div className="space-y-2 pt-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-[var(--text)]">
                    Active Dispatch Radius Horizon:
                  </span>
                  <span className="font-bold tabular-nums text-[var(--primary)]">
                    {dispatchRadius} km
                  </span>
                </div>
                <input
                  type="range"
                  min="2"
                  max="50"
                  step="1"
                  value={dispatchRadius}
                  onChange={(e) => setDispatchRadius(Number(e.target.value))}
                  className="w-full accent-[var(--primary)]"
                />
                <p className="text-[11px] text-[var(--muted)]">
                  You will receive simulated surplus notifications whenever donors list perishable batches within {dispatchRadius} km of this distribution hub.
                </p>
              </div>

              {/* Submit Button */}
              <div className="pt-2">
                <Button variant="primary" size="sm" type="submit" className="text-xs font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                  <span>Update Hub Settings</span>
                </Button>
              </div>
            </form>
          </div>

          {/* Interactive Hub Map */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text)]">
                  Dispatch Hub Coordinates &amp; Coverage
                </h3>
                <p className="text-xs text-[var(--muted)]">
                  Center pin: 12.9716° N, 77.5946° E (Bengaluru Central)
                </p>
              </div>
              <span className="text-xs font-semibold text-[var(--primary)]">
                {dispatchRadius} km Radius
              </span>
            </div>
            <div className="h-64 w-full rounded-[8px] overflow-hidden border border-[var(--border)]">
              <MapView
                markers={[
                  {
                    id: 'ngo_hub',
                    latitude: 12.9716,
                    longitude: 77.5946,
                    title: orgName,
                    subtitle: 'NGO Dispatch Base & Cold Storage',
                    isUserLocation: true,
                  },
                ]}
                center={[12.9716, 77.5946]}
                zoom={12}
              />
            </div>
          </div>
        </div>

        {/* Right Column: Fleet, Theme, Verification Info (1 col) */}
        <div className="space-y-6">
          {/* Appearance Card */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-4">
            <h3 className="text-sm font-semibold text-[var(--text)]">Interface Appearance</h3>
            <p className="text-xs text-[var(--muted)]">
              SurplusSync defaults to a dark-first SaaS aesthetic with WCAG AA compliance. You can toggle to Warm Stone light mode at any time.
            </p>
            <div className="flex items-center justify-between p-3 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)]">
              <div className="flex items-center gap-2.5">
                {isDark ? (
                  <Moon className="w-4 h-4 text-[var(--primary)]" />
                ) : (
                  <Sun className="w-4 h-4 text-[var(--accent)]" />
                )}
                <div>
                  <p className="text-xs font-semibold text-[var(--text)]">
                    {isDark ? 'Dark Theme' : 'Warm Light Theme'}
                  </p>
                  <p className="text-[10px] text-[var(--muted)]">
                    {isDark ? '#0A0E17 slate canvas' : '#F5F4F1 warm stone'}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={onToggleTheme}
                className="text-xs"
              >
                Switch
              </Button>
            </div>
          </div>

          {/* Volunteer Transport Fleet */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[var(--text)] flex items-center gap-1.5">
                <Truck className="w-4 h-4 text-[var(--primary)]" />
                <span>Transport Fleet</span>
              </h3>
              <StatusBadge variant="info" size="sm">
                2 Units Active
              </StatusBadge>
            </div>
            <p className="text-xs text-[var(--muted)]">
              Equipped vehicles registered for rapid commercial pickup dispatches:
            </p>
            <div className="space-y-2 pt-1">
              {vehicleTypes.map((v, i) => (
                <div
                  key={i}
                  className="p-2.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-xs font-medium text-[var(--text)] flex items-center gap-2"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-[var(--color-success)] shrink-0" />
                  <span>{v}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Verification Audit Note */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)]/60 p-4 space-y-2">
            <div className="flex items-center gap-2 text-xs font-semibold text-[var(--text)]">
              <ShieldCheck className="w-4 h-4 text-[var(--color-success)]" />
              <span>Admin Verification Status</span>
            </div>
            <p className="text-[11px] text-[var(--muted)] leading-relaxed">
              Your organization has been fully verified by SurplusSync system administrators. You possess full clearance to claim food batches and initiate collection dispatches across the metropolitan network.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
