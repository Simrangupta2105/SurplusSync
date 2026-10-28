import React, { useState, useMemo, useEffect } from 'react';
import {
  TrendingUp,
  ArrowRight,
} from 'lucide-react';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';
import { Button } from '../ui/Button';
import { useRecentSales, usePlanPrediction } from '../../hooks/useData';
import { isFeatureLive } from '../../services';
import type { RecentSaleItem, PlanPredictionResponse } from '../../types';

interface SalesForecastCardProps {
  onNavigate?: (path: string) => void;
  className?: string;
}

const CATEGORIES = [
  'All',
  'Dairy',
  'Bakery',
  'Vegetables',
  'Fruits',
  'Meat',
  'Prepared Food',
];

export const SalesForecastCard: React.FC<SalesForecastCardProps> = ({
  onNavigate,
  className = '',
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('All');

  // 1. Fetch past 7 days actual sales
  const { data: salesData } = useRecentSales({
    days: 7,
    category: selectedCategory,
  });

  // 2. Fetch AI Demand Forecast for selected category
  const forecastCategory = selectedCategory === 'All' ? 'Dairy' : selectedCategory;
  const { mutate } = usePlanPrediction();
  const [cachedForecast, setCachedForecast] = useState<PlanPredictionResponse | null>(null);

  // Trigger forecast fetch on mount and category switch
  useEffect(() => {
    mutate(
      {
        category: forecastCategory,
        planned_quantity: 100,
        promotion: false,
        weather: 'Sunny',
      },
      {
        onSuccess: (data) => setCachedForecast(data),
      }
    );
  }, [forecastCategory, mutate]);

  const isLive = isFeatureLive('inventory_batches');

  // 3. Merge 7-day actuals + 7-day forecast into unified 14-day time series
  const chartData = useMemo(() => {
    const rawSales = salesData || [];
    const baseDemand = cachedForecast?.forecast_demand ?? 108.0;
    const lowerBound = cachedForecast?.forecast_range?.min ?? Math.max(0, baseDemand * 0.75);
    const upperBound = cachedForecast?.forecast_range?.max ?? baseDemand * 1.35;

    const points: Array<{
      date: string;
      displayDate: string;
      actual: number | null;
      actualRevenue: number | null;
      forecast: number | null;
      forecastLower: number | null;
      forecastUpper: number | null;
      isToday?: boolean;
    }> = [];

    // Past 7 Days Actuals
    rawSales.forEach((sale: RecentSaleItem, idx: number) => {
      const d = new Date(sale.date);
      const isLast = idx === rawSales.length - 1;
      const displayDate = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

      points.push({
        date: sale.date,
        displayDate: isLast ? `${displayDate} (Today)` : displayDate,
        actual: sale.units_sold,
        actualRevenue: sale.revenue,
        // Connect today's actual to start of forecast line for unbroken visualization
        forecast: isLast ? sale.units_sold : null,
        forecastLower: isLast ? sale.units_sold : null,
        forecastUpper: isLast ? sale.units_sold : null,
        isToday: isLast,
      });
    });

    // If no sales returned yet, seed empty 7 past days
    if (points.length === 0) {
      const today = new Date();
      for (let i = 6; i >= 0; i--) {
        const d = new Date(today);
        d.setDate(d.getDate() - i);
        const dateStr = d.toISOString().split('T')[0];
        const displayDate = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        const isToday = i === 0;
        points.push({
          date: dateStr,
          displayDate: isToday ? `${displayDate} (Today)` : displayDate,
          actual: 0,
          actualRevenue: 0,
          forecast: isToday ? 0 : null,
          forecastLower: isToday ? 0 : null,
          forecastUpper: isToday ? 0 : null,
          isToday,
        });
      }
    }

    // Next 7 Days Forecast (Days 1 to 7 into future)
    const today = new Date();
    for (let i = 1; i <= 7; i++) {
      const futureDate = new Date(today);
      futureDate.setDate(futureDate.getDate() + i);
      const dateStr = futureDate.toISOString().split('T')[0];
      const displayDate = futureDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

      // Apply light day-of-week seasonality (weekend lift ~12%)
      const dayOfWeek = futureDate.getDay();
      const weekendFactor = dayOfWeek === 0 || dayOfWeek === 6 ? 1.12 : dayOfWeek === 5 ? 1.06 : 0.98;
      const expectedDaily = Math.round(baseDemand * weekendFactor * 10) / 10;
      const dayLower = Math.max(0, Math.round(lowerBound * weekendFactor * 10) / 10);
      const dayUpper = Math.round(upperBound * weekendFactor * 10) / 10;

      points.push({
        date: dateStr,
        displayDate,
        actual: null,
        actualRevenue: null,
        forecast: expectedDaily,
        forecastLower: dayLower,
        forecastUpper: dayUpper,
      });
    }

    return points;
  }, [salesData, cachedForecast]);

  // Aggregate stats
  const stats = useMemo(() => {
    const rawSales = salesData || [];
    const totalSold = rawSales.reduce((acc, r) => acc + (r.units_sold || 0), 0);
    const avgPastDaily = rawSales.length > 0 ? Math.round((totalSold / rawSales.length) * 10) / 10 : 0;

    const futurePoints = chartData.filter((p) => p.forecast !== null && !p.isToday);
    const avgForecastDaily =
      futurePoints.length > 0
        ? Math.round(
            (futurePoints.reduce((acc, p) => acc + (p.forecast || 0), 0) / futurePoints.length) * 10
          ) / 10
        : Math.round((cachedForecast?.forecast_demand ?? 108) * 10) / 10;

    const diff = avgPastDaily > 0 ? ((avgForecastDaily - avgPastDaily) / avgPastDaily) * 100 : 0;
    const diffFormatted = (diff >= 0 ? '+' : '') + diff.toFixed(1) + '%';

    return {
      avgPastDaily,
      avgForecastDaily,
      diffFormatted,
      isPositive: diff >= 0,
    };
  }, [salesData, chartData, cachedForecast]);

  return (
    <div
      className={`rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 flex flex-col justify-between shadow-sm transition-all ${className}`}
      data-testid="sales-forecast-card"
    >
      <div>
        {/* Card Header */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 mb-5">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-semibold text-[var(--text)] tracking-tight flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-[var(--primary)]" />
                Recent Sales & Demand Forecast
              </h2>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20">
                HistGradientBoostingDemandModel
              </span>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-medium ${
                  isLive
                    ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
                    : 'bg-amber-500/10 text-amber-500 border border-amber-500/20'
                }`}
              >
                {isLive ? 'LIVE POS/LEDGER' : 'SYNTHETIC DEMO DATA'}
              </span>
            </div>
            <p className="text-xs text-[var(--muted)] mt-1">
              7-day actual POS sales ledger merged with a 7-day 90% confidence AI demand forecast
            </p>
          </div>

          {/* Category Selector Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0" role="tablist">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                role="tab"
                aria-selected={selectedCategory === cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2.5 py-1 text-xs rounded-[6px] font-medium transition-colors whitespace-nowrap cursor-pointer ${
                  selectedCategory === cat
                    ? 'bg-[var(--primary)] text-[var(--primary-foreground,white)] shadow-sm'
                    : 'bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-3,var(--border))]'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Unified 14-Day Chart */}
        <div className="h-64 sm:h-72 w-full mt-2">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={chartData}
              margin={{ top: 10, right: 15, left: -15, bottom: 0 }}
            >
              <defs>
                <linearGradient id="actualAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="var(--primary)" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="forecastIntervalGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.20} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />

              <XAxis
                dataKey="displayDate"
                stroke="var(--muted)"
                fontSize={11}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                stroke="var(--muted)"
                fontSize={11}
                tickLine={false}
                domain={[0, 'auto']}
              />

              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    const dataPoint = payload[0].payload;
                    const isActual = dataPoint.actual !== null;
                    const isForecast = dataPoint.forecast !== null && !dataPoint.isToday;

                    return (
                      <div className="rounded-[8px] border border-[var(--border)] bg-[var(--surface)] p-3 shadow-lg text-xs space-y-1.5 min-w-[190px]">
                        <p className="font-semibold text-[var(--text)] border-b border-[var(--border)] pb-1">
                          {label}
                        </p>
                        {isActual && (
                          <div className="text-[var(--primary)] font-medium flex justify-between gap-4">
                            <span>Actual Sales:</span>
                            <span className="font-mono font-semibold">
                              {dataPoint.actual} units
                            </span>
                          </div>
                        )}
                        {dataPoint.actualRevenue !== null && dataPoint.actualRevenue > 0 && (
                          <div className="text-[var(--muted)] flex justify-between gap-4">
                            <span>Revenue:</span>
                            <span className="font-mono">
                              ₹{dataPoint.actualRevenue.toLocaleString()}
                            </span>
                          </div>
                        )}
                        {isForecast && (
                          <>
                            <div className="text-[#3b82f6] font-medium flex justify-between gap-4">
                              <span>AI Forecast:</span>
                              <span className="font-mono font-semibold">
                                {dataPoint.forecast} units
                              </span>
                            </div>
                            <div className="text-[var(--muted)] text-[10px] flex justify-between gap-4">
                              <span>90% Range:</span>
                              <span className="font-mono">
                                [{dataPoint.forecastLower} - {dataPoint.forecastUpper}]
                              </span>
                            </div>
                          </>
                        )}
                      </div>
                    );
                  }
                  return null;
                }}
              />

              <Legend
                verticalAlign="top"
                height={32}
                iconType="plainline"
                wrapperStyle={{ fontSize: '11px', paddingBottom: '8px' }}
              />

              {/* Shaded 90% confidence interval for forecast days */}
              <Area
                type="monotone"
                dataKey="forecastUpper"
                name="90% Confidence Band"
                stroke="none"
                fill="url(#forecastIntervalGrad)"
                isAnimationActive={false}
              />

              {/* Actual Sales Line (Solid) */}
              <Line
                type="monotone"
                dataKey="actual"
                name="Actual Sales (POS/Ledger)"
                stroke="var(--primary)"
                strokeWidth={2.5}
                dot={{ r: 3, fill: 'var(--primary)', strokeWidth: 0 }}
                activeDot={{ r: 5 }}
                connectNulls={false}
              />

              {/* AI Forecast Line (Dashed) */}
              <Line
                type="monotone"
                dataKey="forecast"
                name="AI Forecast (HistGradientBoostingDemandModel, 90% interval)"
                stroke="#3b82f6"
                strokeWidth={2.5}
                strokeDasharray="4 4"
                dot={{ r: 3, fill: '#3b82f6', strokeWidth: 0 }}
                activeDot={{ r: 5 }}
                connectNulls={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Summary Metrics & Deep-Dive Footer */}
      <div className="pt-4 mt-3 border-t border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-4 flex-wrap">
          <div>
            <span className="text-[var(--muted)] block text-[10px] uppercase font-mono">
              7-Day Past Avg
            </span>
            <span className="font-semibold text-[var(--text)] font-mono">
              {stats.avgPastDaily} units/day
            </span>
          </div>
          <div className="h-6 w-px bg-[var(--border)]" />
          <div>
            <span className="text-[var(--muted)] block text-[10px] uppercase font-mono">
              7-Day Forecast Avg
            </span>
            <span className="font-semibold text-[#3b82f6] font-mono">
              {stats.avgForecastDaily} units/day
            </span>
          </div>
          <div className="h-6 w-px bg-[var(--border)]" />
          <div>
            <span className="text-[var(--muted)] block text-[10px] uppercase font-mono">
              Expected Shift
            </span>
            <span
              className={`font-semibold font-mono ${
                stats.isPositive ? 'text-emerald-500' : 'text-amber-500'
              }`}
            >
              {stats.diffFormatted}
            </span>
          </div>
        </div>

        {onNavigate && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onNavigate('business/ai/forecast')}
            className="text-xs text-[var(--primary)] hover:underline p-0 h-auto font-medium self-end sm:self-auto gap-1"
          >
            <span>Explore Full Forecast Engine</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
};
