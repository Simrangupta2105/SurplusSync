import React, { useState } from 'react';
import {
  Sparkles,
  Calculator,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
  TrendingUp,
  CloudSun,
  Tag,
  Calendar,
  Layers,
  ChevronDown,
  ChevronUp,
  Info,
  ShieldAlert,
} from 'lucide-react';
import { PageHeader } from '../../components/ui/PageHeader';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { usePlanPrediction } from '../../hooks/useData';
import type { PlanPredictionRequest } from '../../types';

interface BusinessPurchasePlannerPageProps {
  onNavigate?: (path: string) => void;
  onTriggerToast?: (msg: string) => void;
}

const SUPPORTED_CATEGORIES = [
  { value: 'Bakery', label: 'Bakery (Breads, Pastries)' },
  { value: 'Dairy', label: 'Dairy (Milk, Cheese, Yogurt)' },
  { value: 'Fruits', label: 'Fruits (Fresh Produce)' },
  { value: 'Meat', label: 'Meat & Poultry' },
  { value: 'Prepared Food', label: 'Prepared & Cooked Meals' },
  { value: 'Vegetables', label: 'Vegetables & Fresh Greens' },
];

const WEATHER_OPTIONS: Array<'Sunny' | 'Rainy' | 'Cloudy' | 'Hot'> = [
  'Sunny',
  'Rainy',
  'Cloudy',
  'Hot',
];

