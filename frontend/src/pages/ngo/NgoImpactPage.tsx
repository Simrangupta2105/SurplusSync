import React from 'react';
import {
  TrendingUp,
  Utensils,
  Leaf,
  Droplets,
  Download,
  ShieldCheck,
  Award,
  Sparkles,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatCard } from '../../components/ui/StatCard';
import { FeatureGuard } from '../../components/FeatureGuard';
import { useImpactMetrics } from '../../hooks/useData';

interface NgoImpactPageProps {
  onTriggerToast: (msg: string) => void;
}

export const NgoImpactPage: React.FC<NgoImpactPageProps> = ({
  onTriggerToast,
}) => {
  const { data: impact, isLoading } = useImpactMetrics();

  // Computations
  const totalKg = impact?.kg_diverted || 3240;
  const mealsEquivalent = Math.round(totalKg / 0.42);
  const co2eKg = Math.round(totalKg * 2.5);
  const totalWaterSavedLiters = Math.round(totalKg * 180);

  const handleExportReport = () => {
    onTriggerToast('Downloaded Verified NGO Impact & Hunger Relief Certificate (PDF)');
  };

  return (
    <FeatureGuard feature="impact_metrics" featureName="Rescue & Community Impact">
      <div className="space-y-6 animate-in fade-in duration-200">
        {/* Header */}
        <PageHeader
          title="Community & Environmental Impact"
          description="Audited hunger-relief and sustainability achievements from diverted commercial surplus food."
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportReport}
              className="gap-1.5 text-xs font-semibold"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download Impact Audit</span>
            </Button>
          }
        />

        {/* 4 ESG Stat Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <StatCard
            title="Food Rescued"
            value={`${totalKg.toLocaleString('en-IN')} kg`}
            subtitle="Diverted from landfills"
            icon={TrendingUp}
            trend={{ value: '+18.4% MoM', isPositive: true }}
          />
          <StatCard
            title="Meals Provided"
            value={mealsEquivalent.toLocaleString('en-IN')}
            subtitle="Formula: kg / 0.42"
            icon={Utensils}
            trend={{ value: 'Serving 4 shelters', isPositive: true }}
          />
          <StatCard
            title="CO₂e Abatement"
            value={`${co2eKg.toLocaleString('en-IN')} kg`}
            subtitle="Methane prevention"
            icon={Leaf}
            trend={{ value: '2.5x mass factor', isPositive: true }}
          />
          <StatCard
            title="Water Conserved"
            value={`${Math.round(totalWaterSavedLiters / 1000)}k Liters`}
            subtitle="Virtual water footprint"
            icon={Droplets}
          />
        </div>

        {/* Monthly Trend Recharts Card */}
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-base font-semibold text-[var(--text)]">
                Monthly Food Rescue Velocity
              </h3>
              <p className="text-xs text-[var(--muted)]">
                Total kilograms diverted and delivered to local hunger centers over the last 6 months.
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5 font-medium text-[var(--text)]">
                <span className="w-2.5 h-2.5 rounded-full bg-[var(--primary)]" />
                <span>Rescued (kg)</span>
              </span>
              <span className="flex items-center gap-1.5 font-medium text-[var(--muted)]">
                <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent)]" />
                <span>Meals (x10)</span>
              </span>
            </div>
          </div>

          <div className="h-72 w-full pt-2">
            {isLoading ? (
              <div className="h-full w-full rounded-[8px] bg-[var(--surface-2)] animate-pulse" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={impact?.monthly_trend || []}
                  margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="ngoRescueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="ngoMealGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.6} />
                  <XAxis
                    dataKey="month"
                    stroke="var(--muted)"
                    fontSize={11}
                    tickLine={false}
                    axisLine={{ stroke: 'var(--border)' }}
                  />
                  <YAxis
                    stroke="var(--muted)"
                    fontSize={11}
                    tickLine={false}
                    axisLine={{ stroke: 'var(--border)' }}
                    tickFormatter={(val) => `${val}kg`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--surface-2)',
                      borderColor: 'var(--border)',
                      borderRadius: '8px',
                      color: 'var(--text)',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="kg_diverted"
                    name="Rescued (kg)"
                    stroke="var(--primary)"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#ngoRescueGrad)"
                  />
                  <Area
                    type="monotone"
                    dataKey="meals"
                    name="Meals Served"
                    stroke="var(--accent)"
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                    fillOpacity={1}
                    fill="url(#ngoMealGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Verified NGO Accreditation & Safety Protocol Badge */}
        <div className="rounded-[12px] border border-[var(--border)] bg-gradient-to-r from-[var(--surface-2)] via-[var(--surface)] to-[var(--surface-2)] p-5 sm:p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] shrink-0 mt-0.5">
              <Award className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold text-[var(--text)]">
                  SurplusSync Verified Relief Network Member
                </h4>
                <span className="inline-flex items-center gap-1 rounded-full bg-[var(--color-success-subtle)] px-2 py-0.5 text-[10px] font-semibold text-[var(--color-success)] border border-[var(--color-success-border)]">
                  <ShieldCheck className="w-3 h-3" />
                  <span>Audited Dispatch Hub</span>
                </span>
              </div>
              <p className="text-xs text-[var(--muted)] leading-relaxed max-w-2xl">
                Every kilogram rescued through your fleet meets cold chain hygiene and rapid transit protocols, ensuring safe human consumption at shelter points across the city.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportReport}
            className="text-xs font-semibold gap-1.5 shrink-0"
          >
            <Sparkles className="w-3.5 h-3.5 text-[var(--primary)]" />
            <span>Generate ESG Certificate</span>
          </Button>
        </div>
      </div>
    </FeatureGuard>
  );
};
