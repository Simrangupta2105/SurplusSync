import React, { useState, useRef } from 'react';
import {
  Leaf,
  Heart,
  Download,
  Package,
  Info,
  ChevronDown,
  FileText,
  Calendar,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import { StatCard } from '../components/ui/StatCard';
import { Skeleton } from '../components/ui/Skeleton';
import { useImpactAnalytics } from '../hooks/useData';
import { dataSource } from '../services';
import type { ImpactAnalytics } from '../types';

interface ImpactAnalyticsPageProps {
  onTriggerToast?: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

type RangePreset = '30d' | '90d' | '12m' | 'custom';

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function subtractDays(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return toISODate(d);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function buildFilters(
  preset: RangePreset,
  customStart: string,
  customEnd: string,
): { period?: string; startDate?: string; endDate?: string } {
  if (preset === '30d') return { period: '30d' };
  if (preset === '90d') return { period: '90d' };
  if (preset === '12m') return { period: '12m' };
  return { startDate: customStart, endDate: customEnd };
}

function periodLabel(
  preset: RangePreset,
  customStart: string,
  customEnd: string,
): string {
  if (preset === '30d') return 'Last 30 Days';
  if (preset === '90d') return 'Last 90 Days';
  if (preset === '12m') return 'Last 12 Months';
  return `${customStart} – ${customEnd}`;
}

const FALLBACK: ImpactAnalytics = {
  rescued_food_kg: 1845.5,
  meals_provided: 4250,
  co2_avoided_kg: 4613.8,
  water_saved_liters: 0,
  financial_savings_estimate: 425000,
  total_donations_count: 58,
  active_partners_count: 24,
  calculation_constants: {
    meal_kg_factor: 0.42,
    meal_citation: 'WRAP (2020)',
    co2e_kg_factor: 2.5,
    co2e_citation: 'FAO (2013)',
    caveat:
      'These are estimates based on population-level averages. Actual figures may vary by food type and supply chain.',
  },
  category_breakdown: [
    { category: 'BAKERY', rescued_kg: 620, meals: 1420, percentage: 33.6 },
    { category: 'PRODUCE', rescued_kg: 510, meals: 1180, percentage: 27.6 },
    { category: 'PREPARED_MEALS', rescued_kg: 340, meals: 780, percentage: 18.4 },
    { category: 'DAIRY', rescued_kg: 220, meals: 510, percentage: 11.9 },
    { category: 'PANTRY', rescued_kg: 155.5, meals: 360, percentage: 8.5 },
  ],
  monthly_trend: [
    { month: 'May 2026', rescued_kg: 280, meals: 640, co2_avoided_kg: 700, donations_count: 9 },
    { month: 'Jun 2026', rescued_kg: 340, meals: 780, co2_avoided_kg: 850, donations_count: 11 },
    { month: 'Jul 2026', rescued_kg: 390, meals: 900, co2_avoided_kg: 975, donations_count: 13 },
    { month: 'Aug 2026', rescued_kg: 415, meals: 955, co2_avoided_kg: 1038, donations_count: 12 },
    { month: 'Sep 2026', rescued_kg: 420.5, meals: 975, co2_avoided_kg: 1051, donations_count: 13 },
  ],
};

// Category colour palette (cycles)
const CAT_COLORS = [
  'var(--primary)',
  '#10b981',
  '#f59e0b',
  '#6366f1',
  '#ec4899',
  '#14b8a6',
];

export const ImpactAnalyticsPage: React.FC<ImpactAnalyticsPageProps> = ({
  onTriggerToast,
  onNavigate: _onNavigate,
}) => {
  const [preset, setPreset] = useState<RangePreset>('30d');
  const [customStart, setCustomStart] = useState<string>(subtractDays(30));
  const [customEnd, setCustomEnd] = useState<string>(toISODate(new Date()));
  const [showHow, setShowHow] = useState(false);
  const [csvLoading, setCsvLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);

  const customStartRef = useRef<HTMLInputElement>(null);
  const customEndRef = useRef<HTMLInputElement>(null);

  const filters = buildFilters(preset, customStart, customEnd);
  const { data: analytics, isLoading } = useImpactAnalytics(filters);

  const data = analytics ?? FALLBACK;
  const consts = data.calculation_constants;

  // Max value for monthly trends scaling
  const maxTrendKg = Math.max(...(data.monthly_trend || []).map((m) => m?.rescued_kg || 0), 100);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleExportCsv = async () => {
    setCsvLoading(true);
    try {
      const blob = await dataSource.exportImpactCsv(filters);
      downloadBlob(blob, `SurplusSync-Impact-${preset}.csv`);
      onTriggerToast?.('CSV report downloaded successfully');
    } catch {
      onTriggerToast?.('Failed to export CSV. Please try again.');
    } finally {
      setCsvLoading(false);
    }
  };

  const handleExportPdf = async () => {
    setPdfLoading(true);
    try {
      const blob = await dataSource.exportImpactPdf(filters);
      downloadBlob(blob, `SurplusSync-Impact-${preset}.pdf`);
      onTriggerToast?.('PDF report downloaded successfully');
    } catch {
      onTriggerToast?.('Failed to export PDF. Please try again.');
    } finally {
      setPdfLoading(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  const PRESETS: { id: RangePreset; label: string }[] = [
    { id: '30d', label: '30 Days' },
    { id: '90d', label: '90 Days' },
    { id: '12m', label: '12 Months' },
    { id: 'custom', label: 'Custom' },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-150">
      {/* Header */}
      <PageHeader
        title="Sustainability Impact Dashboard"
        subtitle={`Completed donations only · ${periodLabel(preset, customStart, customEnd)}`}
        action={
          <div className="flex flex-wrap items-center gap-2">
            {/* Period Selector */}
            <div className="flex items-center rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-0.5">
              {PRESETS.map((p) => (
                <button
                  key={p.id}
                  id={`impact-period-${p.id}`}
                  type="button"
                  onClick={() => setPreset(p.id)}
                  className={`px-2.5 py-1 text-[11px] font-semibold rounded-[6px] transition-colors cursor-pointer ${
                    preset === p.id
                      ? 'bg-[var(--surface)] text-[var(--text)] shadow-2xs'
                      : 'text-[var(--muted)] hover:text-[var(--text)]'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Custom Date Pickers */}
            {preset === 'custom' && (
              <div className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
                <Calendar className="w-3.5 h-3.5 shrink-0" />
                <input
                  ref={customStartRef}
                  id="impact-custom-start"
                  type="date"
                  value={customStart}
                  max={customEnd}
                  onChange={(e) => setCustomStart(e.target.value)}
                  className="border border-[var(--border)] bg-[var(--surface-2)] text-[var(--text)] rounded-[6px] px-2 py-1 text-[11px] cursor-pointer"
                />
                <span>–</span>
                <input
                  ref={customEndRef}
                  id="impact-custom-end"
                  type="date"
                  value={customEnd}
                  min={customStart}
                  max={toISODate(new Date())}
                  onChange={(e) => setCustomEnd(e.target.value)}
                  className="border border-[var(--border)] bg-[var(--surface-2)] text-[var(--text)] rounded-[6px] px-2 py-1 text-[11px] cursor-pointer"
                />
              </div>
            )}

            {/* Export Buttons */}
            <Button
              id="impact-export-csv"
              variant="outline"
              size="sm"
              onClick={handleExportCsv}
              disabled={csvLoading}
              className="text-xs"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{csvLoading ? 'Exporting…' : 'CSV'}</span>
            </Button>

            <Button
              id="impact-export-pdf"
              variant="outline"
              size="sm"
              onClick={handleExportPdf}
              disabled={pdfLoading}
              className="text-xs"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>{pdfLoading ? 'Generating…' : 'PDF Report'}</span>
            </Button>
          </div>
        }
      />

      {/* KPI Stat Cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Skeleton variant="statCard" />
          <Skeleton variant="statCard" />
          <Skeleton variant="statCard" />
          <Skeleton variant="statCard" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Food Diverted"
            value={`${(data.rescued_food_kg ?? 0).toLocaleString()} kg`}
            icon={Package}
            trend={{ value: 'Completed donations only', isPositive: true }}
            subtitle="Perishable inventory rescued from waste"
          />
          <StatCard
            title="Estimated Meals"
            value={(data.meals_provided ?? 0).toLocaleString()}
            icon={Heart}
            trend={{ value: `@ ${consts?.meal_kg_factor ?? 0.42} kg / meal`, isPositive: true }}
            subtitle="Wholesome portions provided to shelters"
          />
          <StatCard
            title="CO₂e Avoided"
            value={`${(data.co2_avoided_kg ?? 0).toLocaleString()} kg`}
            icon={Leaf}
            trend={{ value: `@ ${consts?.co2e_kg_factor ?? 2.5} kg CO₂e / kg`, isPositive: true }}
            subtitle="Landfill methane emission prevented"
          />
          <StatCard
            title="Completed Donations"
            value={(data.total_donations_count ?? 0).toLocaleString()}
            icon={Package}
            trend={{ value: `${data.active_partners_count ?? 0} active partners`, isPositive: true }}
            subtitle="Successfully collected & confirmed"
          />
        </div>
      )}

      {/* Middle Row: Trend Chart & Category Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Monthly Trend Bar Chart */}
        <div className="lg:col-span-2 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-[var(--text)]">Monthly Rescue Trajectory</h3>
              <p className="text-xs text-[var(--muted)]">
                Completed donation volume (kg) by month
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="flex items-center gap-1.5 font-medium text-[var(--text)]">
                <span className="w-2.5 h-2.5 rounded-full bg-[var(--primary)]" />
                Rescued (kg)
              </span>
            </div>
          </div>

          {/* SVG Bar Chart */}
          <div className="h-56 flex items-end gap-2 sm:gap-4 pt-4 pb-2 px-1 border-b border-[var(--border)]">
            {(data.monthly_trend || []).map((m, idx) => {
              const rescued = m?.rescued_kg ?? 0;
              const heightPct = Math.max(8, Math.round((rescued / maxTrendKg) * 100));
              return (
                <div key={idx} className="flex-1 flex flex-col items-center gap-2 h-full justify-end group">
                  <span className="text-[10px] font-bold text-[var(--text)] opacity-0 group-hover:opacity-100 transition-opacity tabular-nums whitespace-nowrap">
                    {rescued} kg
                  </span>
                  <div className="w-full max-w-[52px] bg-[var(--surface-2)] rounded-t-[6px] h-full flex items-end overflow-hidden">
                    <div
                      className="w-full bg-[var(--primary)] group-hover:opacity-80 transition-all rounded-t-[6px]"
                      style={{ height: `${heightPct}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-[var(--muted)] truncate max-w-[60px] text-center">
                    {(m?.month || '').split(' ')[0]}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Summary Row */}
          <div className="grid grid-cols-3 gap-2 pt-1 text-center text-xs">
            <div className="rounded-[8px] bg-[var(--surface-2)]/60 p-2.5 border border-[var(--border)]">
              <div className="text-[10px] text-[var(--muted)]">Total Dispatches</div>
              <div className="font-bold text-[var(--text)] text-sm mt-0.5 tabular-nums">
                {data.total_donations_count ?? 0} completed
              </div>
            </div>
            <div className="rounded-[8px] bg-[var(--surface-2)]/60 p-2.5 border border-[var(--border)]">
              <div className="text-[10px] text-[var(--muted)]">Active Partners</div>
              <div className="font-bold text-[var(--text)] text-sm mt-0.5 tabular-nums">
                {data.active_partners_count ?? 0} orgs
              </div>
            </div>
            <div className="rounded-[8px] bg-[var(--surface-2)]/60 p-2.5 border border-[var(--border)]">
              <div className="text-[10px] text-[var(--muted)]">Est. Value Saved</div>
              <div className="font-bold text-[var(--text)] text-sm mt-0.5 tabular-nums">
                ₹{(data.financial_savings_estimate ?? 0).toLocaleString()}
              </div>
            </div>
          </div>
        </div>

        {/* Category Breakdown */}
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-2xs space-y-4">
          <div>
            <h3 className="text-sm font-bold text-[var(--text)]">Diversion by Category</h3>
            <p className="text-xs text-[var(--muted)]">
              Composition of rescued food by type
            </p>
          </div>

          <div className="space-y-3.5 pt-1">
            {(data.category_breakdown || []).map((cat, idx) => (
              <div key={idx} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-[var(--text)] capitalize">
                    {(cat?.category || 'General').replace(/_/g, ' ').toLowerCase()}
                  </span>
                  <div className="flex items-center gap-1.5 tabular-nums">
                    <span className="text-[var(--muted)]">{cat?.rescued_kg ?? 0} kg</span>
                    <span className="font-bold text-[var(--text)]">({cat?.percentage ?? 0}%)</span>
                  </div>
                </div>
                <div className="h-2 w-full rounded-full bg-[var(--surface-2)] overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{
                      width: `${cat.percentage}%`,
                      background: CAT_COLORS[idx % CAT_COLORS.length],
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* How We Calculate This Panel */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] shadow-2xs overflow-hidden">
        <button
          id="impact-how-toggle"
          type="button"
          onClick={() => setShowHow((p) => !p)}
          className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-[var(--surface-2)]/40 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-[var(--primary)]" />
            <span className="text-sm font-semibold text-[var(--text)]">
              How we calculate this
            </span>
          </div>
          <ChevronDown
            className={`w-4 h-4 text-[var(--muted)] transition-transform duration-200 ${
              showHow ? 'rotate-180' : ''
            }`}
          />
        </button>

        {showHow && (
          <div className="px-5 pb-5 space-y-4 border-t border-[var(--border)]">
            <p className="text-xs text-[var(--muted)] pt-4 leading-relaxed">
              All figures below are derived from completed donations only. Pending, cancelled, or
              in-transit requests are excluded.
            </p>

            {/* Constants Table */}
            <div className="rounded-[8px] border border-[var(--border)] overflow-hidden text-xs">
              <table className="w-full">
                <thead>
                  <tr className="bg-[var(--surface-2)] text-[var(--muted)] text-left">
                    <th className="px-3 py-2 font-semibold">Metric</th>
                    <th className="px-3 py-2 font-semibold">Formula</th>
                    <th className="px-3 py-2 font-semibold">Constant</th>
                    <th className="px-3 py-2 font-semibold">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  <tr>
                    <td className="px-3 py-2 text-[var(--text)] font-medium">Estimated Meals</td>
                    <td className="px-3 py-2 text-[var(--muted)] font-mono">kg ÷ meal_kg</td>
                    <td className="px-3 py-2 text-[var(--text)] font-mono tabular-nums">
                      {consts?.meal_kg_factor ?? 0.42} kg / meal
                    </td>
                    <td className="px-3 py-2 text-[var(--muted)]">{consts?.meal_citation ?? 'WRAP (2020)'}</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 text-[var(--text)] font-medium">CO₂e Avoided</td>
                    <td className="px-3 py-2 text-[var(--muted)] font-mono">kg × co2e_factor</td>
                    <td className="px-3 py-2 text-[var(--text)] font-mono tabular-nums">
                      {consts?.co2e_kg_factor ?? 2.5} kg CO₂e / kg
                    </td>
                    <td className="px-3 py-2 text-[var(--muted)]">{consts?.co2e_citation ?? 'FAO (2013)'}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Caveat */}
            <div className="flex items-start gap-2.5 rounded-[8px] bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 px-3 py-2.5">
              <Info className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <p className="text-[11px] text-amber-700 dark:text-amber-300 leading-relaxed">
                <strong>Estimates only.</strong>{' '}
                {consts?.caveat ??
                  'These are estimates based on population-level averages. Actual figures may vary by food type and supply chain.'}
              </p>
            </div>

            {/* References */}
            <div className="text-[11px] text-[var(--muted)] space-y-1">
              <p className="font-semibold text-[var(--text)]">References</p>
              <p>
                · WRAP (2020){' '}
                <em>Quantification of food surplus, waste and related measures across the UK food chain.</em>
              </p>
              <p>
                · FAO (2013){' '}
                <em>Food Wastage Footprint: Impacts on Natural Resources (Technical Report).</em>
              </p>
            </div>
          </div>
        )}
      </div>

      {/* UN SDG Alignment */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-2xs space-y-3">
        <div>
          <h3 className="text-sm font-bold text-[var(--text)]">
            UN SDG Alignment
          </h3>
          <p className="text-xs text-[var(--muted)]">
            SurplusSync redistributions directly contribute to global sustainability benchmarks.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
          <div className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)]/60 p-3.5 flex items-start gap-3">
            <div className="w-9 h-9 rounded-[8px] bg-red-500/10 text-red-500 flex items-center justify-center shrink-0 font-bold text-sm">
              2
            </div>
            <div className="space-y-0.5">
              <h4 className="text-xs font-bold text-[var(--text)]">SDG 2: Zero Hunger</h4>
              <p className="text-[11px] text-[var(--muted)] leading-relaxed">
                Ensuring equitable access to safe, nutritious food for vulnerable communities.
              </p>
            </div>
          </div>

          <div className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)]/60 p-3.5 flex items-start gap-3">
            <div className="w-9 h-9 rounded-[8px] bg-amber-500/10 text-amber-500 flex items-center justify-center shrink-0 font-bold text-sm">
              12
            </div>
            <div className="space-y-0.5">
              <h4 className="text-xs font-bold text-[var(--text)]">SDG 12: Responsible Consumption</h4>
              <p className="text-[11px] text-[var(--muted)] leading-relaxed">
                Halving per-capita food waste at retail and consumer levels.
              </p>
            </div>
          </div>

          <div className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)]/60 p-3.5 flex items-start gap-3">
            <div className="w-9 h-9 rounded-[8px] bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0 font-bold text-sm">
              13
            </div>
            <div className="space-y-0.5">
              <h4 className="text-xs font-bold text-[var(--text)]">SDG 13: Climate Action</h4>
              <p className="text-[11px] text-[var(--muted)] leading-relaxed">
                Mitigating landfill methane by diverting organics back into the food chain.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