export const BusinessPurchasePlannerPage: React.FC<BusinessPurchasePlannerPageProps> = ({
  onTriggerToast,
}) => {
  // Form inputs
  const [category, setCategory] = useState<string>('Bakery');
  const [plannedQuantity, setPlannedQuantity] = useState<string>('120');
  const [promotion, setPromotion] = useState<boolean>(false);
  const [weather, setWeather] = useState<'Sunny' | 'Rainy' | 'Cloudy' | 'Hot'>('Sunny');
  const [date, setDate] = useState<string>(() => new Date().toISOString().split('T')[0]);
  const [showHowCalculated, setShowHowCalculated] = useState<boolean>(false);

  const planMutation = usePlanPrediction();

  const handleCalculate = (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    const qty = parseFloat(plannedQuantity);
    if (isNaN(qty) || qty <= 0) {
      return;
    }

    const payload: PlanPredictionRequest = {
      category,
      planned_quantity: qty,
      promotion,
      weather,
      date: date || undefined,
    };

    planMutation.mutate(payload, {
      onSuccess: (data) => {
        if (data.status !== 'unavailable' && onTriggerToast) {
          onTriggerToast('Purchase plan evaluated successfully.');
        }
      },
    });
  };

  const qtyNumber = parseFloat(plannedQuantity);
  const isFormValid = !isNaN(qtyNumber) && qtyNumber > 0;

  const predictionResult = planMutation.data;
  const isUnavailable =
    predictionResult?.status === 'unavailable' ||
    (planMutation.error as { response?: { status?: number; data?: { status?: string; detail?: string } } })?.response?.status === 503 ||
    (planMutation.error as { response?: { status?: number; data?: { status?: string; detail?: string } } })?.response?.data?.status === 'unavailable';

  const unavailableMessage =
    (predictionResult?.status === 'unavailable' && predictionResult.detail) ||
    (planMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
    'Predictions temporarily unavailable. The machine learning service is offline or starting up. Please try again shortly.';

  const isGeneralError = Boolean(planMutation.error && !isUnavailable);
  const errorMessage =
    (planMutation.error as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail ||
    (planMutation.error as Error)?.message ||
    'Failed to evaluate purchase plan. Please try again.';

  // Waste risk color mapping
  const getRiskBadgeStyles = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'low':
        return {
          container:
            'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
          dot: 'bg-emerald-500',
        };
      case 'medium':
        return {
          container:
            'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30',
          dot: 'bg-amber-500',
        };
      case 'high':
        return {
          container: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30',
          dot: 'bg-red-500',
        };
      default:
        return {
          container: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/30',
          dot: 'bg-gray-500',
        };
    }
  };

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6 pb-12 animate-in fade-in duration-200">
      <PageHeader
        title="Purchase Planner"
        description="Evaluate tentative purchasing orders using Poisson demand forecasting and LightGBM waste-risk classification."
        badge={
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20">
            <Sparkles className="w-3.5 h-3.5" />
            AI-Assisted
          </span>
        }
      />

      {/* Service Unavailable Banner */}
      {isUnavailable && (
        <div
          role="alert"
          aria-live="polite"
          className="rounded-[12px] border border-amber-500/30 bg-amber-500/10 p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <h2 className="text-sm font-semibold text-amber-600 dark:text-amber-400">
                Machine Learning Service Unavailable
              </h2>
              <p className="text-xs text-[var(--muted)] mt-1">
                {unavailableMessage}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleCalculate()}
            className="shrink-0 border-amber-500/30 hover:bg-amber-500/10 text-amber-600 dark:text-amber-400 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Retry Connection
          </Button>
        </div>
      )}

      {/* General Error Banner */}
      {isGeneralError && (
        <div
          role="alert"
          className="rounded-[12px] border border-red-500/30 bg-red-500/10 p-4 flex items-start justify-between gap-3"
        >
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-600 dark:text-red-400">
                {errorMessage}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleCalculate()}
            className="shrink-0 text-xs"
          >
            <RefreshCw className="w-3 h-3 mr-1" />
            Retry
          </Button>
        </div>
      )}

      {/* Main Grid: Form Left, Results Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Form Panel */}
        <section
          aria-label="Purchase Order Parameters"
          className="lg:col-span-5 rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-5"
        >
          <div className="flex items-center gap-2 border-b border-[var(--border)] pb-3">
            <Calculator className="w-4 h-4 text-[var(--primary)]" />
            <h2 className="text-base font-semibold text-[var(--text)]">Plan Parameters</h2>
          </div>

          <form onSubmit={handleCalculate} className="space-y-4">
            {/* Category Select */}
            <div className="space-y-1.5">
              <label
                htmlFor="plan-category"
                className="block text-xs font-medium text-[var(--text)]"
              >
                Food Category <span className="text-red-500">*</span>
              </label>
              <select
                id="plan-category"
                aria-label="Food Category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)] transition-colors"
              >
                {SUPPORTED_CATEGORIES.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Planned Quantity */}
            <div className="space-y-1.5">
              <label
                htmlFor="planned-quantity"
                className="block text-xs font-medium text-[var(--text)]"
              >
                Planned Order Quantity (units) <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  id="planned-quantity"
                  aria-label="Planned Order Quantity"
                  type="number"
                  min="1"
                  step="1"
                  required
                  placeholder="e.g. 100"
                  value={plannedQuantity}
                  onChange={(e) => setPlannedQuantity(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)] transition-colors"
                />
                <span className="absolute right-3 top-2.5 text-xs text-[var(--muted)] pointer-events-none">
                  units
                </span>
              </div>
              {!isFormValid && plannedQuantity !== '' && (
                <p className="text-[11px] text-red-500">
                  Quantity must be greater than zero.
                </p>
              )}
            </div>

            {/* Promotion Toggle */}
            <div className="pt-1">
              <label
                htmlFor="promo-toggle"
                className="flex items-center justify-between p-3 rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] cursor-pointer hover:border-[var(--primary)]/50 transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <Tag className="w-4 h-4 text-[var(--primary)]" />
                  <div>
                    <span className="block text-xs font-semibold text-[var(--text)]">
                      Active Promotion / Discount
                    </span>
                    <span className="block text-[11px] text-[var(--muted)]">
                      Empirical lift: +33% consumer demand
                    </span>
                  </div>
                </div>
                <input
                  id="promo-toggle"
                  type="checkbox"
                  checked={promotion}
                  onChange={(e) => setPromotion(e.target.checked)}
                  className="w-4 h-4 text-[var(--primary)] rounded border-[var(--border)] focus:ring-[var(--primary)] cursor-pointer"
                />
              </label>
            </div>

            {/* Weather Select */}
            <div className="space-y-1.5">
              <label
                htmlFor="plan-weather"
                className="block text-xs font-medium text-[var(--text)] flex items-center gap-1.5"
              >
                <CloudSun className="w-3.5 h-3.5 text-[var(--primary)]" />
                Expected Weather
              </label>
              <select
                id="plan-weather"
                aria-label="Expected Weather"
                value={weather}
                onChange={(e) =>
                  setWeather(e.target.value as 'Sunny' | 'Rainy' | 'Cloudy' | 'Hot')
                }
                className="w-full px-3 py-2 text-sm rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)] transition-colors"
              >
                {WEATHER_OPTIONS.map((w) => (
                  <option key={w} value={w}>
                    {w} {w === 'Hot' ? '(+3.9% lift)' : w === 'Rainy' ? '(-33.2% drop)' : w === 'Cloudy' ? '(-10.8% drop)' : '(Baseline)'}
                  </option>
                ))}
              </select>
            </div>

            {/* Target Date */}
            <div className="space-y-1.5">
              <label
                htmlFor="plan-date"
                className="block text-xs font-medium text-[var(--text)] flex items-center gap-1.5"
              >
                <Calendar className="w-3.5 h-3.5 text-[var(--primary)]" />
                Calendar Date (Optional)
              </label>
              <input
                id="plan-date"
                aria-label="Calendar Date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)] transition-colors"
              />
            </div>

            {/* Calculate Button */}
            <div className="pt-2">
              <Button
                type="submit"
                onClick={(e) => handleCalculate(e)}
                disabled={!isFormValid || planMutation.isPending}
                className="w-full py-2.5 text-sm font-semibold flex items-center justify-center gap-2 cursor-pointer shadow-xs"
              >
                {planMutation.isPending ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Evaluating Plan...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Calculate Plan
                  </>
                )}
              </Button>
            </div>
          </form>
        </section>

        {/* Results Panel */}
        <div className="lg:col-span-7 space-y-6">
          {planMutation.isPending ? (
            /* Skeleton Loading State */
            <div
              aria-label="Calculating forecast"
              className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-6 space-y-6 animate-pulse"
            >
              <div className="h-4 w-32 bg-[var(--surface-2)] rounded-[6px]" />
              <div className="grid grid-cols-2 gap-4">
                <Skeleton variant="statCard" />
                <Skeleton variant="statCard" />
              </div>
              <div className="h-24 bg-[var(--surface-2)] rounded-[8px]" />
              <div className="h-16 bg-[var(--surface-2)] rounded-[8px]" />
            </div>
          ) : predictionResult && predictionResult.status !== 'unavailable' ? (
            /* Result Card */
            <section
              aria-label="Prediction Results"
              className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 shadow-xs space-y-6 animate-in fade-in duration-300"
            >
              {/* Header with Risk Badge */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border)] pb-4">
                <div>
                  <span className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider">
                    Evaluation Result
                  </span>
                  <h3 className="text-lg font-bold text-[var(--text)]">
                    {category} Purchase Plan
                  </h3>
                </div>

                {/* Waste Level Colour-Coded Badge */}
                <div
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-bold uppercase tracking-wide ${
                    getRiskBadgeStyles(predictionResult.predicted_waste_level).container
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      getRiskBadgeStyles(predictionResult.predicted_waste_level).dot
                    }`}
                  />
                  <span>
                    {predictionResult.predicted_waste_level} Waste Risk
                  </span>
                </div>
              </div>

              {/* Key Metrics Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {/* Forecast Demand */}
                <div className="rounded-[10px] bg-[var(--surface-2)] p-4 border border-[var(--border)]">
                  <div className="flex items-center justify-between text-xs text-[var(--muted)] mb-1">
                    <span>Forecast Demand</span>
                    <TrendingUp className="w-3.5 h-3.5 text-[var(--primary)]" />
                  </div>
                  <div className="text-2xl font-bold text-[var(--text)]">
                    {predictionResult.forecast_demand}{' '}
                    <span className="text-xs font-normal text-[var(--muted)]">units</span>
                  </div>
                  <div className="text-[11px] text-[var(--muted)] mt-1">
                    90% Range: {predictionResult.forecast_range?.min} –{' '}
                    {predictionResult.forecast_range?.max}
                  </div>
                </div>

                {/* Over-Order Ratio */}
                <div className="rounded-[10px] bg-[var(--surface-2)] p-4 border border-[var(--border)]">
                  <div className="flex items-center justify-between text-xs text-[var(--muted)] mb-1">
                    <span>Over-Order Ratio</span>
                    <Layers className="w-3.5 h-3.5 text-[var(--primary)]" />
                  </div>
                  <div className="text-2xl font-bold text-[var(--text)]">
                    {predictionResult.over_order_ratio}x
                  </div>
                  <div className="text-[11px] text-[var(--muted)] mt-1">
                    {predictionResult.over_order_ratio > 1.0 ? (
                      <span className="text-amber-500 font-semibold">
                        +{Math.round((predictionResult.over_order_ratio - 1) * 100)}% over forecast
                      </span>
                    ) : (
                      <span className="text-emerald-500 font-semibold">
                        Within expected demand
                      </span>
                    )}
                  </div>
                </div>

                {/* Recommended Quantity */}
                <div className="rounded-[10px] bg-[var(--surface-2)] p-4 border border-[var(--border)]">
                  <div className="flex items-center justify-between text-xs text-[var(--muted)] mb-1">
                    <span>Recommended</span>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  </div>
                  <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                    {predictionResult.recommended_quantity}{' '}
                    <span className="text-xs font-normal text-[var(--muted)]">units</span>
                  </div>
                  <div className="text-[11px] text-[var(--muted)] mt-1">
                    Safety stock + 70% shelf cap
                  </div>
                </div>
              </div>

              {/* Demand & Forecast Range Visualizer (Small Visual Chart) */}
              <div className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)]/60 p-4 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-[var(--text)]">
                    Demand Uncertainty Range (90% Interval)
                  </span>
                  <span className="text-[var(--muted)]">
                    Planned: <strong>{plannedQuantity}</strong> units
                  </span>
                </div>

                {/* Range Bar Graphic */}
                <div className="space-y-1.5 pt-1">
                  <div className="relative h-6 w-full bg-[var(--surface-2)] rounded-[6px] overflow-hidden border border-[var(--border)]">
                    {/* Interval Highlight */}
                    <div
                      className="absolute top-0 bottom-0 bg-[var(--primary)]/20 border-x border-[var(--primary)]"
                      style={{
                        left: `${Math.max(
                          0,
                          Math.min(
                            100,
                            (predictionResult.forecast_range.min /
                              Math.max(
                                1,
                                Math.max(
                                  predictionResult.forecast_range.max * 1.2,
                                  parseFloat(plannedQuantity) * 1.1
                                )
                              )) *
                              100
                          )
                        )}%`,
                        right: `${Math.max(
                          0,
                          100 -
                            (predictionResult.forecast_range.max /
                              Math.max(
                                1,
                                Math.max(
                                  predictionResult.forecast_range.max * 1.2,
                                  parseFloat(plannedQuantity) * 1.1
                                )
                              )) *
                              100
                        )}%`,
                      }}
                      title={`Range: ${predictionResult.forecast_range.min} to ${predictionResult.forecast_range.max}`}
                    />

                    {/* Forecast Demand Center Mark */}
                    <div
                      className="absolute top-0 bottom-0 w-1 bg-[var(--primary)]"
                      style={{
                        left: `${Math.max(
                          0,
                          Math.min(
                            100,
                            (predictionResult.forecast_demand /
                              Math.max(
                                1,
                                Math.max(
                                  predictionResult.forecast_range.max * 1.2,
                                  parseFloat(plannedQuantity) * 1.1
                                )
                              )) *
                              100
                          )
                        )}%`,
                      }}
                      title={`Forecast: ${predictionResult.forecast_demand}`}
                    />

                    {/* Planned Quantity Marker */}
                    <div
                      className="absolute top-0 bottom-0 w-1 bg-amber-500 z-10"
                      style={{
                        left: `${Math.max(
                          0,
                          Math.min(
                            100,
                            (parseFloat(plannedQuantity) /
                              Math.max(
                                1,
                                Math.max(
                                  predictionResult.forecast_range.max * 1.2,
                                  parseFloat(plannedQuantity) * 1.1
                                )
                              )) *
                              100
                          )
                        )}%`,
                      }}
                      title={`Planned: ${plannedQuantity}`}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-[var(--muted)]">
                    <span>Min: {predictionResult.forecast_range.min}</span>
                    <span className="flex items-center gap-1 text-[var(--primary)] font-medium">
                      <span className="w-2 h-2 rounded-full bg-[var(--primary)] inline-block" />
                      Forecast: {predictionResult.forecast_demand}
                    </span>
                    <span className="flex items-center gap-1 text-amber-500 font-medium">
                      <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
                      Planned: {plannedQuantity}
                    </span>
                    <span>Max: {predictionResult.forecast_range.max}</span>
                  </div>
                </div>
              </div>

              {/* Class Probability Distribution */}
              {predictionResult.waste_probabilities && (
                <div className="rounded-[10px] border border-[var(--border)] p-4 space-y-2.5">
                  <div className="flex items-center justify-between text-xs font-semibold text-[var(--text)]">
                    <span>Predicted Waste Level Probabilities</span>
                    <span className="text-[var(--muted)] font-normal text-[11px]">
                      Model v{predictionResult.model_version}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    {/* Low */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                          Low Risk
                        </span>
                        <span className="font-bold">
                          {Math.round((predictionResult.waste_probabilities.Low || 0) * 100)}%
                        </span>
                      </div>
                      <div className="h-2 w-full bg-[var(--surface-2)] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.min(
                              100,
                              Math.round((predictionResult.waste_probabilities.Low || 0) * 100)
                            )}%`,
                          }}
                        />
                      </div>
                    </div>

                    {/* Medium */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-amber-600 dark:text-amber-400 font-medium">
                          Medium
                        </span>
                        <span className="font-bold">
                          {Math.round((predictionResult.waste_probabilities.Medium || 0) * 100)}%
                        </span>
                      </div>
                      <div className="h-2 w-full bg-[var(--surface-2)] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-amber-500 rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.min(
                              100,
                              Math.round((predictionResult.waste_probabilities.Medium || 0) * 100)
                            )}%`,
                          }}
                        />
                      </div>
                    </div>

                    {/* High */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-red-600 dark:text-red-400 font-medium">
                          High Risk
                        </span>
                        <span className="font-bold">
                          {Math.round((predictionResult.waste_probabilities.High || 0) * 100)}%
                        </span>
                      </div>
                      <div className="h-2 w-full bg-[var(--surface-2)] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-red-500 rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.min(
                              100,
                              Math.round((predictionResult.waste_probabilities.High || 0) * 100)
                            )}%`,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Plain-Language Explanation */}
              <div className="rounded-[10px] bg-[var(--primary)]/5 border border-[var(--primary)]/20 p-4 flex items-start gap-3">
                <Info className="w-5 h-5 text-[var(--primary)] shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h4 className="text-xs font-semibold text-[var(--primary)] uppercase tracking-wider">
                    Operational Recommendation
                  </h4>
                  <p className="text-xs text-[var(--text)] leading-relaxed font-normal">
                    {predictionResult.explanation}
                  </p>
                </div>
              </div>

              {/* Confidence Note (Visible when inputs missing or unusual) */}
              {predictionResult.confidence_note && (
                <div className="rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-3 flex items-start gap-2.5 text-[11px] text-[var(--muted)]">
                  <HelpCircle className="w-4 h-4 text-[var(--muted)] shrink-0 mt-0.5" />
                  <span>{predictionResult.confidence_note}</span>
                </div>
              )}
            </section>
          ) : (
            /* Empty Initial State */
            <div className="rounded-[12px] border border-dashed border-[var(--border)] bg-[var(--surface)] p-12 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] flex items-center justify-center mx-auto">
                <Sparkles className="w-6 h-6" />
              </div>
              <h3 className="text-base font-semibold text-[var(--text)]">
                Ready to Evaluate Purchase Plan
              </h3>
              <p className="text-xs text-[var(--muted)] max-w-sm mx-auto">
                Select your food category and planned order quantity, then click &ldquo;Calculate
                Plan&rdquo; to forecast expected demand and avoid over-order waste.
              </p>
            </div>
          )}

          {/* Collapsible Panel: How is this calculated? */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
            <button
              type="button"
              onClick={() => setShowHowCalculated((prev) => !prev)}
              aria-expanded={showHowCalculated}
              className="w-full flex items-center justify-between p-4 text-xs font-semibold text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer"
            >
              <span className="flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-[var(--primary)]" />
                How is this calculated?
              </span>
              {showHowCalculated ? (
                <ChevronUp className="w-4 h-4 text-[var(--muted)]" />
              ) : (
                <ChevronDown className="w-4 h-4 text-[var(--muted)]" />
              )}
            </button>

            {showHowCalculated && (
              <div className="p-4 pt-1 border-t border-[var(--border)] space-y-3 text-xs text-[var(--muted)] leading-relaxed">
                <p>
                  <strong>1. Demand Forecasting:</strong> A generalized linear Poisson regression
                  estimates daily consumer demand based on commercial food category baseline,
                  weather condition multipliers, promotional lift, and day-of-week patterns.
                </p>
                <p>
                  <strong>2. Uncertainty Intervals:</strong> The 90% confidence range reflects a
                  normal approximation with a calibrated Poisson residual standard deviation of
                  &sigma; = 17.63 units.
                </p>
                <p>
                  <strong>3. Waste-Risk Classifier:</strong> A LightGBM gradient-boosted decision tree
                  evaluates the planned purchase against forecast demand and category shelf-life to
                  predict the probability of Low (&le;10%), Medium (10–25%), or High (&gt;25%) waste.
                </p>
                <p>
                  <strong>4. Recommended Order Quantity:</strong> Balances 90% service level safety
                  stock against spoilage constraints, capped at 70% of perishable shelf life.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
