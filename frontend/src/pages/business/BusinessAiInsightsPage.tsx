import React from 'react';
import {
  BarChart3,
  AlertTriangle,
  Info,
  TrendingUp,
  Tag,
  CloudSun,
  ShieldAlert,
  Database,
  RefreshCw,
  FileText,
  Percent,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';
import { PageHeader } from '../../components/ui/PageHeader';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { useDatasetInsights } from '../../hooks/useData';

export const BusinessAiInsightsPage: React.FC = () => {
  const { data: insights, isLoading, isError, error, refetch } = useDatasetInsights();

  if (isLoading) {
    return (
      <div className="w-full max-w-6xl mx-auto space-y-6 pb-12 animate-in fade-in duration-200">
        <PageHeader
          title="Waste Insights"
          description="Empirical patterns and commercial benchmark facts derived from the cross-sectional dataset."
        />
        <div className="h-14 rounded-[12px] bg-[var(--surface-2)] animate-pulse" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Skeleton variant="statCard" />
          <Skeleton variant="statCard" />
          <Skeleton variant="statCard" />
          <Skeleton variant="statCard" />
        </div>
        <div className="h-80 rounded-[12px] bg-[var(--surface)] border border-[var(--border)] animate-pulse" />
      </div>
    );
  }

  if (isError || !insights) {
    return (
      <div className="w-full max-w-6xl mx-auto space-y-6 pb-12">
        <PageHeader
          title="Waste Insights"
          description="Empirical patterns and commercial benchmark facts derived from the cross-sectional dataset."
        />
        <div
          role="alert"
          className="rounded-[12px] border border-red-500/30 bg-red-500/10 p-6 text-center space-y-3"
        >
          <ShieldAlert className="w-8 h-8 text-red-500 mx-auto" />
          <h3 className="text-base font-semibold text-red-600 dark:text-red-400">
            Failed to Load Dataset Insights
          </h3>
          <p className="text-xs text-[var(--muted)] max-w-md mx-auto">
            {error instanceof Error
              ? error.message
              : 'Unable to communicate with the insights service.'}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="mt-2 text-xs cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  // Transform waste rate by category for Recharts
  const wasteRateChartData = Object.entries(insights.waste_rate_by_category || {}).map(
    ([category, rates]) => ({
      category,
      'Waste % of Remaining': rates.waste_pct_of_remaining,
      'Waste % of Purchase': rates.waste_pct_of_purchase,
    })
  );

  // Weather drivers data
  const weatherEntries = Object.entries(insights.demand_lift_weather || {});

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6 pb-12 animate-in fade-in duration-200">
      <PageHeader
        title="Waste Insights"
        description="Cross-sectional benchmark analytics across commercial foodservice and grocery retail operations."
        badge={
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20">
            <Database className="w-3.5 h-3.5" />
            Benchmark Model
          </span>
        }
      />

      {/* MANDATORY SYNTHETIC BENCHMARK DISCLOSURE BANNER */}
      <div
        role="region"
        aria-label="Benchmark Disclosure Notice"
        className="rounded-[12px] border border-blue-500/30 bg-blue-500/10 dark:bg-blue-950/30 p-4 sm:p-5 flex items-start gap-3.5 shadow-xs"
      >
        <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h2 className="text-sm font-semibold text-blue-700 dark:text-blue-300">
            Benchmark Dataset Disclosure
          </h2>
          <p className="text-xs text-blue-800/80 dark:text-blue-300/80 leading-relaxed">
            {insights.data_disclosure ||
              'Based on a benchmark dataset that appears synthetic. These are general patterns, not your own data.'}
          </p>
          <p className="text-[11px] text-blue-700/70 dark:text-blue-400/70">
            Source: <span className="font-semibold">{insights.source}</span>. Figures reflect
            cross-sectional commercial averages and should be used as industry reference points
            rather than individual tenant performance metrics.
          </p>
        </div>
      </div>

      {/* Benchmark KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Over-Purchasing Share */}
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-1 shadow-xs">
          <div className="flex items-center justify-between text-xs text-[var(--muted)]">
            <span>Over-Purchase Rate</span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-[var(--text)]">
            {insights.over_purchase_share?.share_of_orders_over_purchased_pct}%
          </div>
          <div className="text-[11px] text-[var(--muted)]">
            {insights.over_purchase_share?.total_excess_units?.toLocaleString()} excess units across{' '}
            {insights.data_card?.records?.toLocaleString()} records
          </div>
        </div>

        {/* Promotional Demand Lift */}
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-1 shadow-xs">
          <div className="flex items-center justify-between text-xs text-[var(--muted)]">
            <span>Promotion Lift</span>
            <Tag className="w-4 h-4 text-[var(--primary)]" />
          </div>
          <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
            +{insights.demand_lift_promotion?.percentage_lift}%
          </div>
          <div className="text-[11px] text-[var(--muted)]">
            {insights.demand_lift_promotion?.mean_demand_with_promo} vs{' '}
            {insights.demand_lift_promotion?.mean_demand_without_promo} mean daily units
          </div>
        </div>

        {/* Highest Waste Risk Category */}
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-1 shadow-xs">
          <div className="flex items-center justify-between text-xs text-[var(--muted)]">
            <span>Highest Waste Category</span>
            <TrendingUp className="w-4 h-4 text-red-500" />
          </div>
          <div className="text-2xl font-bold text-[var(--text)]">Prepared Food</div>
          <div className="text-[11px] text-red-500 font-medium">
            38.8% remaining inventory lost to spoilage
          </div>
        </div>

        {/* Total Sample Size */}
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-1 shadow-xs">
          <div className="flex items-center justify-between text-xs text-[var(--muted)]">
            <span>Benchmark Observations</span>
            <FileText className="w-4 h-4 text-[var(--primary)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--text)]">
            {insights.data_card?.records?.toLocaleString()}
          </div>
          <div className="text-[11px] text-[var(--muted)]">
            Across 4 business types &amp; 6 fresh food categories
          </div>
        </div>
      </div>

      {/* Chart: Waste Rate by Category */}
      <section
        aria-label="Waste Rate by Category"
        className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[var(--border)] pb-3">
          <div>
            <h3 className="text-base font-semibold text-[var(--text)] flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-[var(--primary)]" />
              Empirical Waste Rate by Food Category
            </h3>
            <p className="text-xs text-[var(--muted)]">
              Comparison between waste as a percentage of unsold remaining stock vs total initial order quantity.
            </p>
          </div>
        </div>

        <div className="h-72 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={wasteRateChartData}
              margin={{ top: 10, right: 10, left: -20, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
              <XAxis
                dataKey="category"
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                axisLine={{ stroke: 'var(--border)' }}
              />
              <YAxis
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                unit="%"
                axisLine={{ stroke: 'var(--border)' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                  fontSize: 12,
                  borderRadius: 8,
                }}
              />
              <Legend
                verticalAlign="top"
                align="right"
                wrapperStyle={{ paddingBottom: 10, fontSize: 12 }}
              />
              <Bar
                dataKey="Waste % of Remaining"
                fill="var(--color-danger, #ef4444)"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="Waste % of Purchase"
                fill="var(--primary, #059669)"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Table & Cards: Waste Reasons by Category */}
      <section
        aria-label="Waste Reasons Breakdown"
        className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-4"
      >
        <div className="border-b border-[var(--border)] pb-3">
          <h3 className="text-base font-semibold text-[var(--text)] flex items-center gap-2">
            <Percent className="w-4 h-4 text-[var(--primary)]" />
            Waste Reasons Distribution by Category (%)
          </h3>
          <p className="text-xs text-[var(--muted)]">
            Distribution of root causes reported across 8,000 observations. On mobile devices, this table transforms into individual cards.
          </p>
        </div>

        {/* Desktop Table View (Hidden on mobile < 640px) */}
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full text-xs text-left text-[var(--text)]">
            <thead className="bg-[var(--surface-2)] text-[var(--muted)] uppercase text-[10px] tracking-wider border-b border-[var(--border)]">
              <tr>
                <th className="py-2.5 px-3 font-semibold">Category</th>
                <th className="py-2.5 px-3 font-semibold text-right">No Waste</th>
                <th className="py-2.5 px-3 font-semibold text-right text-red-500">Expired</th>
                <th className="py-2.5 px-3 font-semibold text-right text-amber-500">Overproduction</th>
                <th className="py-2.5 px-3 font-semibold text-right">Low Demand</th>
                <th className="py-2.5 px-3 font-semibold text-right">Storage Issue</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {Object.entries(insights.waste_reasons_by_category || {}).map(
                ([catName, reasons]) => (
                  <tr key={catName} className="hover:bg-[var(--surface-2)]/50 transition-colors">
                    <td className="py-2.5 px-3 font-medium">{catName}</td>
                    <td className="py-2.5 px-3 text-right text-emerald-600 dark:text-emerald-400 font-medium">
                      {reasons['No Waste']?.toFixed(1) || '0.0'}%
                    </td>
                    <td className="py-2.5 px-3 text-right text-red-500 font-medium">
                      {reasons['Expired']?.toFixed(1) || '0.0'}%
                    </td>
                    <td className="py-2.5 px-3 text-right text-amber-500 font-medium">
                      {reasons['Overproduction']?.toFixed(1) || '0.0'}%
                    </td>
                    <td className="py-2.5 px-3 text-right text-[var(--muted)]">
                      {reasons['Low Demand']?.toFixed(1) || '0.0'}%
                    </td>
                    <td className="py-2.5 px-3 text-right text-[var(--muted)]">
                      {reasons['Storage Issue']?.toFixed(1) || '0.0'}%
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile Cards View (Visible only on mobile < 640px) */}
        <div className="sm:hidden space-y-3">
          {Object.entries(insights.waste_reasons_by_category || {}).map(
            ([catName, reasons]) => (
              <div
                key={catName}
                className="rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-3.5 space-y-2"
              >
                <div className="flex items-center justify-between border-b border-[var(--border)] pb-1.5">
                  <span className="font-bold text-xs text-[var(--text)]">{catName}</span>
                  <span className="text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
                    {reasons['No Waste']?.toFixed(1)}% clean
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-[var(--muted)]">Expired:</span>{' '}
                    <strong className="text-red-500">{reasons['Expired']?.toFixed(1)}%</strong>
                  </div>
                  <div>
                    <span className="text-[var(--muted)]">Overproduction:</span>{' '}
                    <strong className="text-amber-500">{reasons['Overproduction']?.toFixed(1)}%</strong>
                  </div>
                  <div>
                    <span className="text-[var(--muted)]">Low Demand:</span>{' '}
                    <span>{reasons['Low Demand']?.toFixed(1)}%</span>
                  </div>
                  <div>
                    <span className="text-[var(--muted)]">Storage Issue:</span>{' '}
                    <span>{reasons['Storage Issue']?.toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            )
          )}
        </div>
      </section>

      {/* Environmental & Operational Drivers Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Weather Demand Multipliers */}
        <section
          aria-label="Weather Multipliers"
          className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4 shadow-xs"
        >
          <div className="border-b border-[var(--border)] pb-3">
            <h3 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2">
              <CloudSun className="w-4 h-4 text-[var(--primary)]" />
              Weather Condition Demand Multipliers
            </h3>
            <p className="text-xs text-[var(--muted)]">
              Multiplicative adjustments applied to baseline customer demand.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {weatherEntries.map(([condition, stats]) => (
              <div
                key={condition}
                className="rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-3 space-y-1"
              >
                <div className="flex items-center justify-between text-xs font-semibold text-[var(--text)]">
                  <span>{condition}</span>
                  <span
                    className={
                      stats.relative_effect.startsWith('+')
                        ? 'text-emerald-500 font-bold'
                        : stats.relative_effect.startsWith('-')
                        ? 'text-red-500 font-bold'
                        : 'text-[var(--muted)] font-medium'
                    }
                  >
                    {stats.relative_effect}
                  </span>
                </div>
                <div className="text-xs text-[var(--muted)]">
                  Multiplier: <strong className="text-[var(--text)]">{stats.multiplier}x</strong>
                </div>
                <div className="text-[10px] text-[var(--muted)]">
                  Mean: {stats.mean_demand} units/day
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Benchmark Data Card */}
        <section
          aria-label="Dataset Card & Limitations"
          className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4 shadow-xs"
        >
          <div className="border-b border-[var(--border)] pb-3">
            <h3 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2">
              <Database className="w-4 h-4 text-[var(--primary)]" />
              Benchmark Dataset Data Card
            </h3>
            <p className="text-xs text-[var(--muted)]">
              Model provenance, evaluation period, and known constraints.
            </p>
          </div>

          <div className="space-y-2.5 text-xs text-[var(--muted)] leading-relaxed">
            <div>
              <span className="font-semibold text-[var(--text)]">Title: </span>
              {insights.data_card?.title}
            </div>
            <div>
              <span className="font-semibold text-[var(--text)]">Scope: </span>
              {insights.data_card?.scope}
            </div>
            <div>
              <span className="font-semibold text-[var(--text)]">Observation Period: </span>
              {insights.data_card?.period}
            </div>
            <div>
              <span className="font-semibold text-[var(--text)]">Provenance: </span>
              {insights.data_card?.provenance_placeholder}
            </div>
            <div>
              <span className="font-semibold text-[var(--text)]">Accounting Invariants: </span>
              {insights.data_card?.accounting_invariants}
            </div>
            <div className="text-[11px] text-[var(--muted)] pt-1 italic">
              <strong>Limitations: </strong>
              {insights.data_card?.limitations}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
